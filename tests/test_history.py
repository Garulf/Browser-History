import asyncio
from pathlib import Path

import browsers
import history
from conftest import make_firefox_places


def run(method, *args):
    return asyncio.run(history.plugin._event_handler.trigger_event(method, *args))


def results(method, *args):
    return run(method, *args)["Result"]


def test_query_filters_by_title_or_url_newest_first(settings, chrome_history):
    found = results("query", "o")
    assert [r["Title"] for r in found] == [
        "Flow Launcher on GitHub",
        "Hacker News",
        "https://example.com/untitled",
        "sqlite3 - Python documentation",
    ]
    assert [r["Title"] for r in results("query", "GITHUB")] == ["Flow Launcher on GitHub"]


def test_subtitle_numbers_the_full_history(settings, chrome_history):
    (result,) = results("query", "python")
    assert result["SubTitle"] == "3. https://docs.python.org/3/library/sqlite3.html"
    assert result["Score"] == 0


def test_result_opens_url_and_carries_context(settings, chrome_history):
    (result,) = results("query", "hacker")
    assert result["JsonRPCAction"] == {
        "Method": "browser_open",
        "Parameters": ["https://news.ycombinator.com/"],
        "DontHideAfterAction": False,
    }
    assert result["ContextData"] == ["Hacker News", "https://news.ycombinator.com/"]
    assert result["Glyph"] == history.HISTORY_GLYPH


def test_empty_query_lists_everything(settings, chrome_history):
    assert len(results("query", "")) == 4


def test_default_browser_is_chrome(chrome_history):
    history.plugin.launcher._settings = {}
    assert len(results("query", "")) == 4


def test_firefox_setting(settings, firefox_places):
    settings["default_browser"] = "Firefox"
    assert [r["Title"] for r in results("query", "mozilla")] == [
        "Firefox",
        "https://developer.mozilla.org/",
        "Firefox",
    ]


def test_missing_history_shows_not_found(settings, environ):
    settings["default_browser"] = "Edge"
    (result,) = results("query", "")
    assert result["Title"] == "History not found!"
    assert result["JsonRPCAction"] is None


def test_missing_firefox_profile_shows_not_found(settings, environ):
    settings["default_browser"] = "Firefox"
    assert results("query", "")[0]["Title"] == "History not found!"


def test_context_menu_opens_in_browser():
    result = results("context_menu", ["Hacker News", "https://news.ycombinator.com/"])[0]
    assert result["Title"] == "Open in browser"
    assert result["SubTitle"] == "Hacker News"
    assert result["JsonRPCAction"]["Method"] == "browser_open"
    assert result["JsonRPCAction"]["Parameters"] == ["https://news.ycombinator.com/"]


def test_context_menu_without_data_is_empty():
    assert results("context_menu", None) == []


def test_browser_open_uses_default_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(history.webbrowser, "open", opened.append)
    run("browser_open", "https://example.com/")
    assert opened == ["https://example.com/"]


def test_context_menu_copies_url():
    copy = results("context_menu", ["Hacker News", "https://news.ycombinator.com/"])[1]
    assert copy["Title"] == "Copy URL"
    assert copy["SubTitle"] == "https://news.ycombinator.com/"
    assert copy["JsonRPCAction"]["Method"] == "Flow.Launcher.CopyToClipboard"
    assert copy["JsonRPCAction"]["Parameters"][0] == "https://news.ycombinator.com/"


def test_result_copy_text_is_the_url(settings, chrome_history):
    (result,) = results("query", "hacker")
    assert result["CopyText"] == "https://news.ycombinator.com/"


def test_waterfox_setting(settings, environ, tmp_path):
    make_firefox_places(tmp_path / "Roaming" / "Waterfox" / "Profiles" / "k3j2.default-release")
    settings["default_browser"] = "Waterfox"
    assert [r["Title"] for r in results("query", "mozilla")] == [
        "Firefox",
        "https://developer.mozilla.org/",
        "Firefox",
    ]


def test_settings_template_offers_every_browser():
    template = (Path(__file__).parents[1] / "data" / "SettingsTemplate.yaml").read_text(encoding="utf-8")
    options = [line.strip()[2:] for line in template.splitlines() if line.strip().startswith("- ") and "type:" not in line]
    assert options == ["Chrome", "Firefox", "Edge", "Brave", "Opera", "Vivaldi", "Arc", "Waterfox"]
    for option in options:
        assert option.lower() in browsers.CHROMIUM_USER_DATA or option.lower() in browsers.FIREFOX_USER_DATA
