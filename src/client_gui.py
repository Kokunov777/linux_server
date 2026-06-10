#!/usr/bin/env python3
"""
client_gui.py — Графический клиент для сервера удалённого выполнения команд.

GUI на Tkinter (входит в стандартную поставку Python, доп. зависимостей нет).
Сетевая логика вынесена в модуль rcs_client.RCSClient.

Запуск:  python3 client_gui.py
Зависимости в Linux: пакет python3-tk (sudo apt install python3-tk)
"""

import threading
import queue
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from rcs_client import RCSClient, RCSError


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.client: RCSClient | None = None
        self.history: list[str] = []
        self.hist_idx = 0
        self.q: "queue.Queue[tuple]" = queue.Queue()

        root.title("Удалённое выполнение команд — клиент (РГР)")
        root.geometry("820x560")
        root.minsize(640, 460)

        self._build_connection_bar()
        self._build_output()
        self._build_command_bar()
        self._set_connected(False)

        self.root.after(80, self._drain_queue)

    # ------------- построение интерфейса -------------
    def _build_connection_bar(self):
        f = ttk.LabelFrame(self.root, text="Подключение", padding=8)
        f.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(f, text="Хост:").grid(row=0, column=0, sticky="w")
        self.e_host = ttk.Entry(f, width=14); self.e_host.insert(0, "127.0.0.1")
        self.e_host.grid(row=0, column=1, padx=(2, 10))

        ttk.Label(f, text="Порт:").grid(row=0, column=2, sticky="w")
        self.e_port = ttk.Entry(f, width=7); self.e_port.insert(0, "5555")
        self.e_port.grid(row=0, column=3, padx=(2, 10))

        ttk.Label(f, text="Логин:").grid(row=0, column=4, sticky="w")
        self.e_user = ttk.Entry(f, width=12); self.e_user.insert(0, "admin")
        self.e_user.grid(row=0, column=5, padx=(2, 10))

        ttk.Label(f, text="Пароль:").grid(row=0, column=6, sticky="w")
        self.e_pass = ttk.Entry(f, width=12, show="•")
        self.e_pass.grid(row=0, column=7, padx=(2, 10))
        self.e_pass.bind("<Return>", lambda e: self.on_connect())

        self.btn_conn = ttk.Button(f, text="Подключиться", command=self.on_connect)
        self.btn_conn.grid(row=0, column=8, padx=4)
        self.btn_disc = ttk.Button(f, text="Отключиться", command=self.on_disconnect)
        self.btn_disc.grid(row=0, column=9, padx=4)

    def _build_output(self):
        f = ttk.LabelFrame(self.root, text="Вывод", padding=4)
        f.pack(fill="both", expand=True, padx=8, pady=4)
        self.out = scrolledtext.ScrolledText(f, wrap="word", font=("monospace", 10),
                                             state="disabled", bg="#1e1e1e", fg="#dcdcdc",
                                             insertbackground="#dcdcdc")
        self.out.pack(fill="both", expand=True)
        self.out.tag_config("sys", foreground="#4fc1ff")
        self.out.tag_config("cmd", foreground="#c586c0")
        self.out.tag_config("err", foreground="#f48771")
        self.out.tag_config("ok",  foreground="#89d185")

    def _build_command_bar(self):
        f = ttk.Frame(self.root, padding=(8, 0, 8, 4))
        f.pack(fill="x")
        ttk.Label(f, text="Команда:").pack(side="left")
        self.e_cmd = ttk.Entry(f, font=("monospace", 10))
        self.e_cmd.pack(side="left", fill="x", expand=True, padx=6)
        self.e_cmd.bind("<Return>", lambda e: self.on_send())
        self.e_cmd.bind("<Up>",   self._hist_prev)
        self.e_cmd.bind("<Down>", self._hist_next)
        self.btn_send = ttk.Button(f, text="Выполнить", command=self.on_send)
        self.btn_send.pack(side="left")

        self.status = ttk.Label(self.root, text="Не подключено", anchor="w",
                                relief="sunken", padding=(6, 2))
        self.status.pack(fill="x", side="bottom")

    # ------------- состояние -------------
    def _set_connected(self, connected: bool):
        state_conn = "disabled" if connected else "normal"
        state_work = "normal" if connected else "disabled"
        for w in (self.e_host, self.e_port, self.e_user, self.e_pass, self.btn_conn):
            w.config(state=state_conn)
        for w in (self.e_cmd, self.btn_send, self.btn_disc):
            w.config(state=state_work)
        if connected:
            self.e_cmd.focus_set()

    def _log(self, text: str, tag: str = ""):
        self.out.config(state="normal")
        self.out.insert("end", text + "\n", tag)
        self.out.see("end")
        self.out.config(state="disabled")

    # ------------- обработчики -------------
    def on_connect(self):
        host = self.e_host.get().strip() or "127.0.0.1"
        try:
            port = int(self.e_port.get().strip())
        except ValueError:
            messagebox.showerror("Ошибка", "Порт должен быть числом")
            return
        user = self.e_user.get().strip()
        pwd = self.e_pass.get()
        if not user:
            messagebox.showerror("Ошибка", "Введите логин")
            return

        self.status.config(text=f"Подключение к {host}:{port}…")
        self.client = RCSClient(host, port)

        def worker():
            try:
                greeting = self.client.connect(user, pwd)
                self.q.put(("connected", host, port, user, greeting))
            except (RCSError, OSError) as e:
                self.q.put(("conn_error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_disconnect(self):
        if self.client:
            self.client.close()
            self.client = None
        self._set_connected(False)
        self.status.config(text="Не подключено")
        self._log("— соединение закрыто —", "sys")

    def on_send(self):
        if not self.client:
            return
        cmd = self.e_cmd.get().strip()
        if not cmd:
            return
        self.history.append(cmd)
        self.hist_idx = len(self.history)
        self.e_cmd.delete(0, "end")
        self._log(f"$ {cmd}", "cmd")
        self.btn_send.config(state="disabled")
        self.status.config(text="Выполнение…")

        def worker():
            try:
                out = self.client.execute(cmd)
                self.q.put(("output", out))
            except (RCSError, OSError) as e:
                self.q.put(("exec_error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ------------- история команд -------------
    def _hist_prev(self, _):
        if self.history and self.hist_idx > 0:
            self.hist_idx -= 1
            self.e_cmd.delete(0, "end")
            self.e_cmd.insert(0, self.history[self.hist_idx])
        return "break"

    def _hist_next(self, _):
        if self.history and self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.e_cmd.delete(0, "end")
            self.e_cmd.insert(0, self.history[self.hist_idx])
        else:
            self.hist_idx = len(self.history)
            self.e_cmd.delete(0, "end")
        return "break"

    # ------------- очередь сообщений из потоков -------------
    def _drain_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "connected":
                    _, host, port, user, greeting = msg
                    self._set_connected(True)
                    self.status.config(text=f"Подключено: {user}@{host}:{port}")
                    self._log(f"[+] {greeting}", "ok")
                elif kind == "conn_error":
                    self.client = None
                    self.status.config(text="Ошибка подключения")
                    self._log(f"[!] {msg[1]}", "err")
                    messagebox.showerror("Не удалось подключиться", msg[1])
                elif kind == "output":
                    self._log(msg[1])
                    self.btn_send.config(state="normal")
                    self.status.config(text="Готово")
                    self.e_cmd.focus_set()
                elif kind == "exec_error":
                    self._log(f"[!] {msg[1]}", "err")
                    self.btn_send.config(state="normal")
                    self.status.config(text="Ошибка выполнения")
        except queue.Empty:
            pass
        self.root.after(80, self._drain_queue)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
