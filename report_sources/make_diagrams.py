#!/usr/bin/env python3
"""Генерация диаграмм для пояснительной записки (PNG, высокое разрешение)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import os

plt.rcParams["font.family"] = "DejaVu Sans"
OUT = "/home/claude/rgr/img"
os.makedirs(OUT, exist_ok=True)

ACCENT = "#1F4E79"
LIGHT = "#D9E2F3"
GREEN = "#C6E0B4"
GRAY = "#E7E7E7"


def box(ax, x, y, w, h, text, fc=LIGHT, ec=ACCENT, fs=11, bold=False):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                       linewidth=1.4, edgecolor=ec, facecolor=fc)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, fontweight="bold" if bold else "normal", color="#1a1a1a")


def arrow(ax, x1, y1, x2, y2, text="", style="-|>", color="#333", fs=9, dashed=False, off=0.12):
    ls = (0, (4, 3)) if dashed else "-"
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=14,
                        linewidth=1.3, color=color, linestyle=ls)
    ax.add_patch(a)
    if text:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + off, text, ha="center", va="bottom",
                fontsize=fs, color="#222")


# ---------- 1. Архитектура ----------
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.set_xlim(0, 12); ax.set_ylim(0, 8); ax.axis("off")

# клиентская часть
ax.add_patch(Rectangle((0.2, 0.4), 4.6, 7.2, fill=False, edgecolor="#888", linestyle="--", linewidth=1.2))
ax.text(2.5, 7.25, "Клиент", ha="center", fontsize=12, fontweight="bold", color=ACCENT)
box(ax, 0.7, 5.3, 3.6, 1.4, "Графический интерфейс\nclient_gui.py (Tkinter)", fc=GREEN, fs=10)
box(ax, 0.7, 3.1, 3.6, 1.4, "Сетевой модуль\nrcs_client.py", fc=LIGHT, fs=10)
box(ax, 0.7, 1.0, 3.6, 1.2, "SHA-256 (hashlib)", fc=GRAY, fs=10)
arrow(ax, 2.5, 5.3, 2.5, 4.5, "вызовы")
arrow(ax, 2.5, 3.1, 2.5, 2.2, "хэш")

# серверная часть
ax.add_patch(Rectangle((7.2, 0.4), 4.6, 7.2, fill=False, edgecolor="#888", linestyle="--", linewidth=1.2))
ax.text(9.5, 7.25, "Сервер (C)", ha="center", fontsize=12, fontweight="bold", color=ACCENT)
box(ax, 7.6, 5.3, 3.6, 1.4, "Приём соединений\naccept() + pthread", fc=GREEN, fs=10)
box(ax, 7.6, 3.1, 3.6, 1.4, "Авторизация +\nвыполнение команд", fc=LIGHT, fs=10)
box(ax, 7.6, 1.0, 1.7, 1.2, "users.conf", fc=GRAY, fs=9)
box(ax, 9.5, 1.0, 1.7, 1.2, "server.log", fc=GRAY, fs=9)
arrow(ax, 9.4, 5.3, 9.4, 4.5, "поток")
arrow(ax, 8.5, 3.1, 8.5, 2.2, "чтение")
arrow(ax, 10.3, 3.1, 10.3, 2.2, "запись")

# сеть
arrow(ax, 4.3, 4.0, 7.6, 4.0, "TCP / сокеты\n(кадры с длиной)", color=ACCENT, fs=10, off=0.18)
arrow(ax, 7.6, 3.6, 4.3, 3.6, "", color=ACCENT)

plt.tight_layout()
plt.savefig(f"{OUT}/arch.png", dpi=170, bbox_inches="tight", facecolor="white")
plt.close()

# ---------- 2. Диаграмма последовательности ----------
fig, ax = plt.subplots(figsize=(9, 6.2))
ax.set_xlim(0, 12); ax.set_ylim(0, 13); ax.axis("off")
cx, sx = 2.8, 9.2
box(ax, 1.3, 12.0, 3.0, 0.8, "Клиент", fc=GREEN, bold=True)
box(ax, 7.7, 12.0, 3.0, 0.8, "Сервер", fc=LIGHT, bold=True)
ax.plot([cx, cx], [0.5, 12.0], color="#aaa", linewidth=1)
ax.plot([sx, sx], [0.5, 12.0], color="#aaa", linewidth=1)

seq = [
    (11.0, cx, sx, "USER\\n<логин>", False),
    (10.0, sx, cx, "CHALLENGE\\n<соль>\\n<nonce>", True),
    (8.6, cx, cx, "H=SHA256(соль+пароль)\nответ=SHA256(H+nonce)", None),
    (7.6, cx, sx, "RESP\\n<ответ>", False),
    (6.6, sx, sx, "сверка с SHA256(H+nonce)", None),
    (5.8, sx, cx, "OK / ERR", True),
    (4.6, cx, sx, "CMD\\n<команда>", False),
    (3.6, sx, sx, "popen(): выполнение", None),
    (2.8, sx, cx, "OUT\\n<вывод + код>", True),
    (1.6, cx, sx, "QUIT", False),
]
for y, x1, x2, txt, dashed in seq:
    if x1 == x2:  # действие на стороне
        side = -1 if x1 == cx else 1
        bx = x1 + (0.4 if side > 0 else -3.6)
        box(ax, bx, y - 0.35, 3.2, 0.8, txt, fc="#FFF2CC", ec="#BF9000", fs=8.5)
    else:
        arrow(ax, x1, y, x2, y, txt, dashed=dashed, fs=9, off=0.12)

plt.tight_layout()
plt.savefig(f"{OUT}/seq.png", dpi=170, bbox_inches="tight", facecolor="white")
plt.close()

# ---------- 3. Блок-схема сервера ----------
fig, ax = plt.subplots(figsize=(5.2, 8.4))
ax.set_xlim(0, 6); ax.set_ylim(0, 14); ax.axis("off")


def fbox(y, text, fc=LIGHT, h=0.9, w=4.2):
    box(ax, 0.9, y, w, h, text, fc=fc, fs=9.5)


def down(y1, y2, text=""):
    arrow(ax, 3.0, y1, 3.0, y2, text, fs=8.5, off=0.05)


fbox(12.9, "Старт: создать сокет,\nbind(), listen()", fc=GREEN)
down(12.9, 12.2)
fbox(11.3, "accept() — ждать клиента")
down(11.3, 10.6)
fbox(9.7, "Создать поток (pthread)\nдля клиента", fc="#FFF2CC")
arrow(ax, 0.9, 10.1, 0.3, 10.1)
arrow(ax, 0.3, 10.1, 0.3, 11.75)
arrow(ax, 0.3, 11.75, 0.9, 11.75, "след. клиент")
down(9.7, 9.0)
fbox(8.1, "Принять USER,\nотправить CHALLENGE")
down(8.1, 7.4)
fbox(6.5, "Принять RESP,\nсверить хэш")
down(6.5, 5.8)
# ромб решения
ax.add_patch(plt.Polygon([(3.0, 5.7), (4.6, 5.0), (3.0, 4.3), (1.4, 5.0)],
             closed=True, facecolor="#FCE4D6", edgecolor="#C55A11", linewidth=1.3))
ax.text(3.0, 5.0, "Верно?", ha="center", va="center", fontsize=9.5, fontweight="bold")
arrow(ax, 4.6, 5.0, 5.5, 5.0, "нет")
ax.text(5.5, 4.3, "пауза,\nразрыв", ha="center", fontsize=8.5, color="#C00000")
arrow(ax, 5.5, 4.6, 5.5, 0.9)
arrow(ax, 5.5, 0.9, 3.0, 0.9)
down(4.3, 3.7, "да")
fbox(2.8, "Цикл: принять CMD,\npopen(), вернуть OUT")
down(2.8, 2.1)
fbox(1.0, "QUIT / разрыв →\nзакрыть соединение", fc=GRAY, h=0.9)

plt.tight_layout()
plt.savefig(f"{OUT}/flow.png", dpi=170, bbox_inches="tight", facecolor="white")
plt.close()

print("Диаграммы созданы:", os.listdir(OUT))
