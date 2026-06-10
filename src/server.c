/*
 * server.c — Безопасный сервер удалённого выполнения команд (РГР, Linux).
 *
 * Возможности:
 *   - TCP-сервер, каждый клиент обслуживается в отдельном потоке (pthread);
 *   - аутентификация по схеме challenge-response: пароль НЕ передаётся
 *     по сети в открытом виде, используется одноразовый nonce -> защита
 *     от перехвата и повтора (replay);
 *   - пароли хранятся не в открытом виде, а в виде солёного хэша SHA-256;
 *   - выполнение команд разрешено только после успешной авторизации;
 *   - кадрирование сообщений (4 байта длины + полезная нагрузка) — нет
 *     проблемы "слипания" пакетов, ограничение длины защищает от DoS;
 *   - аудит-журнал: время, IP клиента, имя пользователя, команда;
 *   - защита от перебора: пауза и разрыв соединения при неверном пароле.
 *
 * Сборка:  gcc -O2 -Wall -o server server.c -lpthread
 * Запуск:  ./server [порт]      (порт по умолчанию 5555)
 *
 * Реализация SHA-256 встроена (public domain), внешних зависимостей нет.
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <signal.h>
#include <time.h>
#include <errno.h>
#include <fcntl.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <netinet/in.h>

/* ===================== Параметры ===================== */
#define DEFAULT_PORT   5555
#define MAX_FRAME      (1u << 20)   /* 1 МБ — максимальный размер кадра      */
#define MAX_OUTPUT     (1u << 20)   /* 1 МБ — максимальный размер вывода      */
#define MAX_USERS      64
#define MAX_BACKLOG    16
#define AUTH_FAIL_WAIT 2            /* сек паузы после неверной попытки      */
#define USERS_FILE     "users.conf"
#define LOG_FILE       "server.log"

/* ===================== SHA-256 (public domain) ===================== */
typedef struct {
    uint8_t  data[64];
    uint32_t datalen;
    uint64_t bitlen;
    uint32_t state[8];
} SHA256_CTX;

#define ROTR(a,b) (((a) >> (b)) | ((a) << (32-(b))))
#define CH(x,y,z)  (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)  (ROTR(x,2) ^ ROTR(x,13) ^ ROTR(x,22))
#define EP1(x)  (ROTR(x,6) ^ ROTR(x,11) ^ ROTR(x,25))
#define SIG0(x) (ROTR(x,7) ^ ROTR(x,18) ^ ((x) >> 3))
#define SIG1(x) (ROTR(x,17) ^ ROTR(x,19) ^ ((x) >> 10))

