#!/usr/bin/env python3
"""
mkuser.py — добавление пользователя в users.conf.

Генерирует случайную соль и хэш H = SHA256(соль + пароль) — в точности по
той же схеме, что и сервер. Пароль в открытом виде нигде не сохраняется.

Использование:
    python3 mkuser.py <логин> <пароль> [файл]
Пример:
    python3 mkuser.py operator S3cret!  users.conf
"""

import sys
import os
import hashlib


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    user = sys.argv[1]
    password = sys.argv[2]
    path = sys.argv[3] if len(sys.argv) > 3 else "users.conf"

    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    line = f"{user}:{salt}:{h}\n"

    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

    print(f"[+] Пользователь '{user}' добавлен в {path}")
    print(f"    соль: {salt}")
    print(f"    хэш:  {h}")


if __name__ == "__main__":
    main()
