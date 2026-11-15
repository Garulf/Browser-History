from pathlib import Path

import pytest

import browsers
from conftest import make_chromium_history, make_firefox_places


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


PROFILES_INI = """[Profile1]
Name=default
IsRelative=1
Path=Profiles/abcd1234.default
Default=1

[Profile0]
Name=work
IsRelative=1
Path=Profiles/qs116czo.Old Settings

[Install308046B0AF4A39CB]
Default=Profiles/qs116czo.Old Settings
Locked=1

[General]
StartWithLastProfile=1
Version=2
"""


def test_firefox_uses_install_default_from_profiles_ini(firefox_dir):
    make_firefox_places(firefox_dir / "Profiles" / "abcd1234.default")
    expected = make_firefox_places(firefox_dir / "Profiles" / "qs116czo.Old Settings")
    (firefox_dir / "profiles.ini").write_text(PROFILES_INI, encoding="utf-8")
    assert browsers.get("firefox").database_path == expected


def test_firefox_falls_back_to_legacy_default_profile(firefox_dir):
    expected = make_firefox_places(firefox_dir / "Profiles" / "abcd1234.default")
    ini = PROFILES_INI.replace("Default=Profiles/qs116czo.Old Settings", "Default=Profiles/missing")
    (firefox_dir / "profiles.ini").write_text(ini, encoding="utf-8")
    assert browsers.get("firefox").database_path == expected


def test_firefox_finds_suffixed_default_release_profile(firefox_dir):
    expected = make_firefox_places(firefox_dir / "Profiles" / "5ci8zu0b.default-release-1681539393892")
    assert browsers.get("firefox").database_path == expected


def test_firefox_absolute_profile_path(firefox_dir, tmp_path):
    expected = make_firefox_places(tmp_path / "Elsewhere" / "custom.profile")
    firefox_dir.mkdir(parents=True)
    (firefox_dir / "profiles.ini").write_text(
        f"[Install1]\nDefault={expected.parent}\n", encoding="utf-8"
    )
    assert browsers.get("firefox").database_path == expected


def test_unreadable_profiles_ini_is_ignored(firefox_places, firefox_dir):
    (firefox_dir / "profiles.ini").write_bytes(b"\xff\xfe not an ini [")
    assert browsers.get("firefox").database_path == firefox_places
