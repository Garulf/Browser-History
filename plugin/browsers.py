from __future__ import annotations

import os
import platform
import sqlite3
import time
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional

# Environment variables
LOCAL_DATA = os.getenv("LOCALAPPDATA")
ROAMING = os.getenv("APPDATA")

# Chromium profile base folders (User Data only, profile selected later)
CHROMIUM_PROFILE_BASES = {
    "chrome": Path(LOCAL_DATA, "Google", "Chrome", "User Data"),
    "edge": Path(LOCAL_DATA, "Microsoft", "Edge", "User Data"),
    "brave": Path(LOCAL_DATA, "BraveSoftware", "Brave-Browser", "User Data"),
    "brave nightly": Path(
        LOCAL_DATA, "BraveSoftware", "Brave-Browser-Nightly", "User Data"
    ),
    "vivaldi": Path(LOCAL_DATA, "Vivaldi", "User Data"),
    "arc": Path(
        LOCAL_DATA,
        "Packages",
        "TheBrowserCompany.Arc_ttt1ap7aakyb4",
        "LocalCache",
        "Local",
        "Arc",
        "User Data",
    ),
    "thorium": Path(LOCAL_DATA, "Thorium", "User Data"),
    "helium": Path(LOCAL_DATA, "imput", "Helium", "User Data"),
}

# Single fixed path browsers
FIXED_PATHS = {
    "opera": Path(ROAMING, "Opera Software", "Opera Stable", "Default", "History")
}

FIREFOX_BASES = {
    "firefox": Path(ROAMING, "Mozilla", "Firefox", "Profiles"),
    "zen": Path(ROAMING, "zen", "Profiles"),
    "floorp": Path(ROAMING, "Floorp", "Profiles"),
    "waterfox": Path(ROAMING, "Waterfox", "Profiles"),
}

CHROMIUM_QUERY = (
    "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC"
)
FIREFOX_QUERY = "SELECT url, title, visit_date FROM moz_places INNER JOIN moz_historyvisits ON moz_historyvisits.place_id = moz_places.id ORDER BY visit_date DESC"

CHROMIUM_EPOCH_OFFSET = 11644473600


def _get_chromium_profiles(base: Path, db_file: str) -> List[Path]:
    if not base.exists():
        return []
    return [
        p / db_file
        for p in base.iterdir()
        if p.is_dir()
        and (p / db_file).exists()
        and (p.name == "Default" or p.name.startswith("Profile "))
    ]


def _get_firefox_profiles(base: Path, db_file: str) -> List[Path]:
    if not base.exists():
        return []
    return [
        p / db_file for p in base.iterdir() if p.is_dir() and (p / db_file).exists()
    ]


