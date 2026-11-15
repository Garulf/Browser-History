from __future__ import annotations

import asyncio
import logging
import webbrowser
from typing import List, Optional

from pyflowlauncher import FlowLauncherV2, Plugin, Result, icons

import browsers

HISTORY_LIMIT = 10000
DEFAULT_BROWSER = "chrome"
HISTORY_GLYPH = {"Glyph": "", "FontFamily": "/Resources/#Segoe Fluent Icons"}

log = logging.getLogger(__name__)
plugin = Plugin(launcher=FlowLauncherV2())


@plugin.on_method
def browser_open(url: str) -> None:
    webbrowser.open(url)


def selected_browser() -> browsers.Browser:
    name = plugin.settings.get("default_browser") or DEFAULT_BROWSER
    return browsers.get(name.lower())


def history_result(index: int, item: browsers.HistoryItem) -> Result:
    return Result(
        title=item.title,
        subtitle=f"{index}. {item.url}",
        icon=icons.HISTORY,
        glyph=HISTORY_GLYPH,
        context_data=[item.title, item.url],
    ).add_action(browser_open, [item.url])


def search(query: str) -> List[Result]:
    history = selected_browser().history(limit=HISTORY_LIMIT)
    return [history_result(index, item) for index, item in enumerate(history) if item.matches(query)]


def history_not_found() -> List[Result]:
    return [Result(title="History not found!", subtitle="Check your logs for more information.")]


@plugin.on_method
async def query(query: str) -> List[Result]:
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, search, query)
    except FileNotFoundError:
        log.exception("Browser history database not found")
        return history_not_found()


@plugin.on_method
def context_menu(data: Optional[list]) -> List[Result]:
    if not data:
        return []
    title, url = data
    return [Result(title="Open in browser", subtitle=title, icon=icons.BROWSER).add_action(browser_open, [url])]
