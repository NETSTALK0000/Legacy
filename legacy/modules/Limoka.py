# meta developer: @limokanews
# requires: whoosh cryptography

# Limoka search module.

#         This module loads a remote `modules.json`, builds a Whoosh index and
#         exposes inline and chat commands to search and display module
#         information. It handles remote banner validation and falls back to an
#         external PNG hosted in the repository when a module banner is missing.
#         The fallback is provided as a URL (`self._fallback_banner_url`). Depending
#         on the client library the `photo` parameter may accept a URL, a file
#         path or a file-like object; this implementation prefers using the
#         external URL for the fallback.

#         Note: Expected `modules.json` record format:

#         {
#             "path/to/module.py": {
#                 "name": "ModuleName",
#                 "description": "Short description",
#                 "meta": {"banner": "https://.../image.png", "developer": "@dev"},
#                 "commands": [{"cmd1": "desc1"}, {"cmd2": "desc2"}],
#                 "category": ["fun", "tools"]
#             }
#         }
# Whoosh index in `userbotFolder/limoka_search/index`.


from whoosh.index import create_in, open_dir
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser, OrGroup
from whoosh.query import FuzzyTerm, Wildcard

import aiohttp
import random
import logging
import os
import html
import json

import re

import asyncio

from typing import Union, List, Dict, Any, Optional
import hashlib

from telethon.types import Message
from telethon.errors.rpcerrorlist import WebpageMediaEmptyError

try:
    from aiogram.utils.exceptions import BadRequest
except ImportError:
    from aiogram.exceptions import TelegramBadRequest as BadRequest

from .. import utils, loader
from ..types import InlineCall

logger = logging.getLogger("Limoka")

__version__ = (1, 3, 0)


class Search:
    def __init__(self, query, ix):
        self.schema = Schema(
            title=TEXT(stored=True), path=ID(stored=True), content=TEXT(stored=True)
        )
        self.query = query
        self.ix = ix

    def search_module(self):
        with self.ix.searcher() as searcher:
            parser = QueryParser("content", self.ix.schema, group=OrGroup.factory(0.8))
            query = parser.parse(self.query)
            wildcard_query = Wildcard("content", f"*{self.query}*")
            fuzzy_query = FuzzyTerm("content", self.query, maxdist=2, prefixlength=1)

            for search_query in [query, wildcard_query, fuzzy_query]:
                results = searcher.search(search_query)
                if results:
                    return list(set(result["path"] for result in results))
            return []


