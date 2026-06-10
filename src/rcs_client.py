"""
rcs_client.py — сетевой клиент протокола RCS (Remote Command Service).

Реализует тот же протокол, что и server.c:
  - кадрирование: 4 байта длины (big-endian) + полезная нагрузка;
  - аутентификация challenge-response с солёным SHA-256 и одноразовым nonce
    (пароль по сети в открытом виде НЕ передаётся).

Класс RCSClient не зависит от GUI — его используют и графический клиент,
и автотесты протокола.
"""

import socket
import struct
import hashlib


class RCSError(Exception):
    """Ошибка протокола или авторизации."""


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class RCSClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 5555, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.username: str | None = None

    # ---------- низкоуровневое кадрирование ----------
    def _send_frame(self, payload: str) -> None:
        data = payload.encode("utf-8")
        self.sock.sendall(struct.pack("!I", len(data)) + data)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RCSError("соединение закрыто сервером")
            buf += chunk
        return buf

    def _recv_frame(self) -> tuple[str, str]:
        (length,) = struct.unpack("!I", self._recv_exact(4))
        if length == 0 or length > (1 << 20):
            raise RCSError("некорректный размер кадра")
        payload = self._recv_exact(length).decode("utf-8", errors="replace")
        # формат: "TYPE\nтекст"
        if "\n" in payload:
            head, body = payload.split("\n", 1)
        else:
            head, body = payload, ""
        return head, body

    # ---------- публичный API ----------
    def connect(self, username: str, password: str) -> str:
        """Подключиться и пройти авторизацию. Возвращает приветствие сервера."""
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.username = username

        # 1. отправляем имя пользователя
        self._send_frame(f"USER\n{username}")

        # 2. получаем соль и nonce
        head, body = self._recv_frame()
        if head != "CHALLENGE":
            raise RCSError(f"ожидался CHALLENGE, получено: {head} {body}")
        salt, nonce = body.split("\n", 1)

        # 3. вычисляем ответ: H = SHA256(salt+password); resp = SHA256(H+nonce)
        h = _sha256_hex(salt + password)
        resp = _sha256_hex(h + nonce)
        self._send_frame(f"RESP\n{resp}")

        # 4. результат авторизации
        head, body = self._recv_frame()
        if head == "OK":
            return body
        self.close()
        raise RCSError(body or "авторизация отклонена")

    def execute(self, command: str) -> str:
        """Выполнить команду на сервере и вернуть её вывод."""
        if not self.sock:
            raise RCSError("нет подключения")
        self._send_frame(f"CMD\n{command}")
        head, body = self._recv_frame()
        if head == "OUT":
            return body
        if head == "ERR":
            raise RCSError(body)
        raise RCSError(f"неожиданный ответ: {head}")

    def close(self) -> None:
        if self.sock:
            try:
                self._send_frame("QUIT")
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
