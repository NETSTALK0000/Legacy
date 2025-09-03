# ©️ Dan Gazizullin, 2021-2023
# This file is a part of Hikka Userbot
# 🌐 https://github.com/hikariatama/Hikka
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import contextlib
import itertools
import os
import subprocess
import sys
import tempfile
import typing
from types import ModuleType
from io import StringIO

import legacytl
from legacytl.errors.rpcerrorlist import MessageIdInvalidError
from legacytl.sessions import StringSession
from legacytl.tl.types import Message
from legacytl.tl.types.messages import AffectedMessages
from meval import meval

from .. import loader, utils
from ..log import LegacyException


@loader.tds
class Evaluator(loader.Module):
    strings = {"name": "Evaluator"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "hide_telethon_results",
                False,
                lambda: "Suppress the output of Telethon API method return values (e.g., Message, AffectedMessages) in the result",
                validator=loader.validators.Boolean(),
            )
        )

    @loader.command(alias="eval")
    async def e(self, message: Message):
        try:
            output_buffer = StringIO()

            with contextlib.redirect_stdout(output_buffer):
                result = await meval(
                    utils.get_args_raw(message),
                    globals(),
                    **await self.getattrs(message),
                )

            printed_output = output_buffer.getvalue()
        except Exception:
            item = LegacyException.from_exc_info(*sys.exc_info())

            await utils.answer(
                message,
                self.strings("err").format(
                    "4985626654563894116",
                    "python",
                    utils.escape_html(utils.get_args_raw(message)),
                    "error",
                    self.censor(
                        (
                            "\n".join(item.full_stack.splitlines()[:-1])
                            + "\n\n"
                            + "🚫 "
                            + item.full_stack.splitlines()[-1]
                        )
                    ),
                ),
            )

            return

        def contains_message(obj):
            if isinstance(obj, (Message, AffectedMessages)):
                return True
            if isinstance(obj, (list, tuple, set)):
                return any(contains_message(i) for i in obj)
            if isinstance(obj, dict):
                return any(
                    contains_message(k) or contains_message(v) for k, v in obj.items()
                )
            return False

        if self.config["hide_telethon_results"] and contains_message(result):
            result = None

        if callable(getattr(result, "stringify", None)):
            with contextlib.suppress(Exception):
                result = str(result.stringify())

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings["eval"].format(
                    "4985626654563894116",
                    "python",
                    utils.escape_html(utils.get_args_raw(message)),
                )
                + (
                    self.strings["result"].format(
                        "python", f"{utils.escape_html(self.censor(str(result)))}"
                    )
                    if result
                    else ""
                )
                + (
                    self.strings["output"].format(
                        "python", utils.escape_html(self.censor(printed_output))
                    )
                    if printed_output
                    else ""
                ),
            )

    @loader.command()
    async def ecpp(self, message: Message, c: bool = False):
        try:
            subprocess.check_output(
                ["gcc" if c else "g++", "--version"],
                stderr=subprocess.STDOUT,
            )
        except Exception:
            await utils.answer(
                message,
                self.strings("no_compiler").format(
                    "4986046904228905931" if c else "4985844035743646190",
                    "C (gcc)" if c else "C++ (g++)",
                ),
            )
            return

        code = utils.get_args_raw(message)
        message = await utils.answer(message, self.strings("compiling"))
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.cpp")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["gcc" if c else "g++", "-o", "code", "code.cpp"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True

            if not result:
                try:
                    result = subprocess.check_output(
                        ["./code"],
                        cwd=tmpdir,
                        stderr=subprocess.STDOUT,
                    ).decode()
                except subprocess.CalledProcessError as e:
                    result = e.output.decode()
                    error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings("err" if error else "eval").format(
                    "4986046904228905931" if c else "4985844035743646190",
                    "c" if c else "cpp",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    @loader.command()
    async def ec(self, message: Message):
        await self.ecpp(message, c=True)

    @loader.command()
    async def enode(self, message: Message):
        try:
            subprocess.check_output(
                ["node", "--version"],
                stderr=subprocess.STDOUT,
            )
        except Exception:
            await utils.answer(
                message,
                self.strings("no_compiler").format(
                    "4985643941807260310",
                    "Node.js",
                ),
            )
            return

        code = utils.get_args_raw(message)
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.js")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["node", "code.js"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings("err" if error else "eval").format(
                    "4985643941807260310",
                    "javascript",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    @loader.command()
    async def ephp(self, message: Message):
        try:
            subprocess.check_output(
                ["php", "--version"],
                stderr=subprocess.STDOUT,
            )
        except Exception:
            await utils.answer(
                message,
                self.strings("no_compiler").format(
                    "4985815079074136919",
                    "PHP",
                ),
            )
            return

        code = utils.get_args_raw(message)
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.php")
            with open(file, "w") as f:
                f.write(f"<?php {code} ?>")

            try:
                result = subprocess.check_output(
                    ["php", "code.php"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings("err" if error else "eval").format(
                    "4985815079074136919",
                    "php",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    @loader.command()
    async def eruby(self, message: Message):
        try:
            subprocess.check_output(
                ["ruby", "--version"],
                stderr=subprocess.STDOUT,
            )
        except Exception:
            await utils.answer(
                message,
                self.strings("no_compiler").format(
                    "4985760855112024628",
                    "Ruby",
                ),
            )
            return

        code = utils.get_args_raw(message)
        error = False
        with tempfile.TemporaryDirectory() as tmpdir:
            file = os.path.join(tmpdir, "code.rb")
            with open(file, "w") as f:
                f.write(code)

            try:
                result = subprocess.check_output(
                    ["ruby", "code.rb"],
                    cwd=tmpdir,
                    stderr=subprocess.STDOUT,
                ).decode()
            except subprocess.CalledProcessError as e:
                result = e.output.decode()
                error = True

        with contextlib.suppress(MessageIdInvalidError):
            await utils.answer(
                message,
                self.strings("err" if error else "eval").format(
                    "4985760855112024628",
                    "ruby",
                    utils.escape_html(code),
                    "error" if error else "output",
                    utils.escape_html(result),
                ),
            )

    def censor(self, ret: str) -> str:
        ret = ret.replace(str(self._client.legacy_me.phone), "&lt;phone&gt;")

        if btoken := self._db.get("legacy.inline", "bot_token", False):
            ret = ret.replace(
                btoken,
                f"{btoken.split(':')[0]}:{'*' * 26}",
            )

        if htoken := self.lookup("loader").get("token", False):
            ret = ret.replace(htoken, f"eugeo_{'*' * 26}")

        ret = ret.replace(
            StringSession.save(self._client.session),
            "StringSession(**************************)",
        )

        return ret

    async def getattrs(self, message: Message) -> dict:
        reply = await message.get_reply_message()
        me = await self._client.get_me()
        return {
            "message": message,
            "client": self._client,
            "reply": reply,
            "r": reply,
            "event": message,
            "chat": message.to_id,
            "me": me,
            "legacytl": legacytl,
            "herokutl": legacytl,
            "telethon": legacytl,
            "hikkatl": legacytl,
            "utils": utils,
            "loader": loader,
            "f": legacytl.tl.functions,
            "c": self._client,
            "m": message,
            "lookup": self.lookup,
            "self": self,
            "db": self.db,
            "os": os,
            "sys": sys,
            "subprocess": subprocess,
        }

    def get_sub(self, obj: typing.Any, _depth: int = 1) -> dict:
        """Get all callable capitalised objects in an object recursively, ignoring _*"""
        return {
            **dict(
                filter(
                    lambda x: x[0][0] != "_"
                    and x[0][0].upper() == x[0][0]
                    and callable(x[1]),
                    obj.__dict__.items(),
                )
            ),
            **dict(
                itertools.chain.from_iterable(
                    [
                        self.get_sub(y[1], _depth + 1).items()
                        for y in filter(
                            lambda x: x[0][0] != "_"
                            and isinstance(x[1], ModuleType)
                            and x[1] != obj
                            and x[1].__package__.rsplit(".", _depth)[0]
                            == "legacytl.tl",
                            obj.__dict__.items(),
                        )
                    ]
                )
            ),
        }
