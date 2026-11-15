from __future__ import annotations

import configparser
import json
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Mapping, Optional, Tuple

CHROMIUM_QUERY = "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC"
FIREFOX_QUERY = (
    "SELECT url, title, visit_date FROM moz_places "
    "INNER JOIN moz_historyvisits on moz_historyvisits.place_id = moz_places.id "
    "ORDER BY visit_date DESC"
)
FIREFOX_PROFILE_GLOB = "*.default-release*"

CHROMIUM_USER_DATA = {
    "chrome": ("LOCALAPPDATA", "Google", "Chrome", "User Data"),
    "edge": ("LOCALAPPDATA", "Microsoft", "Edge", "User Data"),
    "brave": ("LOCALAPPDATA", "BraveSoftware", "Brave-Browser", "User Data"),
    "opera": ("APPDATA", "Opera Software", "Opera Stable"),
    "vivaldi": ("LOCALAPPDATA", "Vivaldi", "User Data"),
    "arc": ("LOCALAPPDATA", "Packages", "TheBrowserCompany.Arc_ttt1ap7aakyb4", "LocalCache", "Local", "Arc", "User Data"),
}
CHROMIUM_DEFAULT_PROFILE = "Default"
FIREFOX_USER_DATA = {
    "firefox": ("APPDATA", "Mozilla", "Firefox"),
    "waterfox": ("APPDATA", "Waterfox"),
}


@dataclass(frozen=True)
class HistoryItem:
    url: str
    title: str
    last_visit_time: int

    @classmethod
    def from_row(cls, url: str, title: Optional[str], last_visit_time: int) -> HistoryItem:
        if not title or not title.strip():
            title = url
        return cls(url, title, last_visit_time)

    def matches(self, query: str) -> bool:
        query = query.lower()
        return query in self.title.lower() or query in self.url.lower()


@dataclass(frozen=True)
class Browser:
    name: str
    database_path: Path
    query: str

    def history(self, limit: int = 10) -> List[HistoryItem]:
        """Most recent visits, newest first, read from a copy because the browser locks its database."""
        temp_dir = tempfile.mkdtemp(prefix="browser-history-")
        try:
            temp_path = shutil.copy(str(self.database_path), temp_dir)
            wal = self.database_path.with_name(self.database_path.name + "-wal")
            if wal.is_file():
                shutil.copy(str(wal), temp_dir)
            connection = sqlite3.connect(temp_path)
            try:
                rows = connection.execute(f"{self.query} LIMIT ?", (limit,)).fetchall()
            finally:
                connection.close()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return [HistoryItem.from_row(*row) for row in rows]


def _path(parts: Tuple[str, ...], environ: Mapping[str, str]) -> Path:
    root, *rest = parts
    return Path(environ.get(root, ""), *rest)


def _last_used_chromium_profile(user_data: Path) -> Optional[str]:
    try:
        local_state = json.loads((user_data / "Local State").read_text(encoding="utf-8"))
        return local_state["profile"]["last_used"] or None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def find_chromium_database(user_data: Path) -> Path:
    for profile in (_last_used_chromium_profile(user_data), CHROMIUM_DEFAULT_PROFILE):
        if profile and (user_data / profile / "History").is_file():
            return user_data / profile / "History"
    return user_data / CHROMIUM_DEFAULT_PROFILE / "History"


def _read_profiles_ini(firefox_dir: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        parser.read_string((firefox_dir / "profiles.ini").read_text(encoding="utf-8", errors="replace"))
    except (OSError, configparser.Error):
        pass
    return parser


def _candidate_profiles(firefox_dir: Path) -> Iterator[Path]:
    """Profiles in the order Firefox picks them: the install default, the legacy default, then by name."""
    parser = _read_profiles_ini(firefox_dir)
    sections = [parser[name] for name in parser.sections()]
    for section in sections:
        if section.name.startswith("Install") and section.get("Default"):
            yield firefox_dir / section["Default"]
    for section in sections:
        if section.name.startswith("Profile") and section.get("Default") == "1" and section.get("Path"):
            yield firefox_dir / section["Path"]
    yield from sorted((firefox_dir / "Profiles").glob(FIREFOX_PROFILE_GLOB))


def find_firefox_database(firefox_dir: Path) -> Path:
    for profile in _candidate_profiles(Path(firefox_dir)):
        database = profile / "places.sqlite"
        if database.is_file():
            return database
    raise FileNotFoundError(f"No Firefox profile with places.sqlite in {firefox_dir}")


def get(browser_name: str, environ: Optional[Mapping[str, str]] = None) -> Browser:
    environ = os.environ if environ is None else environ
    if browser_name in CHROMIUM_USER_DATA:
        database = find_chromium_database(_path(CHROMIUM_USER_DATA[browser_name], environ))
        return Browser(browser_name, database, CHROMIUM_QUERY)
    if browser_name in FIREFOX_USER_DATA:
        database = find_firefox_database(_path(FIREFOX_USER_DATA[browser_name], environ))
        return Browser(browser_name, database, FIREFOX_QUERY)
    raise ValueError("Invalid browser name")
