import sqlite3
from pathlib import Path

import pytest

import browsers
import history

CHROME_ROWS = [
    ("https://docs.python.org/3/library/sqlite3.html", "sqlite3 - Python documentation", 13370000000000000),
    ("https://github.com/Flow-Launcher/Flow.Launcher", "Flow Launcher on GitHub", 13370000300000000),
    ("https://example.com/untitled", "", 13370000100000000),
    ("https://news.ycombinator.com/", "Hacker News", 13370000200000000),
]
FIREFOX_PLACES = [
    (1, "https://www.mozilla.org/firefox/", "Firefox"),
    (2, "https://developer.mozilla.org/", None),
]
FIREFOX_VISITS = [(1, 1700000000000000), (2, 1700000500000000), (1, 1700000900000000)]


def make_chromium_history(path: Path, rows=CHROME_ROWS) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as connection:
        connection.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, last_visit_time INTEGER)")
        connection.executemany("INSERT INTO urls (url, title, last_visit_time) VALUES (?, ?, ?)", rows)
    connection.close()
    return path


def make_firefox_places(profile_dir: Path) -> Path:
    path = profile_dir / "places.sqlite"
    profile_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(path)) as connection:
        connection.execute("CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
        connection.execute("CREATE TABLE moz_historyvisits (id INTEGER PRIMARY KEY, place_id INTEGER, visit_date INTEGER)")
        connection.executemany("INSERT INTO moz_places VALUES (?, ?, ?)", FIREFOX_PLACES)
        connection.executemany("INSERT INTO moz_historyvisits (place_id, visit_date) VALUES (?, ?)", FIREFOX_VISITS)
    connection.close()
    return path


@pytest.fixture
def environ(tmp_path, monkeypatch):
    local = tmp_path / "Local"
    roaming = tmp_path / "Roaming"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))
    return {"LOCALAPPDATA": str(local), "APPDATA": str(roaming)}


@pytest.fixture
def chrome_user_data(environ):
    return browsers._path(browsers.CHROMIUM_USER_DATA["chrome"], environ)


@pytest.fixture
def chrome_history(chrome_user_data):
    return make_chromium_history(chrome_user_data / "Default" / "History")


@pytest.fixture
def firefox_dir(environ):
    return browsers._path(browsers.FIREFOX_USER_DATA["firefox"], environ)


@pytest.fixture
def firefox_places(environ):
    profiles = browsers._path(browsers.FIREFOX_USER_DATA["firefox"], environ) / "Profiles"
    (profiles / "abcd1234.default").mkdir(parents=True)
    return make_firefox_places(profiles / "wxyz5678.default-release")


@pytest.fixture
def settings():
    launcher = history.plugin.launcher
    launcher._settings = {"default_browser": "Chrome"}
    yield launcher._settings
    launcher._settings = {}
