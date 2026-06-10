#!/usr/bin/env python3
"""Реалистичный скриншот окна графического клиента (Tkinter, тема clam) в Linux."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANSB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

def F(path, sz): return ImageFont.truetype(path, sz)
ui   = F(SANS, 26)
uib  = F(SANSB, 26)
uismall = F(SANS, 23)
mono = F(MONO, 25)
titlef = F(SANS, 27)

WIN_W, WIN_H = 1500, 1040
M = 72
W, H = WIN_W + M * 2, WIN_H + M * 2

# цвета окна (светлая тема GNOME/clam)
HDR1, HDR2 = (246, 245, 244), (228, 228, 226)
HDR_BORDER = (200, 196, 192)
CONTENT = (237, 237, 237)
FRAME_BORDER = (176, 176, 176)
ENTRY_BG = (255, 255, 255)
ENTRY_BORDER = (158, 158, 158)
BTN_BG, BTN_BORDER = (224, 224, 224), (150, 150, 150)
TXT = (40, 44, 52)
# тёмная область вывода (как в client_gui.py)
OUT_BG, OUT_FG = (30, 30, 30), (220, 220, 220)
C_OK, C_CMD, C_ERR, C_SYS = (137, 209, 133), (197, 134, 192), (244, 135, 113), (79, 193, 255)

# ---------- фон-градиент (тот же стиль, что у скриншота терминала) ----------
c1, c2 = np.array([43, 88, 118]), np.array([78, 67, 118])
yy, xx = np.mgrid[0:H, 0:W]
t = (xx + yy) / (W + H)
grad = (c1[None, None, :] * (1 - t)[..., None] + c2[None, None, :] * t[..., None]).astype("uint8")
img = Image.fromarray(grad, "RGB").convert("RGBA")

# ---------- тень окна ----------
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle([M, M + 16, M + WIN_W, M + WIN_H + 16], radius=14, fill=(0, 0, 0, 150))
img = Image.alpha_composite(img, shadow.filter(ImageFilter.GaussianBlur(24)))
d = ImageDraw.Draw(img)

ox, oy = M, M  # origin окна

def rrect(xy, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

# корпус окна
rrect([ox, oy, ox + WIN_W, oy + WIN_H], 14, fill=CONTENT)

# ---------- заголовок (headerbar) ----------
HDR_H = 64
hdr = Image.new("RGB", (WIN_W, HDR_H))
for i in range(HDR_H):
    k = i / HDR_H
    col = tuple(int(HDR1[j] * (1 - k) + HDR2[j] * k) for j in range(3))
    ImageDraw.Draw(hdr).line([(0, i), (WIN_W, i)], fill=col)
# скруглим верхние углы заголовка
mask = Image.new("L", (WIN_W, HDR_H), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, WIN_W, HDR_H + 14], radius=14, fill=255)
img.paste(hdr, (ox, oy), mask)
d.line([(ox, oy + HDR_H), (ox + WIN_W, oy + HDR_H)], fill=HDR_BORDER, width=2)

# заголовок окна
title = "Удалённое выполнение команд — клиент (РГР)"
tw = d.textlength(title, font=titlef)
d.text((ox + (WIN_W - tw) / 2, oy + 18), title, font=titlef, fill=TXT)

# кнопки окна (свернуть / развернуть / закрыть) справа
bx = ox + WIN_W - 56
for sym in ["✕"]:
    d.ellipse([bx - 18, oy + 14, bx + 18, oy + 50], fill=(231, 76, 60))
    d.text((bx - d.textlength(sym, font=uismall) / 2, oy + 20), sym, font=uismall, fill=(255, 255, 255))
# минимизировать/развернуть как простые значки
d.line([(bx - 84, oy + 36), (bx - 64, oy + 36)], fill=(120, 120, 120), width=3)
d.rectangle([bx - 140, oy + 22, bx - 118, oy + 44], outline=(120, 120, 120), width=3)

cx0 = ox + 24  # левый внутренний край

def labelframe(y0, y1, caption):
    rrect([cx0, oy + y0, ox + WIN_W - 24, oy + y1], 6, outline=FRAME_BORDER, width=2)
    w = d.textlength(caption, font=uismall)
    d.rectangle([cx0 + 18, oy + y0 - 14, cx0 + 30 + w, oy + y0 + 14], fill=CONTENT)
    d.text((cx0 + 26, oy + y0 - 14), caption, font=uismall, fill=(90, 90, 90))

def entry(x, y, w, text, mono_f=True, mask=False, focus=False):
    d.rounded_rectangle([x, y, x + w, y + 40], radius=4, fill=ENTRY_BG,
                        outline=(70, 130, 220) if focus else ENTRY_BORDER, width=2 if focus else 1)
    f = mono if mono_f else ui
    s = "•" * len(text) if mask else text
    d.text((x + 10, y + 6), s, font=f, fill=TXT)

def button(x, y, w, text):
    d.rounded_rectangle([x, y, x + w, y + 42], radius=5, fill=BTN_BG, outline=BTN_BORDER, width=1)
    tw = d.textlength(text, font=ui)
    d.text((x + (w - tw) / 2, y + 6), text, font=ui, fill=TXT)
    return x + w

# ---------- панель подключения ----------
labelframe(96, 196, "Подключение")
ry = oy + 128
def lbl(x, text):
    d.text((x, ry + 6), text, font=ui, fill=TXT)
    return x + d.textlength(text, font=ui) + 10
# кнопки привязаны к правому краю панели, с зазором
frame_right = ox + WIN_W - 24
w_disc, w_conn, gap = 168, 188, 16
bx_disc = frame_right - 16 - w_disc
bx_conn = bx_disc - gap - w_conn
# поля слева
x = cx0 + 24
x = lbl(x, "Хост:");    entry(x, ry, 150, "127.0.0.1"); x += 164
x = lbl(x, "Порт:");    entry(x, ry, 80, "5555");        x += 94
x = lbl(x, "Логин:");   entry(x, ry, 135, "admin");      x += 149
x = lbl(x, "Пароль:");  entry(x, ry, 135, "admin123", mask=True)
button(bx_conn, ry - 1, w_conn, "Подключиться")
button(bx_disc, ry - 1, w_disc, "Отключиться")

# ---------- область вывода ----------
labelframe(228, 812, "Вывод")
out_x0, out_y0 = cx0 + 14, oy + 248
out_x1, out_y1 = ox + WIN_W - 60, oy + 798
d.rectangle([out_x0, out_y0, out_x1, out_y1], fill=OUT_BG)
# полоса прокрутки
d.rectangle([out_x1 + 6, out_y0, out_x1 + 22, out_y1], fill=(210, 210, 210))
d.rounded_rectangle([out_x1 + 8, out_y0 + 6, out_x1 + 20, out_y0 + 150], radius=6, fill=(150, 150, 150))

out_lines = [
    ("[+] Авторизация успешна. Введите команду.", C_OK),
    ("$ whoami", C_CMD),
    ("[код возврата: 0]", OUT_FG),
    ("vladik", OUT_FG),
    ("$ uname -srm", C_CMD),
    ("[код возврата: 0]", OUT_FG),
    ("Linux 6.8.0-52-generic x86_64", OUT_FG),
    ("$ echo Привет, РГР!", C_CMD),
    ("[код возврата: 0]", OUT_FG),
    ("Привет, РГР!", OUT_FG),
    ("$ ls -1 | head -4", C_CMD),
    ("[код возврата: 0]", OUT_FG),
    ("client_gui.py", OUT_FG),
    ("mkuser.py", OUT_FG),
    ("rcs_client.py", OUT_FG),
    ("server.c", OUT_FG),
]
ty = out_y0 + 12
for text, col in out_lines:
    d.text((out_x0 + 14, ty), text, font=mono, fill=col)
    ty += 33

# ---------- строка команды ----------
cy = oy + 844
d.text((cx0 + 24, cy + 6), "Команда:", font=ui, fill=TXT)
cmd_x = cx0 + 24 + d.textlength("Команда:", font=ui) + 14
entry(cmd_x, cy, WIN_W - (cmd_x - ox) - 220, "df -h", focus=True)
# курсор
d.line([(cmd_x + 10 + d.textlength("df -h", font=mono) + 3, cy + 8),
        (cmd_x + 10 + d.textlength("df -h", font=mono) + 3, cy + 34)], fill=TXT, width=2)
button(ox + WIN_W - 24 - 180, cy - 1, 180, "Выполнить")

# ---------- строка состояния ----------
st_y = oy + WIN_H - 48
d.rectangle([ox + 2, st_y, ox + WIN_W - 2, oy + WIN_H - 4], fill=(225, 225, 225), outline=(180, 180, 180))
d.text((ox + 18, st_y + 8), "Подключено: admin@127.0.0.1:5555", font=uismall, fill=(70, 70, 70))

img.convert("RGB").save("/home/claude/rgr/img/gui.png", quality=95)
print("Создан скриншот GUI:", img.size)
