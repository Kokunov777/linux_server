#!/usr/bin/env python3
"""Генерация реалистичного скриншота терминала (стиль carbon.now.sh)."""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

FREG = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FS = 30
font = ImageFont.truetype(FREG, FS)
fontb = ImageFont.truetype(BOLD, FS)

# палитра Dracula
BG      = (40, 42, 54)     # окно
FG      = (248, 248, 242)  # обычный текст
GRAY    = (98, 114, 164)   # комментарий/тусклый
GREEN   = (80, 250, 123)
CYAN    = (139, 233, 253)
PURPLE  = (189, 147, 249)
PINK    = (255, 121, 198)
ORANGE  = (255, 184, 108)
YELLOW  = (241, 250, 140)
SEP     = (68, 71, 90)

def seg(t, c, b=False):
    return (t, c, b)

# ----- содержимое (по логическим строкам -> список сегментов) -----
def prompt():
    return [seg("vladik@linux", GREEN, True), seg(":", FG), seg("~/rgr", CYAN, True), seg("$ ", FG)]

def log(ts, body_segs):
    return [seg(ts + " ", GRAY), seg("127.0.0.1", PURPLE), seg(" | ", SEP)] + body_segs

TS = "[2026-06-04 11:41:56]"
lines = [
    prompt() + [seg("make", FG, True)],
    [seg("cc -O2 -Wall -Wextra -o src/server src/server.c -lpthread", GRAY)],
    prompt() + [seg("cd src && ./server 5555", FG, True)],
    [seg("[!] ", YELLOW, True), seg("Файл users.conf не найден — создан пользователь:", YELLOW)],
    [seg("    логин: ", FG), seg("admin", ORANGE), seg("   пароль: ", FG), seg("admin123", ORANGE)],
    [seg("[*] ", CYAN, True), seg("Загружено пользователей: 1", CYAN)],
    [seg("[*] ", CYAN, True), seg("Сервер слушает порт 5555. Журнал: server.log", CYAN)],
    log(TS, [seg("новое подключение", FG)]),
    log(TS, [seg("успешная авторизация ", GREEN), seg("user=admin", ORANGE)]),
    log(TS, [seg("user=admin", ORANGE), seg(" CMD: ", PINK), seg("whoami", FG)]),
    log(TS, [seg("user=admin", ORANGE), seg(" CMD: ", PINK), seg("uname -srm", FG)]),
    log(TS, [seg("user=admin", ORANGE), seg(" CMD: ", PINK), seg("echo Привет, РГР!", FG)]),
    log(TS, [seg("user=admin", ORANGE), seg(" CMD: ", PINK), seg("ls -1 | head -4", FG)]),
    log(TS, [seg("user=admin", ORANGE), seg(" CMD: ", PINK), seg("id -u", FG)]),
    log(TS, [seg("отключение ", FG), seg("user=admin", ORANGE)]),
    [seg("█", GREEN)],
]

# ----- геометрия -----
PAD_X, PAD_TOP = 34, 70          # отступы текста внутри окна (top — под заголовком)
PAD_BOT = 28
LH = FS + 12                     # высота строки
def line_width(segs):
    return sum(font.getlength(t) for t, _, _ in segs)
text_w = max(line_width(s) for s in lines)
win_w = int(text_w + PAD_X * 2)
win_h = int(PAD_TOP + LH * len(lines) + PAD_BOT)

MARGIN = 80                      # поле вокруг окна (фон)
W, H = win_w + MARGIN * 2, win_h + MARGIN * 2

# ----- фон-градиент (диагональ, "Kashmir") -----
c1, c2 = np.array([43, 88, 118]), np.array([78, 67, 118])
yy, xx = np.mgrid[0:H, 0:W]
t = (xx + yy) / (W + H)
grad = (c1[None, None, :] * (1 - t)[..., None] + c2[None, None, :] * t[..., None]).astype("uint8")
img = Image.fromarray(grad, "RGB")
draw = ImageDraw.Draw(img)

# ----- тень окна -----
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle([MARGIN, MARGIN + 14, MARGIN + win_w, MARGIN + win_h + 14],
                     radius=16, fill=(0, 0, 0, 150))
shadow = shadow.filter(ImageFilter.GaussianBlur(22))
img = Image.alpha_composite(img.convert("RGBA"), shadow)
draw = ImageDraw.Draw(img)

# ----- окно -----
x0, y0 = MARGIN, MARGIN
x1, y1 = MARGIN + win_w, MARGIN + win_h
draw.rounded_rectangle([x0, y0, x1, y1], radius=16, fill=BG)

# светофор
for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    cx = x0 + 28 + i * 28
    cy = y0 + 28
    draw.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=col)

# заголовок окна по центру
title = "vladik@linux: ~/rgr/src"
tf = ImageFont.truetype(FREG, 24)
tw = tf.getlength(title)
draw.text((x0 + (win_w - tw) / 2, y0 + 16), title, font=tf, fill=(150, 153, 170))

# ----- текст -----
y = y0 + PAD_TOP
for segs in lines:
    x = x0 + PAD_X
    for t_, c_, b_ in segs:
        f = fontb if b_ else font
        draw.text((x, y), t_, font=f, fill=c_)
        x += font.getlength(t_)
    y += LH

img.convert("RGB").save("/home/claude/rgr/img/terminal.png", quality=95)
print("Создан скриншот:", img.size)
