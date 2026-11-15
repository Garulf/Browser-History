from pathlib import Path

import pytest

import browsers
from conftest import make_chromium_history


def test_chromium_history_is_newest_first_and_limited(chrome_history):
    items = browsers.get("chrome").history(limit=3)
    assert [item.title for item in items] == [
        "Flow Launcher on GitHub",
        "Hacker News",
        "https://example.com/untitled",
    ]
    assert items[0].url == "https://github.com/Flow-Launcher/Flow.Launcher"
    assert items[0].last_visit_time == 13370000300000000


def test_history_reads_a_copy_and_leaves_the_database_alone(chrome_history):
    before = chrome_history.read_bytes()
    browsers.get("chrome").history()
    assert chrome_history.read_bytes() == before


@pytest.mark.parametrize(
    ("name", "root", "parts"),
    [
        ("chrome", "Local", ("Google", "Chrome", "User Data", "Default", "History")),
        ("edge", "Local", ("Microsoft", "Edge", "User Data", "Default", "History")),
        ("brave", "Local", ("BraveSoftware", "Brave-Browser", "User Data", "Default", "History")),
        ("opera", "Roaming", ("Opera Software", "Opera Stable", "Default", "History")),
        ("vivaldi", "Local", ("Vivaldi", "User Data", "Default", "History")),
        (
            "arc",
            "Local",
            ("Packages", "TheBrowserCompany.Arc_ttt1ap7aakyb4", "LocalCache", "Local", "Arc", "User Data", "Default", "History"),
        ),
    ],
)
def test_chromium_browsers_read_their_own_profile(environ, tmp_path, name, root, parts):
    path = make_chromium_history(Path(tmp_path, root, *parts), rows=[("https://example.org/", name, 1)])
    browser = browsers.get(name)
    assert browser.database_path == path
    assert [item.title for item in browser.history()] == [name]


def test_firefox_uses_default_release_profile(firefox_places):
    browser = browsers.get("firefox")
    assert browser.database_path == firefox_places
    items = browser.history(limit=10)
    assert [(item.title, item.last_visit_time) for item in items] == [
        ("Firefox", 1700000900000000),
        ("https://developer.mozilla.org/", 1700000500000000),
        ("Firefox", 1700000000000000),
    ]


def test_firefox_without_release_profile_is_not_found(environ):
    with pytest.raises(FileNotFoundError):
        browsers.get("firefox")


def test_missing_history_file_is_not_found(environ):
    with pytest.raises(FileNotFoundError):
        browsers.get("edge").history()


def test_unknown_browser_is_rejected(environ):
    with pytest.raises(ValueError):
        browsers.get("netscape")


def test_paths_can_be_injected(tmp_path):
    browser = browsers.get("chrome", environ={"LOCALAPPDATA": str(tmp_path)})
    assert browser.database_path == tmp_path / "Google" / "Chrome" / "User Data" / "Default" / "History"


@pytest.mark.parametrize("query", ["hacker", "HACKER", "ycombinator"])
def test_item_matches_title_or_url_ignoring_case(query):
    item = browsers.HistoryItem.from_row("https://news.ycombinator.com/", "Hacker News", 1)
    assert item.matches(query)
    assert not item.matches("lobsters")