class LimokaAPI:
    async def get_all_modules(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return json.loads(await response.text())


@loader.tds
class Limoka(loader.Module):
    """Modules are now in one place with easy searching!"""

    strings = {
        "name": "Limoka",
        "wait": (
            "Just wait\n"
            "<emoji document_id=5404630946563515782>🔍</emoji> A search is underway among {count} modules "
            "for the query: <code>{query}</code>\n\n<i>{fact}</i>"
        ),
        "found": (
            "<emoji document_id=5413334818047940135>🔍</emoji> Found module <b>{name}</b> "
            "by query: <b>{query}</b>\n\n"
            "<b><emoji document_id=5418376169055602355>ℹ️</emoji> Description:</b> {description}\n"
            "<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Developer:</b> {username}\n\n"
            "{commands}\n"
            "<emoji document_id=5411143117711624172>🪄</emoji> <code>{prefix}dlm {url}{module_path}</code>"
        ),
        "caption_short": (
            "<emoji document_id=5413334818047940135>🔍</emoji> <b>{safe_name}</b>\n"
            "<b><emoji document_id=5418376169055602355>ℹ️</emoji> Description:</b> {safe_desc}\n"
            "<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Dev:</b> {dev_username}\n\n"
            "<emoji document_id=5411143117711624172>🪄</emoji> <code>{prefix}dlm {module_path}</code>"
        ),
        "command_template": "{emoji} <code>{prefix}{command}</code> — {description}\n",
        "emojis": {
            1: "<emoji document_id=5416037945909987712>1️⃣</emoji>",
            2: "<emoji document_id=5413855071731470617>2️⃣</emoji>",
            3: "<emoji document_id=5416068826724850291>3️⃣</emoji>",
            4: "<emoji document_id=5415843998071803071>4️⃣</emoji>",
            5: "<emoji document_id=5415684843763686989>5️⃣</emoji>",
            6: "<emoji document_id=5415975458430796879>6️⃣</emoji>",
            7: "<emoji document_id=5415769763857060166>7️⃣</emoji>",
            8: "<emoji document_id=5416006506749383505>8️⃣</emoji>",
            9: "<emoji document_id=5415963015910544694>9️⃣</emoji>",
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> <b>Not found by query: <i>{query}</i></b>",
        "noargs": "<emoji document_id=5210952531676504517>❌</emoji> <b>No args</b>",
        "?": "<emoji document_id=5951895176908640647>🔎</emoji> Request too short / not found",
        "no_info": "No information",
        "facts": [
            "<emoji document_id=5472193350520021357>🛡</emoji> The limoka catalog is carefully moderated!",
            "<emoji document_id=5940434198413184876>🚀</emoji> Limoka performance allows you to search for modules quickly!",
        ],
        "inline404": "Not found",
        "inline?": "Request too short / not found",
        "inlinenoargs": "Please, enter query",
        "history": (
            "<emoji document_id=5879939498149679716>🔎</emoji> <b>Your search history:</b>\n"
            "{history}"
        ),
        "filter_menu": "Choose filters",
        "filter_cat": "📑 Filter by Category",
        "apply_filters": "✅ Apply Filters",
        "clear_filters": "🗑 Clear Filters",
        "back_to_results": "🔙 Back to Results",
        "empty_history": "<emoji document_id=5879939498149679716>🔎</emoji> <b>Your search history is empty!</b>",
        "enter_query": "🔍 Enter new search query:",
        "global_search": "<emoji document_id=5413334818047940135>🔍</emoji> Global search for <b>{query}</b> — found <b>{count}</b> modules",
        "change_query": "🔍 Change query",
        "no_modules": "No modules available.",
        "filter_title": "🏷 Filters",
        "category_title": "📂 Categories",
        "selected_categories": "✅ Selected categories: {categories}",
        "no_categories": "No categories found in the module database",
        "select_category": "Select categories for query: <code>{query}</code>\n(You can select multiple)",
        "back": "🔙 Back",
        "category": "📁 {category}",
        "no_category": "No category",
        "global_button": "🌍 Results",
        "filtered_button": "🏷️ Filtered search",
        "inline_search": "🔍 Search in Limoka",
        "inline_no_results": "❌ No modules found",
        "inline_error": "❌ Search error occurred",
        "inline_short_query": "❌ Query too short (min 2 chars)",
        "inline_switch_pm": "💬 Open in chat",
        "inline_switch_pm_text": "🔍 Results for: {query}",
        "inline_start_message": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Search</b>\n\nType module name or keyword",
        "first_page": "This is the first page!",
        "last_page": "This is the last page!",
        "display_error": "Error displaying module. Please try again.",
        "error_occurred": "An error occurred. Please try again.",
        "start_search_form": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Search</b>\n\nEnter your query to search for modules:",
        "global_search_form": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Global Search</b>\n\nEnter your query to search ALL modules without filters:",
        "history_cleared": "<emoji document_id=5427009710268689068>🧹</emoji> <b>Search history cleared!</b>",
        "invalid_history_arg": "<emoji document_id=5210952531676504517>❌</emoji> <b>Invalid argument for history command. Use:</b>\n<code>.lshistory</code> - show history\n<code>.lshistory clear</code> - clear history",
        "close": "❌ Close",
        "watcher_no_tag": "❌ Invalid message format. No #limoka tag found.",
        "watcher_invalid_format": "❌ Invalid format. Expected: #limoka:path:signature",
        "watcher_signature_invalid": "❌ Signature invalid! Installation aborted.",
        "watcher_loader_missing": "❌ Loader module not found.",
        "watcher_module_not_found": "❌ Module not found in Limoka database: <code>{path}</code>",
        "watcher_critical": "❌ Critical error: {error}",
    }

    strings_ru = {
        "name": "Limoka",
        "wait": (
            "Подождите\n"
            "<emoji document_id=5404630946563515782>🔍</emoji> Идёт поиск среди {count} модулей по запросу: <code>{query}</code>\n\n"
            "<i>{fact}</i>"
        ),
        "found": (
            "<emoji document_id=5413334818047940135>🔍</emoji> Найден модуль <b>{name}</b> "
            "по запросу: <b>{query}</b>\n\n"
            "<b><emoji document_id=5418376169055602355>ℹ️</emoji> Описание:</b> {description}\n"
            "<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Разработчик:</b> {username}\n\n"
            "{commands}\n"
            "<emoji document_id=5411143117711624172>🪄</emoji> <code>{prefix}dlm {url}{module_path}</code>"
        ),
        "caption_short": (
            "<emoji document_id=5413334818047940135>🔍</emoji> <b>{safe_name}</b>\n"
            "<b><emoji document_id=5418376169055602355>ℹ️</emoji> Описание:</b> {safe_desc}\n"
            "<b><emoji document_id=5418299289141004396>🧑‍💻</emoji> Разработчик:</b> {dev_username}\n\n"
            "<emoji document_id=5411143117711624172>🪄</emoji> <code>{prefix}dlm {module_path}</code>"
        ),
        "command_template": "{emoji} <code>{prefix}{command}</code> — {description}\n",
        "emojis": {
            1: "<emoji document_id=5416037945909987712>1️⃣</emoji>",
            2: "<emoji document_id=5413855071731470617>2️⃣</emoji>",
            3: "<emoji document_id=5416068826724850291>3️⃣</emoji>",
            4: "<emoji document_id=5415843998071803071>4️⃣</emoji>",
            5: "<emoji document_id=5415684843763686989>5️⃣</emoji>",
            6: "<emoji document_id=5415975458430796879>6️⃣</emoji>",
            7: "<emoji document_id=5415769763857060166>7️⃣</emoji>",
            8: "<emoji document_id=5416006506749383505>8️⃣</emoji>",
            9: "<emoji document_id=5415963015910544694>9️⃣</emoji>",
        },
        "404": "<emoji document_id=5210952531676504517>❌</emoji> <b>Не найдено по запросу: <i>{query}</i></b>",
        "noargs": "<emoji document_id=5210952531676504517>❌</emoji> <b>Нет аргументов</b>",
        "?": "<emoji document_id=5951895176908640647>🔎</emoji> Запрос слишком короткий / не найден",
        "no_info": "Нет информации",
        "facts": [
            "<emoji document_id=5472193350520021357>🛡</emoji> Каталог Limoka тщательно модерируется!",
            "<emoji document_id=5940434198413184876>🚀</emoji> Limoka позволяет искать модули с невероятной скоростью!",
            (
                "<emoji document_id=5188311512791393083>🔎</emoji> Limoka имеет лучший поиск*!"
                "\n <i>* В сравнении с предыдущей версией Limoka</i>"
            ),
        ],
        "inline404": "Не найдено",
        "inline?": "Запрос слишком короткий / не найден",
        "inlinenoargs": "Введите запрос",
        "history": (
            "<emoji document_id=5879939498149679716>🔎</emoji> <b>История поиска:</b>\n"
            "{history}"
        ),
        "filter_menu": "Выберите фильтры",
        "filter_cat": "📑 Фильтр по категориям",
        "apply_filters": "✅ Применить фильтры",
        "clear_filters": "🗑 Очистить фильтры",
        "back_to_results": "🔙 Вернуться к результатам",
        "empty_history": "<emoji document_id=5879939498149679716>🔎</emoji> <b>История поиска пуста!</b>",
        "enter_query": "🔍 Введите новый поисковый запрос:",
        "global_search": "<emoji document_id=5413334818047940135>🔍</emoji> Глобальный поиск по <b>{query}</b> — найдено <b>{count}</b> модулей",
        "change_query": "🔍 Изменить запрос",
        "no_modules": "Модули недоступны.",
        "filter_title": "🏷 Фильтры",
        "category_title": "📂 Категории",
        "selected_categories": "✅ Выбранные категории: {categories}",
        "no_categories": "Категории не найдены в базе модулей",
        "select_category": "Выберите категории для запроса: <code>{query}</code>\n(Можно выбрать несколько)",
        "back": "🔙 Назад",
        "category": "📁 {category}",
        "no_category": "Без категории",
        "global_button": "🌍 Результаты",
        "filtered_button": "🏷️ Поиск с фильтрами",
        "inline_search": "🔍 Поиск в Limoka",
        "inline_no_results": "❌ Модули не найдены",
        "inline_error": "❌ Ошибка поиска",
        "inline_short_query": "❌ Запрос слишком короткий (мин. 2 символа)",
        "inline_switch_pm": "💬 Открыть в чате",
        "inline_switch_pm_text": "🔍 Результаты для: {query}",
        "inline_start_message": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Поиск</b>\n\nВведите название модуля или ключевое слово",
        "first_page": "Это первая страница!",
        "last_page": "Это последняя страница!",
        "display_error": "Ошибка отображения модуля. Пожалуйста, попробуйте еще раз.",
        "error_occurred": "Произошла ошибка. Пожалуйста, попробуйте еще раз.",
        "start_search_form": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Limoka Поиск</b>\n\nВведите ваш запрос для поиска модулей:",
        "global_search_form": "<emoji document_id=5413334818047940135>🔍</emoji> <b>Глобальный Поиск</b>\n\nВведите запрос для поиска ВСЕХ модулей без фильтров:",
        "history_cleared": "<emoji document_id=5427009710268689068>🧹</emoji> <b>История поиска очищена!</b>",
        "invalid_history_arg": "<emoji document_id=5210952531676504517>❌</emoji> <b>Неверный аргумент для команды истории. Используйте:</b>\n<code>.lshistory</code> - показать историю\n<code>.lshistory clear</code> - очистить историю",
        "close": "❌ Закрыть",
        "watcher_no_tag": "❌ Неверный формат сообщения. Тег #limoka не найден.",
        "watcher_invalid_format": "❌ Неверный формат. Ожидается: #limoka:path:signature",
        "watcher_signature_invalid": "❌ Неверная подпись! Установка отменена.",
        "watcher_loader_missing": "❌ Модуль загрузчика не найден.",
        "watcher_module_not_found": "❌ Модуль не найден в базе Limoka: <code>{path}</code>",
        "watcher_critical": "❌ Критическая ошибка: {error}",
        "_cls_doc": "Модули теперь в одном месте с простым и удобным поиском!",
    }

    def __init__(self):
        self.api = LimokaAPI()
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "limokaurl",
                "https://raw.githubusercontent.com/MuRuLOSE/limoka/refs/heads/main/",
                lambda: "Mirror (doesn't work): https://raw.githubusercontent.com/MuRuLOSE/limoka-mirror/refs/heads/main/",
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "external_install_allowed",
                True,
                lambda: "If enabled, module installation can be handled via external Limoka bot (@limoka_bbot) for better reliability.",
                validator=loader.validators.Boolean(),
            ),
        )
        self.name = self.strings["name"]
        self._invalid_banners = set()
        # Also keep a convenient external fallback URL for plain search display
        # (used when no valid banner is available and no filters are applied).
        self._fallback_banner_url = "https://raw.githubusercontent.com/MuRuLOSE/limoka/refs/heads/main/assets/limoka404.png"

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.api = LimokaAPI()
        self.schema = Schema(
            title=TEXT(stored=True), path=ID(stored=True), content=TEXT(stored=True)
        )

        os.makedirs("limoka_search", exist_ok=True)
        if not os.path.exists("limoka_search/index"):
            self.ix = create_in("limoka_search", self.schema)
        else:
            self.ix = open_dir("limoka_search")

        self._history = self.pointer("history", [])

        data = await self.api.get_all_modules(self.config["limokaurl"] + "modules.json")
        self.modules = data.get("modules", {}) if isinstance(data, dict) else {}
        await self._update_index()

    async def _update_index(self):
        writer = self.ix.writer()
        for module_path, module_data in self.modules.items():
            writer.add_document(
                title=module_data["name"],
                path=module_path,
                content=module_data["name"] + " " + (module_data["description"] or ""),
            )
            for func in module_data["commands"]:
                for command, description in func.items():
                    writer.add_document(
                        title=module_data["name"],
                        path=module_path,
                        content=f"{command} {description}",
                    )
        writer.commit()

    async def _validate_url(self, url: str) -> Optional[str]:
        """Validate a remote URL points to an image.

        Args:
            url: Remote URL to validate.

        Returns:
            The same URL if it points to an image and is reachable, otherwise
            ``None``.

        Side effects:
            Adds invalid URLs to ``self._invalid_banners`` to avoid repeated
            checks.
        """
        # Return the url if valid, otherwise None. Do not return or use
        # a global fallback here; fallback handling is done by the caller
        # based on display context.
        if not url or url in self._invalid_banners:
            return None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=5) as response:
                    if response.status != 200:
                        self._invalid_banners.add(url)
                        return None
                    content_type = response.headers.get("Content-Type", "").lower()
                    if not content_type.startswith("image/"):
                        self._invalid_banners.add(url)
                        return None
                    return url
        except (aiohttp.ClientError, asyncio.TimeoutError):
            if url:
                self._invalid_banners.add(url)
            return None

    def generate_commands(self, module_info):
        commands = []
        for i, func in enumerate(module_info["commands"], 1):
            if i > 9:
                commands.append("…\n")
                break
            for command, description in func.items():
                emoji = self.strings["emojis"].get(i, "")
                desc = description or self.strings["no_info"]
                if len(desc) > 150:
                    desc = desc[:147] + "…"
                commands.append(
                    self.strings["command_template"].format(
                        prefix=self.get_prefix(),
                        command=html.escape(command.replace("cmd", "")),
                        emoji=emoji,
                        description=html.escape(desc),
                    )
                )
        return commands[:5]

    def _format_module_content(
        self,
        module_info: Dict[str, Any],
        query: str,
        filters: Dict[str, List[str]],
        include_categories: bool = True,
        module_path: Optional[str] = None,
    ) -> tuple:
        """Formats the module content for display."""
        name = html.escape(module_info.get("name") or self.strings["no_info"])
        description = html.escape(
            module_info.get("description") or self.strings["no_info"]
        )
        dev_username = html.escape(str((module_info.get("meta") or {}).get("developer") or "Unknown"))

        # Prefer explicit module_path argument (caller provides the key),
        # otherwise fall back to module_info['path'] if present.
        raw_path = (
            module_path if module_path is not None else module_info.get("path", "")
        )
        clean_module_path = (raw_path or "").replace("\\", "/")
        commands = self.generate_commands(module_info)

        categories_text = ""
        if include_categories:
            categories = filters.get("category", [])
            if categories:
                categories_text = "\n\n" + self.strings["selected_categories"].format(
                    categories=", ".join(html.escape(c) for c in categories)
                )

        if len(description) > 300:
            description = description[:297] + "…"

        core_message = self.strings["found"].format(
            query=html.escape(query),
            name=name,
            description=description,
            url=html.escape(self.config["limokaurl"]),
            username=dev_username,
            commands="".join(commands),
            prefix=html.escape(self.get_prefix()),
            module_path=html.escape(clean_module_path),
        )

        full_message = core_message[:4096] + categories_text[:100]

        caption_message = full_message
        if len(caption_message) > 1024:
            safe_name = name[:40] + ("..." if len(name) > 40 else "")
            safe_desc = description[:100] + ("…" if len(description) > 100 else "")

            caption_message = self.strings["caption_short"].format(
                safe_name=safe_name,
                safe_desc=safe_desc,
                dev_username=dev_username,
                prefix=self.get_prefix(),
                module_path=html.escape(self.config["limokaurl"] + clean_module_path),
            )[:1024]

            if categories_text:
                remaining_space = 1024 - len(caption_message)
                if remaining_space > 0:
                    caption_message += categories_text[:remaining_space]

        return caption_message, full_message

    def _build_navigation_markup(
        self, result: List[str], index: int, query: str, filters: Dict[str, List[str]]
    ) -> list:
        """Create navigation markup for inline results."""
        page = index + 1
        markup = [
            [
                {
                    "text": "⏪" if index > 0 else "🚫",
                    "callback": self._previous_page if index > 0 else self._inline_void,
                    "args": (result, index, query, filters) if index > 0 else (),
                },
                {"text": f"{page}/{len(result)}", "callback": self._inline_void},
                {
                    "text": "⏩" if index + 1 < len(result) else "🚫",
                    "callback": (
                        self._next_page
                        if index + 1 < len(result)
                        else self._inline_void
                    ),
                    "args": (
                        (result, index, query, filters)
                        if index + 1 < len(result)
                        else ()
                    ),
                },
            ],
            [
                {
                    "text": "🔍 " + self.strings["filter_menu"].split(":")[0],
                    "callback": self._display_filter_menu,
                    "args": (query, filters),
                },
                {
                    "text": "🔄 " + self.strings["change_query"],
                    "callback": self._enter_query,
                },
            ],
            [
                {
                    "text": self.strings["global_button"],
                    "callback": self._show_global_results,
                    "args": (query,),
                },
            ],
        ]
        # Add a universal close button to the navigation markup
        markup.append(
            [{"text": self.strings.get("close", "❌ Close"), "action": "close"}]
        )
        return markup

    async def _safe_display(
        self,
        message_or_call: Union[Message, InlineCall],
        text: str,
        markup: list,
        photo: Optional[Any] = None,
    ):
        """Safely display module information, handling potential errors."""
        try:
            if message_or_call is None:
                logger.error("message_or_call is None in _safe_display")
                return

            if isinstance(message_or_call, Message):
                if photo is not None:
                    # photo can be a URL/str, file path or a file-like object
                    await self.inline.form(
                        text=text,
                        message=message_or_call,
                        reply_markup=markup,
                        photo=photo,
                    )
                else:
                    await self.inline.form(
                        text=text, message=message_or_call, reply_markup=markup
                    )
            else:
                if photo is not None:
                    await message_or_call.edit(
                        text=text, reply_markup=markup, photo=photo
                    )
                else:
                    await message_or_call.edit(text=text, reply_markup=markup)
        except (BadRequest, WebpageMediaEmptyError) as e:
            logger.exception(f"Error in _safe_display: {e}")
            if isinstance(message_or_call, Message):
                await utils.answer(message_or_call, self.strings["display_error"])
            elif hasattr(message_or_call, "edit"):
                await message_or_call.edit(self.strings["display_error"])

    async def _display_module(
        self,
        message_or_call: Union[Message, InlineCall],
        module_info: Dict[str, Any],
        module_path: str,
        query: str,
        result: List[str],
        index: int,
        filters: Dict[str, List[str]],
    ):
        """Display module information with banner and formatted content.

        Args:
            message_or_call: Message or InlineCall object where the module
                will be displayed.
            module_info: Dictionary with module metadata (name, description,
                meta.banner, commands, category).
            module_path: Path key of the module in `self.modules`.
            query: Original search query string.
            result: Full list of matched module paths.
            index: Index of the current module in `result`.
            filters: Active filters (e.g., categories). If ``filters`` is
                empty and no valid remote banner exists, the external fallback
                URL (`self._fallback_banner_url`) will be used.

        Notes:
            The method attempts to validate a remote banner URL via
            :meth:`_validate_url`. If validation succeeds the remote URL is
            passed to the messaging client. If validation fails and ``filters``
            is empty, the external fallback URL (`self._fallback_banner_url`)
            will be used. Behavior may vary depending on the messaging client
            used (Telethon/aiogram/etc.).
        """
        try:
            banner_url = await self._validate_url(module_info["meta"].get("banner"))

            caption_message, full_message = self._format_module_content(
                module_info,
                query,
                filters,
                include_categories=True,
                module_path=module_path,
            )

            markup = self._build_navigation_markup(result, index, query, filters)

            # Determine which banner to use. If banner_url is valid, use it.
            # If no valid banner and no filters are applied (normal search display),
            # create an in-memory BytesIO from the embedded base64 and use it.
            banner_to_use = None
            if banner_url:
                banner_to_use = banner_url
            else:
                if not filters:
                    # Use external fallback URL for plain search display.
                    banner_to_use = getattr(self, "_fallback_banner_url", None)

            display_text = caption_message if banner_to_use else full_message
            await self._safe_display(
                message_or_call, display_text, markup, banner_to_use
            )

        except Exception as e:
            logger.exception(f"Error in _display_module: {e}")
            if isinstance(message_or_call, Message):
                await utils.answer(message_or_call, self.strings["error_occurred"])
            elif hasattr(message_or_call, "edit"):
                await message_or_call.edit(self.strings["error_occurred"])

    async def _display_filter_menu(
        self, call: InlineCall, query: str, current_filters: dict
    ):
        categories = current_filters.get("category", [])
        filters_text = self.strings["selected_categories"].format(
            categories=(
                ", ".join(categories) if categories else self.strings["no_category"]
            )
        )

        markup = [
            [
                {
                    "text": self.strings["filter_cat"],
                    "callback": self._select_category,
                    "args": (query, current_filters),
                },
            ],
            [
                {
                    "text": self.strings["apply_filters"],
                    "callback": self._apply_filters,
                    "args": (query, current_filters),
                },
                {
                    "text": self.strings["clear_filters"],
                    "callback": self._clear_filters,
                    "args": (query,),
                },
            ],
            [
                {
                    "text": self.strings["back_to_results"],
                    "callback": self._show_results,
                    "args": (query, {}, True),
                },
            ],
            [{"text": self.strings.get("close", "❌ Close"), "action": "close"}],
        ]

        text = self.strings["filter_menu"].format(query=query) + f"\n\n{filters_text}"
        await call.edit(text, reply_markup=markup)

    async def _select_category(
        self, call: InlineCall, query: str, current_filters: dict
    ):
        all_categories = set()
        for module_data in self.modules.values():
            all_categories.update(module_data.get("category", ["No category"]))
        categories = sorted(all_categories)

        if not categories:
            await call.edit(
                self.strings["no_categories"],
                reply_markup=[
                    [
                        {
                            "text": self.strings["back"],
                            "callback": self._display_filter_menu,
                            "args": (query, current_filters),
                        }
                    ]
                ],
            )
            return

        selected_categories = current_filters.get("category", [])
        buttons = []
        row = []

        for i, cat in enumerate(categories):
            button_text = (
                self.strings["category"].format(category=cat)
                if "category" in self.strings
                else f"📁 {cat}"
            )
            if cat in selected_categories:
                button_text = "✅ " + button_text

            row.append(
                {
                    "text": button_text,
                    "callback": self._toggle_category,
                    "args": (query, current_filters, cat),
                }
            )

            if (i + 1) % 3 == 0 or i == len(categories) - 1:
                buttons.append(row)
                row = []

        buttons.append(
            [
                {
                    "text": self.strings["back"],
                    "callback": self._display_filter_menu,
                    "args": (query, current_filters),
                }
            ]
        )

        # Add close button to category selector
        buttons.append(
            [{"text": self.strings.get("close", "❌ Close"), "action": "close"}]
        )

        text = self.strings["select_category"].format(query=query)
        await call.edit(text, reply_markup=buttons)

    async def _toggle_category(
        self, call: InlineCall, query: str, current_filters: dict, category: str
    ):
        new_filters = current_filters.copy()
        selected_categories = new_filters.get("category", [])

        if category in selected_categories:
            selected_categories.remove(category)
        else:
            selected_categories.append(category)

        if selected_categories:
            new_filters["category"] = selected_categories
        else:
            new_filters.pop("category", None)

        await self._select_category(call, query, new_filters)

    async def _apply_filters(self, call: InlineCall, query: str, filters: dict):
        await self._show_results(call, query, filters, from_filters=True)

    async def _clear_filters(self, call: InlineCall, query: str):
        await self._show_results(call, query, {}, from_filters=True)

    async def _show_results(
        self, call: InlineCall, query: str, filters: dict, from_filters: bool = False
    ):
        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(self.strings["?"], reply_markup=[])
            return

        if not result:
            markup = (
                [
                    [
                        {
                            "text": self.strings["back"],
                            "callback": self._display_filter_menu,
                            "args": (query, filters),
                        }
                    ]
                ]
                if from_filters
                else []
            )
            # Always provide a close button on empty-result screens
            markup.append(
                [{"text": self.strings.get("close", "❌ Close"), "action": "close"}]
            )
            await call.edit(
                self.strings["404"].format(query=query), reply_markup=markup
            )
            return

        if filters.get("category"):
            filtered_result = [
                path
                for path in result
                if any(
                    cat in self.modules.get(path, {}).get("category", ["No category"])
                    for cat in filters["category"]
                )
            ]
        else:
            filtered_result = result

        if not filtered_result:
            markup = (
                [
                    [
                        {
                            "text": self.strings["back"],
                            "callback": self._display_filter_menu,
                            "args": (query, filters),
                        }
                    ]
                ]
                if from_filters
                else []
            )
            # Add close button when filtered results are empty
            markup.append(
                [{"text": self.strings.get("close", "❌ Close"), "action": "close"}]
            )
            await call.edit(
                self.strings["404"].format(query=query), reply_markup=markup
            )
            return

        module_path = filtered_result[0]
        module_info = self.modules[module_path]
        await self._display_module(
            call, module_info, module_path, query, filtered_result, 0, filters
        )

    async def _enter_query_handler(
        self, call_or_query, query: Optional[str] = None, *args, **kwargs
    ):
        """Handler for inline query input.

        This handler is tolerant to different calling conventions used by the
        framework: some callers provide `(call, query)`, others may provide
        `(query,)` or `(query, call)` depending on context. Normalize the
        inputs so the handler works from menus and forms alike.
        """
        # Normalize parameters: try to find `call` (message or InlineCall)
        call = None
        if query is None and isinstance(call_or_query, str):
            # Called as (query, ...) — search text is first argument
            query = call_or_query
            for a in args:
                if hasattr(a, "edit") or isinstance(a, Message):
                    call = a
                    break
        else:
            # Expected calling convention: (call, query, ...)
            call = call_or_query

        if call is None:
            logger.error("_enter_query_handler: missing call/context")
            return

        if not query:
            await call.edit(
                self.strings["?"],
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": self._enter_query,
                        }
                    ]
                ],
            )
            return

        if len(query) <= 1:
            await call.edit(
                self.strings["?"],
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": self._enter_query,
                        }
                    ]
                ],
            )
            return

        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(
                self.strings["?"],
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": self._enter_query,
                        }
                    ]
                ],
            )
            return

        if not result:
            await call.edit(
                self.strings["404"].format(query=query),
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": self._enter_query,
                        }
                    ],
                    [
                        {
                            "text": self.strings.get("close", "❌ Close"),
                            "action": "close",
                        }
                    ],
                ],
            )
            return

        module_path = result[0]
        module_info = self.modules[module_path]
        await self._display_module(call, module_info, module_path, query, result, 0, {})

    async def _enter_query(self, call: InlineCall, query: Optional[str] = None):
        """Show input form for new query.

        Accepts an optional `query` when called from other menus so the
        "back to results" button can restore the previous search context.
        """
        markup = [
            [
                {
                    "text": "✍️ " + self.strings["enter_query"],
                    "input": self.strings["enter_query"],
                    "handler": self._enter_query_handler,
                }
            ],
            [
                {
                    "text": self.strings["back_to_results"],
                    "callback": self._show_results,
                    "args": (query or "", {}),
                }
            ],
            [
                {
                    "text": self.strings.get("close", "❌ Close"),
                    "action": "close",
                }
            ],
        ]

        await call.edit(self.strings["enter_query"], reply_markup=markup)

    async def _show_global_results(self, call: InlineCall, query: str):
        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(self.strings["?"], reply_markup=[])
            return

        if not result:
            await call.edit(
                self.strings["404"].format(query=query),
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": self._enter_query,
                        }
                    ]
                ],
            )
            return

        text = self.strings["global_search"].format(
            query=html.escape(query), count=len(result)
        )
        buttons = []
        for i, path in enumerate(result[:15]):
            info = self.modules.get(path)
            if not info:
                continue
            name = info.get("name", "Unknown")
            buttons.append(
                [
                    {
                        "text": f"{i + 1}. {name}",
                        "callback": self._display_module_from_global,
                        "args": (path, query, result),
                    }
                ]
            )
        buttons.append(
            [{"text": self.strings["change_query"], "callback": self._enter_query}]
        )

        await call.edit(text=text[:4096], reply_markup=buttons)

    async def _display_module_from_global(
        self, call: InlineCall, module_path: str, query: str, result: list
    ):
        module_info = self.modules[module_path]
        await self._display_module(
            call, module_info, module_path, query, result, result.index(module_path), {}
        )

    async def _next_page(
        self, call: InlineCall, result: list, index: int, query: str, filters: dict
    ):
        if index + 1 >= len(result):
            await call.answer(self.strings["last_page"])
            return

        index += 1
        module_path = result[index]
        module_info = self.modules[module_path]
        await self._display_module(
            call, module_info, module_path, query, result, index, filters
        )

    async def _previous_page(
        self, call: InlineCall, result: list, index: int, query: str, filters: dict
    ):
        if index - 1 < 0:
            await call.answer(self.strings["first_page"])
            return

        index -= 1
        module_path = result[index]
        module_info = self.modules[module_path]
        await self._display_module(
            call, module_info, module_path, query, result, index, filters
        )

    async def _inline_void(self, call: InlineCall):
        await call.answer()

    @loader.command(ru_doc="[запрос / ничего] — Поиск модулей")
    async def limokacmd(self, message: Message):
        """[query / nothing] - Search modules"""
        args = utils.get_args_raw(message)

        if not args:
            markup = [
                [
                    {
                        "text": "✍️ " + self.strings["enter_query"],
                        "input": self.strings["enter_query"],
                        "handler": self._enter_query_handler,
                    }
                ],
                [
                    {
                        "text": self.strings["global_button"],
                        "callback": self._show_global_form,
                        "args": (message,),
                    }
                ],
            ]
            # Close button on the main no-args form
            markup.append(
                [{"text": self.strings.get("close", "❌ Close"), "action": "close"}]
            )

            await self.inline.form(
                text=self.strings["start_search_form"],
                message=message,
                reply_markup=markup,
            )
            return

        history = self.get("history", [])
        if len(history) >= 10:
            history = history[-9:]
        history.append(args)
        self.set("history", history)

        await utils.answer(
            message,
            self.strings["wait"].format(
                count=len(self.modules),
                fact=random.choice(self.strings["facts"]),
                query=args,
            ),
        )

        searcher = Search(args.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            return await utils.answer(message, self.strings["?"])

        if not result:
            return await utils.answer(message, self.strings["404"].format(query=args))

        module_path = result[0]
        module_info = self.modules[module_path]
        await self._display_module(
            message, module_info, module_path, args, result, 0, {}
        )

    async def _show_global_form(self, call: InlineCall, message: Message):
        markup = [
            [
                {
                    "text": "✍️ " + self.strings["enter_query"],
                    "input": self.strings["enter_query"],
                    "handler": self._global_search_handler,
                    "args": (message,),
                }
            ],
            [
                {
                    "text": "🔙 " + self.strings["back"],
                    "callback": self._inline_void,
                }
            ],
            [
                {
                    "text": self.strings.get("close", "❌ Close"),
                    "action": "close",
                }
            ],
        ]

        await call.edit(self.strings["global_search_form"], reply_markup=markup)

    async def _global_search_handler(
        self, call: InlineCall, query: str, message: Message, *args, **kwargs
    ):
        if len(query) <= 1:
            await call.edit(
                self.strings["?"],
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": lambda c: self._show_global_form(c, message),
                        }
                    ],
                    [
                        {
                            "text": self.strings.get("close", "❌ Close"),
                            "action": "close",
                        }
                    ],
                ],
            )
            return

        searcher = Search(query.lower(), self.ix)
        try:
            result = searcher.search_module()
        except Exception:
            await call.edit(
                self.strings["?"],
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": lambda c: self._show_global_form(c, message),
                        }
                    ],
                    [
                        {
                            "text": self.strings.get("close", "❌ Close"),
                            "action": "close",
                        }
                    ],
                ],
            )
            return

        if not result:
            await call.edit(
                self.strings["404"].format(query=query),
                reply_markup=[
                    [
                        {
                            "text": "🔄 " + self.strings["change_query"],
                            "callback": lambda c: self._show_global_form(c, message),
                        }
                    ],
                    [
                        {
                            "text": self.strings.get("close", "❌ Close"),
                            "action": "close",
                        }
                    ],
                ],
            )
            return

        text = self.strings["global_search"].format(
            query=html.escape(query), count=len(result)
        )
        buttons = []
        for i, path in enumerate(result[:15]):
            info = self.modules.get(path)
            if not info:
                continue
            name = info.get("name", "Unknown")
            buttons.append(
                [
                    {
                        "text": f"{i + 1}. {name}",
                        "callback": self._display_module_from_global,
                        "args": (path, query, result),
                    }
                ]
            )
        buttons.append(
            [
                {
                    "text": "🔄 " + self.strings["change_query"],
                    "callback": lambda c: self._show_global_form(c, message),
                }
            ]
        )
        buttons.append(
            [{"text": self.strings.get("close", "❌ Close"), "action": "close"}]
        )

        await call.edit(text=text[:4096], reply_markup=buttons)

    @loader.command(ru_doc="[clear] — Показать или очистить историю поиска")
    async def lshistorycmd(self, message: Message):
        """[clear] - Show or clear search history"""
        args = utils.get_args_raw(message).strip().lower()

        if args == "clear":
            self.set("history", [])
            await utils.answer(message, self.strings["history_cleared"])
            return

        if args:
            await utils.answer(message, self.strings["invalid_history_arg"])
            return

        history = self.get("history", [])

        if not history:
            await utils.answer(message, self.strings["empty_history"])
            return

        formatted_history = [
            f"{i + 1}. <code>{utils.escape_html(h)}</code>"
            for i, h in enumerate(history[-10:])
        ]
        await utils.answer(
            message,
            self.strings["history"].format(history="\n".join(formatted_history)),
        )

    @loader.watcher(from_dl=False)
    async def secure_install_watcher(self, message: Message):
        """Secure install watcher for official Limoka bot.

        This watcher cleans HTML from incoming messages, extracts a
        signed #limoka:<path>:<signature> tag, verifies the signature and
        triggers the loader to download and install the module if valid.
        """
        if not message.text:
            return

        # Verify sender id is present and comes from the official Limoka bot
        if not hasattr(message, "from_id") or not message.from_id:
            return

        sender_id = None
        if hasattr(message.from_id, "user_id"):
            sender_id = message.from_id.user_id
        elif hasattr(message.from_id, "channel_id"):
            sender_id = message.from_id.channel_id

        if sender_id != 8581621390:
            logger.debug("Message not from official bot, ignoring")
            return

        # Only act when external installs are enabled
        if not self.config["external_install_allowed"]:
            return

        try:
            # Prefer raw_text/message when available to preserve original
            # formatting (some clients provide parsed .text that loses
            # tags/links). Fall back to .text if needed.
            clean_text = (
                getattr(message, "raw_text", None)
                or getattr(message, "message", None)
                or message.text
                or ""
            )

            if message.entities:
                from html import unescape

                clean_text = unescape(clean_text)
                # Remove HTML tags but keep their inner text so we don't
                # accidentally remove the tag content when it's wrapped
                # in an <a> or similar.
                clean_text = re.sub(r"<[^>]+>", "", clean_text)

            # Extract the first #limoka:<content> occurrence. Allow for
            # characters until whitespace or HTML/quote delimiters.
            match = re.search(r"#limoka:([^\s\"'<>]+)", clean_text)
            if not match:
                logger.debug(
                    "No #limoka tag found in cleaned text; leaving original message intact"
                )
                # Do not send a user-visible reply for missing tag; simply exit.
                return

            tag_content = match.group(1)

            # Expect format: <path>:<hex_signature>
            parts = tag_content.split(":", 1)
            if len(parts) != 2:
                logger.error("Invalid tag format after cleaning")
                await utils.answer(message, self.strings["watcher_invalid_format"])
                # Do not delete the original message on parse errors.
                return

            module_path, signature_hex = parts

            # Strip leftover quote characters and whitespace
            module_path = re.sub(r"[<>\"']", "", module_path).strip()

            # Handle possible href= artifacts
            if module_path.startswith("href="):
                module_path = module_path[5:].strip('"').strip("'")

            # Try to resolve the module key in database
            if module_path not in self.modules:
                found = False
                for db_path in self.modules.keys():
                    if module_path in db_path or db_path in module_path:
                        module_path = db_path
                        found = True
                        break

                if not found:
                    logger.warning(f"Module not found after cleanup: {module_path}")
                    await utils.answer(
                        message,
                        self.strings["watcher_module_not_found"].format(
                            path=html.escape(module_path)
                        ),
                    )
                    # Keep original message in chat for inspection.
                    return

            # logger.info(f"Module found in database: {module_path}")

            # Verify signature using embedded public key — signature covers
            # the module path AND the SHA256 of the module content (format:
            # "{module_path}|{sha256}"). Download module, compute hash and
            # verify signature against that combined payload.
            try:
                import base64
                from cryptography.hazmat.primitives.asymmetric import ed25519

                PUB_KEY_B64 = (
                    "MCowBQYDK2VwAyEA1ltSnqtf3pGBuctuAYqHivCXsaRtKOVxavai7yin7ZE="
                )
                der_bytes = base64.b64decode(PUB_KEY_B64)
                raw_pubkey = der_bytes[-32:]

                # Download module content to compute SHA256
                module_url = self.config["limokaurl"] + module_path
                async with aiohttp.ClientSession() as session:
                    async with session.get(module_url, timeout=10) as resp:
                        if resp.status != 200:
                            logger.error(
                                f"Failed to fetch module for verification: {module_url} (HTTP {resp.status})"
                            )
                            await utils.answer(
                                message, self.strings["watcher_loader_missing"]
                            )
                            return
                        module_bytes = await resp.read()

                sha256 = hashlib.sha256(module_bytes).hexdigest()

                public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pubkey)
                signature = bytes.fromhex(signature_hex)
                signed_payload = f"{module_path}|{sha256}".encode()
                public_key.verify(signature, signed_payload)
                # logger.info(f"Signature verified for {module_path} (sha256={sha256})")
            except Exception as e:
                logger.error(f"Signature verification failed for {module_path}: {e}")
                await utils.answer(message, self.strings["watcher_signature_invalid"])
                # Keep original message so admins can inspect the signed payload.
                return

            # Perform install via loader
            loader_mod = self.lookup("loader")
            if not loader_mod:
                logger.error("Loader module not found")
                await utils.answer(message, self.strings["watcher_loader_missing"])
                # Do not delete the original message on loader problems.
                return

            module_url = self.config["limokaurl"] + module_path
            # logger.info(f"Installing from URL: {module_url}")

            status = await loader_mod.download_and_install(module_url, None)

            if getattr(loader_mod, "fully_loaded", False):
                loader_mod.update_modules_in_db()

            # Attempt to remove the original message
            try:
                await message.delete()
                # logger.info("Original message deleted")
            except Exception as e:
                logger.error(f"Failed to delete message: {e}")

            # logger.info(status)

            if status:
                # module_name = module_path.split("/")[-1].replace(".py", "")
                # Notify official bot about success
                try:
                    bot_peer = await self.client.get_entity(8581621390)
                    await self.client.send_message(
                        bot_peer, f"#limoka:sucsess:{message.id}"
                    )
                    # logger.info(f"Sent success confirmation to bot for message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to send success confirmation: {e}")

                # logger.info(f"Module {module_name} installed successfully")
            else:
                logger.error(f"Installation failed with status: {status}")
                try:
                    bot_peer = await self.client.get_entity(8581621390)
                    await self.client.send_message(
                        bot_peer, f"#limoka:failed:{message.id}"
                    )
                    # logger.info(f"Sent failure notification to bot for message {message.id}")
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {e}")

        except Exception as e:
            logger.exception(f"CRITICAL ERROR in secure_install_watcher: {e}")
            try:
                await utils.answer(
                    message, self.strings["watcher_critical"].format(error=str(e)[:100])
                )
                await asyncio.sleep(5)
                await message.delete()
            except Exception:
                pass