class Browser:
    """Represents a single browser profile history database."""

    def __init__(
        self,
        name: str,
        query: str,
        cache_dir: Path,
        timestamp_type: str = "chromium",
        custom_path: Optional[Path] = None,
        dynamic_profile: bool = False,
        db_file: str = "History",
        profile_last_updated: bool = False,
    ) -> None:
        self.name = name
        self.query = query
        self.cache_dir = cache_dir
        self.timestamp_type = timestamp_type
        self.db_file = db_file

        # Resolve database path
        if custom_path:
            # Enforce directory-only custom path strictly
            if not isinstance(custom_path, Path):
                custom_path = Path(custom_path)
            if not custom_path.exists() or not custom_path.is_dir():
                raise FileNotFoundError(
                    f"Custom profile directory does not exist or is not a directory: '{custom_path}'"
                )
            self.database_path = custom_path / db_file
        elif name in CHROMIUM_PROFILE_BASES:
            self.database_path = self._select_chromium_profile(
                CHROMIUM_PROFILE_BASES[name], db_file, profile_last_updated
            )
        elif name in FIREFOX_BASES:
            self.database_path = self._select_firefox_profile(
                FIREFOX_BASES[name], db_file, profile_last_updated
            )
        elif name in FIXED_PATHS:
            self.database_path = FIXED_PATHS[name]
        else:
            raise ValueError(f"Unsupported browser name: {name}")

        if not self.database_path or not self.database_path.exists():
            raise FileNotFoundError(
                f"History database not found exactly at: '{self.database_path}'"
            )

    def _select_chromium_profile(
        self, base: Path, db_file: str, last_updated: bool
    ) -> Path:
        candidates = _get_chromium_profiles(base, db_file)
        if not candidates:
            return None
        return (
            max(candidates, key=lambda p: p.stat().st_mtime)
            if last_updated
            else candidates[0]
        )

    def _select_firefox_profile(
        self, base: Path, db_file: str, last_updated: bool
    ) -> Path:
        candidates = _get_firefox_profiles(base, db_file)
        if not candidates:
            return None
        return (
            max(candidates, key=lambda p: p.stat().st_mtime)
            if last_updated
            else candidates[0]
        )

    def _copy_database(self, force_refresh: bool = False) -> str:
        """Create a consistent, atomically published cache copy of the source DB."""
        safe_name = self.name.replace(" ", "_")
        safe_pc = platform.node().replace(" ", "_")

        # Hash the absolute path to prevent cache collisions between different custom profiles
        path_hash = hashlib.md5(str(self.database_path).encode("utf-8")).hexdigest()[:8]
        cache_name = f"bh_{safe_pc}_{safe_name}_{path_hash}_cache.sqlite"
        target = self.cache_dir / cache_name

        # Check if we already have a cached copy that is up to date.
        try:
            if not force_refresh and target.exists():
                source_mtime = self.database_path.stat().st_mtime
                target_mtime = target.stat().st_mtime
                if source_mtime <= target_mtime:
                    return str(target)
        except OSError:
            pass  # Fallback to copying if stat fails

        temp_path = None
        last_err = None
        for attempt in range(3):
            try:
                temp_fd, temp_name = tempfile.mkstemp(
                    prefix=f".{target.name}.", suffix=".tmp", dir=self.cache_dir
                )
                os.close(temp_fd)
                temp_path = Path(temp_name)

                source_uri = f"{self.database_path.as_uri()}?mode=ro"
                source_connection = None
                destination_connection = None
                try:
                    source_connection = sqlite3.connect(source_uri, uri=True)
                    destination_connection = sqlite3.connect(str(temp_path))
                    source_connection.backup(destination_connection)
                    destination_connection.commit()
                    check = destination_connection.execute(
                        "PRAGMA quick_check"
                    ).fetchone()
                    if not check or check[0] != "ok":
                        raise sqlite3.DatabaseError(
                            f"SQLite integrity check failed for '{self.database_path}'"
                        )
                finally:
                    if source_connection:
                        source_connection.close()
                    if destination_connection:
                        destination_connection.close()

                os.replace(temp_path, target)
                temp_path = None
                break
            except (OSError, sqlite3.Error) as e:
                last_err = e
                if temp_path:
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                    temp_path = None
                time.sleep(0.05 * (attempt + 1))
        else:
            raise OSError(
                f"Failed copying history DB for '{self.name}' from '{self.database_path}' to '{target}': {last_err}"
            )

        return str(target)

    def history(
        self,
        search_term: str = "",
        limit: int = 100,
        blocked_domains: Optional[List[str]] = None,
    ) -> List["HistoryItem"]:
        for cache_attempt in range(2):
            db_path = self._copy_database(force_refresh=cache_attempt == 1)
            try:
                rows = self._read_history(db_path, search_term, limit, blocked_domains)
                return [HistoryItem(self, *row) for row in rows]
            except sqlite3.DatabaseError:
                if cache_attempt == 1:
                    raise
                try:
                    Path(db_path).unlink()
                except OSError:
                    pass

        return []

    def _read_history(
        self,
        db_path: str,
        search_term: str,
        limit: int,
        blocked_domains: Optional[List[str]],
    ):
        last_err = None
        connection = None
        for attempt in range(3):
            try:
                # Open strictly in read-only mode using a URI
                connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                break
            except (OSError, sqlite3.Error) as e:
                last_err = e
                time.sleep(0.03 * (attempt + 1))
        else:
            raise OSError(
                f"Failed to open copied history DB for '{self.name}' at '{db_path}' after retries: {last_err}"
            )

        try:
            cursor = connection.cursor()
            base, order = self.query.split(" ORDER BY ")
            conditions = []
            params = []

            if search_term:
                terms = search_term.split()
                # Require EVERY word to be present in either the title or the URL
                for term in terms:
                    conditions.append("(title LIKE ? OR url LIKE ?)")
                    params.extend([f"%{term}%", f"%{term}%"])

            if blocked_domains:
                for domain in blocked_domains:
                    conditions.append("url NOT LIKE ?")
                    params.append(f"%{domain}%")

            if conditions:
                where_clause = " AND ".join(conditions)
                sql = f"{base} WHERE {where_clause} ORDER BY {order} LIMIT ?"
            else:
                sql = f"{base} ORDER BY {order} LIMIT ?"

            params.append(limit)
            cursor.execute(sql, tuple(params))

            rows = cursor.fetchall()
        finally:
            connection.close()
        return rows

    def convert_timestamp(self, raw_time):
        seconds = self.normalize_timestamp(raw_time)
        return datetime.fromtimestamp(seconds)

    def normalize_timestamp(self, raw_time) -> float:
        if raw_time is None:
            return 0.0
        try:
            if self.timestamp_type == "chromium":
                seconds = raw_time / 1_000_000 - CHROMIUM_EPOCH_OFFSET
            elif self.timestamp_type == "unix_us":
                seconds = raw_time / 1_000_000
            else:
                seconds = 0.0
            return max(0.0, float(seconds))
        except OSError:
            return 0.0


