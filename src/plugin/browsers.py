from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Tuple

CHROMIUM_QUERY = "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC"
FIREFOX_QUERY = (
    "SELECT url, title, visit_date FROM moz_places "
    "INNER JOIN moz_historyvisits on moz_historyvisits.place_id = moz_places.id "
    "ORDER BY visit_date DESC"
)
FIREFOX_PROFILE_GLOB = "*.default-release"

CHROMIUM_HISTORY = {
    "chrome": ("LOCALAPPDATA", "Google", "Chrome", "User Data", "Default", "History"),
    "edge": ("LOCALAPPDATA", "Microsoft", "Edge", "User Data", "Default", "History"),
    "brave": ("LOCALAPPDATA", "BraveSoftware", "Brave-Browser", "User Data", "Default", "History"),
    "opera": ("APPDATA", "Opera Software", "Opera Stable", "Default", "History"),
    "vivaldi": ("LOCALAPPDATA", "Vivaldi", "User Data", "Default", "History"),
    "arc": (
        "LOCALAPPDATA", "Packages", "TheBrowserCompany.Arc_ttt1ap7aakyb4",
        "LocalCache", "Local", "Arc", "User Data", "Default", "History",
    ),
}
FIREFOX_PROFILES = ("APPDATA", "Mozilla", "Firefox", "Profiles")


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
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = shutil.copy(str(self.database_path), temp_dir)
            connection = sqlite3.connect(temp_path)
            try:
                rows = connection.execute(f"{self.query} LIMIT ?", (limit,)).fetchall()
            finally:
                connection.close()
        return [HistoryItem.from_row(*row) for row in rows]


def _path(parts: Tuple[str, ...], environ: Mapping[str, str]) -> Path:
    root, *rest = parts
    return Path(environ.get(root, ""), *rest)


def find_firefox_database(profiles_dir: Path) -> Path:
    profile = next(Path(profiles_dir).glob(FIREFOX_PROFILE_GLOB), None)
    if profile is None:
        raise FileNotFoundError(f"No {FIREFOX_PROFILE_GLOB} profile in {profiles_dir}")
    return profile / "places.sqlite"


def get(browser_name: str, environ: Optional[Mapping[str, str]] = None) -> Browser:
    environ = os.environ if environ is None else environ
    if browser_name in CHROMIUM_HISTORY:
        return Browser(browser_name, _path(CHROMIUM_HISTORY[browser_name], environ), CHROMIUM_QUERY)
    if browser_name == "firefox":
        database = find_firefox_database(_path(FIREFOX_PROFILES, environ))
        return Browser(browser_name, database, FIREFOX_QUERY)
    raise ValueError("Invalid browser name")
