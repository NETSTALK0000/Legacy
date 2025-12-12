"""Entry point. Checks for user and starts main script"""

# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import getpass
import os
import subprocess
import sys
import time


def deps():
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "-q",
            "--disable-pip-version-check",
            "--no-warn-script-location",
            "-r",
            "requirements.txt",
        ],
        check=True,
    )


def start():
    from . import log, main
    from ._internal import restart

    if (
        getpass.getuser() == "root"
        and "--root" not in " ".join(sys.argv)
        and all(trigger not in os.environ for trigger in {"DOCKER", "GOORM", "NO_SUDO"})
    ):
        print("🚫" * 15)
        print("Вы попытались запустить Legacy от имени пользователя root")
        print("Пожалуйста, создайте нового пользователя и перезапустите скрипт")
        print("Если это действие было преднамеренным, передайте аргумент --root вместо этого")
        print("🚫" * 15)
        print()
        print("Введите force_insecure, чтобы проигнорировать это предупреждение")
        print("Введите no_sudo, если в вашей системе нет sudo (привет, Debian)")
        inp = input("> ").lower()
        if inp != "force_insecure":
            sys.exit(1)
        elif inp == "no_sudo":
            os.environ["NO_SUDO"] = "1"
            print("Добавлена переменная NO_SUDO в ваши переменные окружения")
            restart()

    if sys.version_info < (3, 8, 0):
        print("🚫 Ошибка: вы должны использовать как минимум Python версии 3.8.0")
        sys.exit(1)

    if __package__ != "legacy":
        print(
            "🚫 Ошибка: вы не можете запустить это как скрипт; вы должны выполнить это как пакет"
        )
        sys.exit(1)

    try:
        import legacytl

        if tuple(map(int, legacytl.__version__.split("."))) < (1, 7, 5):
            raise ImportError
    except Exception:
        deps()
        restart()

    log.init()

    os.environ.pop("HIKKA_DO_NOT_RESTART", None)
    os.environ.pop("HIKKA_DO_NOT_RESTART2", None)

    main.legacy.main()


try:
    start()
except ImportError as e:
    print("📦 Пытаюсь установить недостающие зависимости из requirements.txt...")
    try:
        deps()
    except subprocess.CalledProcessError as deps_err:
        print("❌ Не удалось установить зависимости")
        raise deps_err

    start()
except Exception as e2:
    print("❌ Не удалось запустить Legacy")
    print(e2)

    if "DOCKER" in os.environ:
        time.sleep(9999)

    sys.exit(1)
