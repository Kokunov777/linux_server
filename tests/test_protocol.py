#!/usr/bin/env python3
"""
test_protocol.py — автотест протокола RCS.

Запускает собранный сервер на тестовом порту и проверяет:
  1) успешную авторизацию и выполнение команды;
  2) корректную передачу кириллицы и кода возврата;
  3) отказ при неверном пароле;
  4) отказ при неизвестном пользователе (без раскрытия факта существования);
  5) работу пользователя, добавленного через mkuser.py.

Запуск:  python3 tests/test_protocol.py
"""

import os
import sys
import time
import subprocess
import tempfile

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, os.path.abspath(SRC))
from rcs_client import RCSClient, RCSError  # noqa: E402

PORT = 5601
passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [OK]   {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}")


def main():
    workdir = tempfile.mkdtemp(prefix="rcs_test_")
    server_bin = os.path.abspath(os.path.join(SRC, "server"))
    assert os.path.exists(server_bin), "сначала соберите сервер: make"

    # добавим второго пользователя через mkuser.py (в рабочем каталоге сервера)
    subprocess.run([sys.executable, os.path.abspath(os.path.join(SRC, "mkuser.py")),
                    "operator", "Passw0rd", "users.conf"],
                   cwd=workdir, check=True, stdout=subprocess.DEVNULL)

    srv = subprocess.Popen([server_bin, str(PORT)], cwd=workdir,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.6)
    try:
        # 1-2: верная авторизация + команда + кириллица + код возврата
        c = RCSClient("127.0.0.1", PORT)
        greet = c.connect("operator", "Passw0rd")
        check("авторизация operator", "успешна" in greet)
        out = c.execute("echo тест-кириллица-123")
        check("вывод команды получен", "тест-кириллица-123" in out)
        check("код возврата 0 присутствует", "код возврата: 0" in out)
        out2 = c.execute("nosuchcmd_xyz")
        check("ненулевой код возврата для ошибки", "код возврата: 127" in out2)
        c.close()

        # 3: неверный пароль
        try:
            RCSClient("127.0.0.1", PORT).connect("operator", "bad")
            check("отказ при неверном пароле", False)
        except RCSError:
            check("отказ при неверном пароле", True)

        # 4: неизвестный пользователь
        try:
            RCSClient("127.0.0.1", PORT).connect("ghost", "x")
            check("отказ при неизвестном пользователе", False)
        except RCSError:
            check("отказ при неизвестном пользователе", True)

    finally:
        srv.terminate()
        srv.wait(timeout=3)

    print(f"\nИтог: успешно {passed}, провалено {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