class HistoryItem:
    """Single history row wrapper."""

    def __init__(
        self, browser: Browser, url: str, title: str, last_visit_time: int
    ) -> None:
        self.browser = browser
        self.url = url
        self.title = title.strip() if title else url
        self.last_visit_time = last_visit_time

    def timestamp(self) -> datetime:
        return self.browser.convert_timestamp(self.last_visit_time)

    def normalized_time(self) -> float:
        return self.browser.normalize_timestamp(self.last_visit_time)


def get(
    browser_name: str,
    cache_dir: Path,
    custom_profile_path: Optional[str] = None,
    profile_last_updated: bool = False,
) -> Optional[Browser]:
    browser_name = browser_name.lower()
    profile_last_updated = bool(profile_last_updated)

    if browser_name == "custom profile":
        if not custom_profile_path:
            raise ValueError("Custom profile path not provided in settings.")

        raw_path = os.path.expandvars(custom_profile_path.strip("\"' "))
        path = Path(raw_path)

        if not path.exists() or not path.is_dir():
            raise ValueError(
                f"Custom directory does not exist or is not a folder: {path}"
            )

        # Strictly check exact folder provided by the user
        if (path / "History").exists():
            return Browser(
                "custom profile",
                CHROMIUM_QUERY,
                cache_dir,
                "chromium",
                custom_path=path,
                db_file="History",
            )
        elif (path / "places.sqlite").exists():
            return Browser(
                "custom profile",
                FIREFOX_QUERY,
                cache_dir,
                "unix_us",
                custom_path=path,
                db_file="places.sqlite",
            )
        else:
            raise ValueError(
                f"Neither 'History' nor 'places.sqlite' exists exactly in: '{path}'"
            )

    try:
        if browser_name in CHROMIUM_PROFILE_BASES or browser_name in FIXED_PATHS:
            return Browser(
                browser_name,
                CHROMIUM_QUERY,
                cache_dir,
                "chromium",
                profile_last_updated=profile_last_updated,
            )
        if browser_name in FIREFOX_BASES:
            return Browser(
                browser_name,
                FIREFOX_QUERY,
                cache_dir,
                "unix_us",
                dynamic_profile=True,
                db_file="places.sqlite",
                profile_last_updated=profile_last_updated,
            )
        raise ValueError(f"Unsupported browser: {browser_name}")
    except FileNotFoundError:
        return None


def get_all_profiles(
    browser_name: str, cache_dir: Path, custom_profile_path: Optional[str] = None
) -> List[Browser]:
    browser_name = browser_name.lower()
    browsers_list = []

    if browser_name == "custom profile":
        if not custom_profile_path:
            return []

        raw_path = os.path.expandvars(custom_profile_path.strip("\"' "))
        path = Path(raw_path)

        if not path.exists() or not path.is_dir():
            raise ValueError(
                f"Custom directory does not exist or is not a folder: {path}"
            )

        # Strictly check exact folder provided by the user
        if (path / "History").exists():
            browsers_list.append(
                Browser(
                    "custom_profile_0",
                    CHROMIUM_QUERY,
                    cache_dir,
                    "chromium",
                    custom_path=path,
                    db_file="History",
                )
            )
        elif (path / "places.sqlite").exists():
            browsers_list.append(
                Browser(
                    "custom_profile_0",
                    FIREFOX_QUERY,
                    cache_dir,
                    "unix_us",
                    custom_path=path,
                    db_file="places.sqlite",
                )
            )
        else:
            raise ValueError(
                f"Neither 'History' nor 'places.sqlite' exists exactly in: '{path}'"
            )

        return browsers_list

    if browser_name in CHROMIUM_PROFILE_BASES:
        base = CHROMIUM_PROFILE_BASES[browser_name]
        db_file = "History"
        query = CHROMIUM_QUERY
        ts_type = "chromium"
    elif browser_name in FIREFOX_BASES:
        base = FIREFOX_BASES[browser_name]
        db_file = "places.sqlite"
        query = FIREFOX_QUERY
        ts_type = "unix_us"
    else:
        single_browser = get(browser_name, cache_dir)
        return [single_browser] if single_browser else []

    if not base.exists():
        return []

    if browser_name in CHROMIUM_PROFILE_BASES:
        candidates = _get_chromium_profiles(base, db_file)
    else:
        candidates = _get_firefox_profiles(base, db_file)

    for idx, path in enumerate(candidates):
        unique_name = f"{browser_name}_profile_{idx}"
        try:
            browsers_list.append(
                Browser(
                    unique_name,
                    query,
                    cache_dir,
                    ts_type,
                    custom_path=path.parent,
                    db_file=db_file,
                )
            )
        except FileNotFoundError:
            continue

    return browsers_list