static const uint32_t K[64] = {
  0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
  0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
  0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
  0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
  0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
  0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
  0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
  0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

static void sha256_transform(SHA256_CTX *ctx, const uint8_t data[]) {
    uint32_t a,b,c,d,e,f,g,h,i,j,t1,t2,m[64];
    for (i=0,j=0; i<16; ++i,j+=4)
        m[i] = (data[j]<<24)|(data[j+1]<<16)|(data[j+2]<<8)|(data[j+3]);
    for (; i<64; ++i)
        m[i] = SIG1(m[i-2]) + m[i-7] + SIG0(m[i-15]) + m[i-16];
    a=ctx->state[0]; b=ctx->state[1]; c=ctx->state[2]; d=ctx->state[3];
    e=ctx->state[4]; f=ctx->state[5]; g=ctx->state[6]; h=ctx->state[7];
    for (i=0; i<64; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + K[i] + m[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    ctx->state[0]+=a; ctx->state[1]+=b; ctx->state[2]+=c; ctx->state[3]+=d;
    ctx->state[4]+=e; ctx->state[5]+=f; ctx->state[6]+=g; ctx->state[7]+=h;
}

static void sha256_init(SHA256_CTX *ctx) {
    ctx->datalen=0; ctx->bitlen=0;
    ctx->state[0]=0x6a09e667; ctx->state[1]=0xbb67ae85;
    ctx->state[2]=0x3c6ef372; ctx->state[3]=0xa54ff53a;
    ctx->state[4]=0x510e527f; ctx->state[5]=0x9b05688c;
    ctx->state[6]=0x1f83d9ab; ctx->state[7]=0x5be0cd19;
}

static void sha256_update(SHA256_CTX *ctx, const uint8_t *data, size_t len) {
    for (size_t i=0; i<len; ++i) {
        ctx->data[ctx->datalen++] = data[i];
        if (ctx->datalen == 64) {
            sha256_transform(ctx, ctx->data);
            ctx->bitlen += 512;
            ctx->datalen = 0;
        }
    }
}

static void sha256_final(SHA256_CTX *ctx, uint8_t hash[32]) {
    uint32_t i = ctx->datalen;
    ctx->data[i++] = 0x80;
    if (ctx->datalen < 56) {
        while (i < 56) ctx->data[i++] = 0;
    } else {
        while (i < 64) ctx->data[i++] = 0;
        sha256_transform(ctx, ctx->data);
        memset(ctx->data, 0, 56);
    }
    ctx->bitlen += (uint64_t)ctx->datalen * 8;
    for (int j=0;j<8;++j) ctx->data[63-j] = (uint8_t)(ctx->bitlen >> (8*j));
    sha256_transform(ctx, ctx->data);
    for (i=0;i<4;++i)
        for (int j=0;j<8;++j)
            hash[i + j*4] = (ctx->state[j] >> (24 - i*8)) & 0xff;
}

/* Хэш строки -> 64 hex-символа (нижний регистр) в out (>=65 байт). */
static void sha256_hex(const char *s, char *out) {
    SHA256_CTX c; uint8_t h[32];
    sha256_init(&c);
    sha256_update(&c, (const uint8_t*)s, strlen(s));
    sha256_final(&c, h);
    static const char hx[] = "0123456789abcdef";
    for (int i=0;i<32;++i) { out[i*2]=hx[h[i]>>4]; out[i*2+1]=hx[h[i]&0xf]; }
    out[64]='\0';
}

/* ===================== Пользователи ===================== */
typedef struct {
    char name[64];
    char salt[33];   /* 16 байт -> 32 hex                       */
    char hash[65];   /* H = SHA256(salt + password), 64 hex     */
} User;

static User   g_users[MAX_USERS];
static int    g_user_count = 0;
static pthread_mutex_t g_log_mtx = PTHREAD_MUTEX_INITIALIZER;

/* Случайные hex-байты из /dev/urandom. */
static void random_hex(char *out, int nbytes) {
    uint8_t buf[64];
    if (nbytes > 64) nbytes = 64;
    int fd = open("/dev/urandom", O_RDONLY);
    if (fd >= 0) { if (read(fd, buf, nbytes) != nbytes) { /* fallback */ } close(fd); }
    else { for (int i=0;i<nbytes;++i) buf[i] = rand() & 0xff; }
    static const char hx[] = "0123456789abcdef";
    for (int i=0;i<nbytes;++i){ out[i*2]=hx[buf[i]>>4]; out[i*2+1]=hx[buf[i]&0xf]; }
    out[nbytes*2]='\0';
}

/* Вычислить H = SHA256(salt + password). */
static void compute_hash(const char *salt, const char *password, char *out_hex) {
    char buf[256];
    snprintf(buf, sizeof(buf), "%s%s", salt, password);
    sha256_hex(buf, out_hex);
}

/* Загрузить пользователей из файла. Формат строки: name:salt:hash */
static int load_users(void) {
    FILE *f = fopen(USERS_FILE, "r");
    if (!f) return 0;
    char line[512];
    while (fgets(line, sizeof(line), f) && g_user_count < MAX_USERS) {
        char *nl = strchr(line, '\n'); if (nl) *nl = '\0';
        if (line[0]=='\0' || line[0]=='#') continue;
        User *u = &g_users[g_user_count];
        /* поля ограничены по ширине -> переполнение невозможно */
        if (sscanf(line, "%63[^:]:%32[^:]:%64[^\n]", u->name, u->salt, u->hash) == 3)
            g_user_count++;
    }
    fclose(f);
    return g_user_count;
}

/* Создать users.conf с пользователем по умолчанию admin / admin123. */
static void create_default_users(void) {
    User *u = &g_users[g_user_count++];
    strcpy(u->name, "admin");
    random_hex(u->salt, 16);
    compute_hash(u->salt, "admin123", u->hash);

    FILE *f = fopen(USERS_FILE, "w");
    if (f) {
        fprintf(f, "# Формат: имя:соль:хэш  (хэш = SHA256(соль+пароль))\n");
        fprintf(f, "%s:%s:%s\n", u->name, u->salt, u->hash);
        fclose(f);
        chmod(USERS_FILE, 0600);
    }
    fprintf(stderr,
        "[!] Файл %s не найден — создан пользователь по умолчанию:\n"
        "    логин: admin   пароль: admin123\n"
        "    ОБЯЗАТЕЛЬНО смените пароль для боевой эксплуатации!\n",
        USERS_FILE);
}

static User *find_user(const char *name) {
    for (int i=0;i<g_user_count;++i)
        if (strcmp(g_users[i].name, name)==0) return &g_users[i];
    return NULL;
}

/* ===================== Журналирование ===================== */
static void logmsg(const char *ip, const char *fmt, ...) {
    char ts[32];
    time_t t = time(NULL);
    struct tm tmv; localtime_r(&t, &tmv);
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", &tmv);

    char body[1024];
    va_list ap; va_start(ap, fmt);
    vsnprintf(body, sizeof(body), fmt, ap);
    va_end(ap);

    pthread_mutex_lock(&g_log_mtx);
    fprintf(stdout, "[%s] %s | %s\n", ts, ip?ip:"-", body);
    fflush(stdout);
    FILE *f = fopen(LOG_FILE, "a");
    if (f) { fprintf(f, "[%s] %s | %s\n", ts, ip?ip:"-", body); fclose(f); }
    pthread_mutex_unlock(&g_log_mtx);
}

/* ===================== Кадрирование TCP ===================== */
/* Гарантированно прочитать n байт. Возврат: 0 — ок, -1 — ошибка/разрыв. */
static int recv_all(int fd, void *buf, size_t n) {
    uint8_t *p = buf; size_t got = 0;
    while (got < n) {
        ssize_t r = recv(fd, p+got, n-got, 0);
        if (r <= 0) return -1;
        got += (size_t)r;
    }
    return 0;
}
static int send_all(int fd, const void *buf, size_t n) {
    const uint8_t *p = buf; size_t sent = 0;
    while (sent < n) {
        ssize_t r = send(fd, p+sent, n-sent, MSG_NOSIGNAL);
        if (r <= 0) return -1;
        sent += (size_t)r;
    }
    return 0;
}
/* Прочитать кадр: [uint32 len][payload]. Выделяет память (free у вызывающего). */
static char *recv_frame(int fd, size_t *out_len) {
    uint32_t netlen;
    if (recv_all(fd, &netlen, 4) != 0) return NULL;
    uint32_t len = ntohl(netlen);
    if (len == 0 || len > MAX_FRAME) return NULL;
    char *buf = malloc(len + 1);
    if (!buf) return NULL;
    if (recv_all(fd, buf, len) != 0) { free(buf); return NULL; }
    buf[len] = '\0';
    if (out_len) *out_len = len;
    return buf;
}
static int send_frame(int fd, const char *payload, size_t len) {
    uint32_t netlen = htonl((uint32_t)len);
    if (send_all(fd, &netlen, 4) != 0) return -1;
    return send_all(fd, payload, len);
}
/* Удобный помощник: отправить "TYPE\nтекст". */
static int send_msg(int fd, const char *type, const char *text) {
    char *buf; size_t n;
    n = strlen(type) + 1 + (text ? strlen(text) : 0);
    buf = malloc(n + 1);
    if (!buf) return -1;
    if (text) snprintf(buf, n+1, "%s\n%s", type, text);
    else      snprintf(buf, n+1, "%s\n", type);
    int rc = send_frame(fd, buf, strlen(buf));
    free(buf);
    return rc;
}

/* ===================== Выполнение команды ===================== */
static void run_command(int fd, const char *ip, const char *user, const char *cmd) {
    logmsg(ip, "user=%s CMD: %s", user, cmd);

    /* stderr перенаправляем в stdout, чтобы вернуть и ошибки. */
    char full[8192];
    snprintf(full, sizeof(full), "%s 2>&1", cmd);

    FILE *pp = popen(full, "r");
    if (!pp) { send_msg(fd, "OUT", "[ошибка] не удалось запустить команду"); return; }

    char *out = malloc(MAX_OUTPUT + 1);
    if (!out) { pclose(pp); send_msg(fd, "OUT", "[ошибка] нет памяти"); return; }

    size_t total = 0; size_t r;
    while ((r = fread(out+total, 1, MAX_OUTPUT-total, pp)) > 0) {
        total += r;
        if (total >= MAX_OUTPUT) break;
    }
    out[total] = '\0';
    int code = pclose(pp);

    char header[128];
    snprintf(header, sizeof(header), "[код возврата: %d]\n", WEXITSTATUS(code));

    char *msg = malloc(strlen(header) + total + 16);
    sprintf(msg, "%s%s", header, out);
    send_msg(fd, "OUT", msg);
    free(msg);
    free(out);
}

/* ===================== Обработка клиента ===================== */
typedef struct { int fd; char ip[INET_ADDRSTRLEN]; } ClientArg;

static void *client_thread(void *arg) {
    ClientArg ca = *(ClientArg*)arg;
    free(arg);
    int fd = ca.fd;

    logmsg(ca.ip, "новое подключение");

    /* --- Шаг 1: клиент присылает имя пользователя --- */
    size_t len;
    char *frame = recv_frame(fd, &len);
    if (!frame) { close(fd); logmsg(ca.ip, "соединение разорвано (до USER)"); return NULL; }

    /* Ожидаем "USER\n<имя>" */
    char username[64] = {0};
    if (strncmp(frame, "USER\n", 5) == 0) {
        strncpy(username, frame+5, sizeof(username)-1);
    }
    free(frame);
    if (username[0] == '\0') { send_msg(fd, "ERR", "ожидалось имя пользователя"); close(fd); return NULL; }

    /* --- Шаг 2: сервер отправляет соль и одноразовый nonce --- */
    User *u = find_user(username);
    char salt[33], nonce[33];
    random_hex(nonce, 16);
    /* Чтобы нельзя было по соли узнать о существовании пользователя,
       для несуществующего выдаём псевдослучайную соль. */
    if (u) strncpy(salt, u->salt, sizeof(salt));
    else   random_hex(salt, 16);

    char challenge[128];
    snprintf(challenge, sizeof(challenge), "%s\n%s", salt, nonce);
    if (send_msg(fd, "CHALLENGE", challenge) != 0) { close(fd); return NULL; }

    /* --- Шаг 3: клиент присылает RESP = SHA256(H + nonce) --- */
    frame = recv_frame(fd, &len);
    if (!frame) { close(fd); logmsg(ca.ip, "соединение разорвано (до RESP)"); return NULL; }
    char client_resp[65] = {0};
    if (strncmp(frame, "RESP\n", 5) == 0)
        strncpy(client_resp, frame+5, sizeof(client_resp)-1);
    free(frame);

    /* --- Проверка ответа --- */
    int ok = 0;
    if (u) {
        char concat[160], expected[65];
        snprintf(concat, sizeof(concat), "%s%s", u->hash, nonce);
        sha256_hex(concat, expected);
        if (strcmp(expected, client_resp) == 0) ok = 1;
    }

    if (!ok) {
        logmsg(ca.ip, "НЕУДАЧНАЯ авторизация user=%s", username);
        sleep(AUTH_FAIL_WAIT);                 /* антиперебор */
        send_msg(fd, "ERR", "Неверный логин или пароль");
        close(fd);
        return NULL;
    }

    logmsg(ca.ip, "успешная авторизация user=%s", username);
    send_msg(fd, "OK", "Авторизация успешна. Введите команду.");

    /* --- Основной цикл: приём и выполнение команд --- */
    for (;;) {
        frame = recv_frame(fd, &len);
        if (!frame) break;

        if (strncmp(frame, "CMD\n", 4) == 0) {
            const char *cmd = frame + 4;
            if (cmd[0] != '\0') run_command(fd, ca.ip, username, cmd);
            else send_msg(fd, "OUT", "[пустая команда]");
        } else if (strncmp(frame, "QUIT", 4) == 0) {
            free(frame);
            break;
        } else {
            send_msg(fd, "ERR", "неизвестная команда протокола");
        }
        free(frame);
    }

    logmsg(ca.ip, "отключение user=%s", username);
    close(fd);
    return NULL;
}

/* ===================== main ===================== */
int main(int argc, char **argv) {
    signal(SIGPIPE, SIG_IGN);
    srand((unsigned)time(NULL));

    int port = (argc > 1) ? atoi(argv[1]) : DEFAULT_PORT;
    if (port <= 0 || port > 65535) port = DEFAULT_PORT;

    if (load_users() == 0) create_default_users();
    fprintf(stderr, "[*] Загружено пользователей: %d\n", g_user_count);

    int srv = socket(AF_INET, SOCK_STREAM, 0);
    if (srv < 0) { perror("socket"); return 1; }
    int yes = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(port);

    if (bind(srv, (struct sockaddr*)&addr, sizeof(addr)) < 0) { perror("bind"); return 1; }
    if (listen(srv, MAX_BACKLOG) < 0) { perror("listen"); return 1; }

    fprintf(stderr, "[*] Сервер слушает порт %d. Журнал: %s\n", port, LOG_FILE);

    for (;;) {
        struct sockaddr_in cli; socklen_t cl = sizeof(cli);
        int fd = accept(srv, (struct sockaddr*)&cli, &cl);
        if (fd < 0) { if (errno==EINTR) continue; perror("accept"); break; }

        ClientArg *ca = malloc(sizeof(ClientArg));
        ca->fd = fd;
        inet_ntop(AF_INET, &cli.sin_addr, ca->ip, sizeof(ca->ip));

        pthread_t th;
        if (pthread_create(&th, NULL, client_thread, ca) != 0) {
            perror("pthread_create"); close(fd); free(ca);
        } else {
            pthread_detach(th);
        }
    }

    close(srv);
    return 0;
}
