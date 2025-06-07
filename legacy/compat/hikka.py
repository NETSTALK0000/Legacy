# ©️ Undefined & XDesai, 2025
# This file is a part of Legacy Userbot
# 🌐 https://github.com/Crayz310/Legacy
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

# ©️ Based on Dan Gazizullin's work
# 🌐 https://github.com/hikariatama/Hikka

import re

def compat(code: str) -> str:
    """
    Reformats modules, built for Hikka to work with Legacy
    :param code: code to reformat
    :return: reformatted code
    :rtype: str
    """

    return "\n".join(
        [
            re.sub(
                r"\butils\.get_platform_name\b",
                "utils.get_named_platform",
                line,
                flags=re.M,
            )
            for line in code.splitlines()
        ]
    )