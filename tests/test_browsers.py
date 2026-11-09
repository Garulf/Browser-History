import sqlite3
import tempfile
import unittest
from pathlib import Path

from plugin.browsers import Browser, CHROMIUM_QUERY


class BrowserCacheTests(unittest.TestCase):
    def assert_database_is_valid(self, database: Path) -> None:
        connection = sqlite3.connect(database)
        try:
            self.assertEqual(
                connection.execute("PRAGMA quick_check").fetchone()[0], "ok"
            )
        finally:
            connection.close()

    def create_browser(self, root: Path) -> Browser:
        profile = root / "Profile"
        profile.mkdir()
        database = profile / "History"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "CREATE TABLE urls (url TEXT, title TEXT, last_visit_time INTEGER)"
            )
            connection.execute(
                "INSERT INTO urls VALUES (?, ?, ?)",
                ("https://example.com", "Example", 13253760000000000),
            )
            connection.commit()
        finally:
            connection.close()

        return Browser(
            "custom profile",
            CHROMIUM_QUERY,
            root / "Cache",
            custom_path=profile,
            db_file="History",
        )

    def test_database_is_published_without_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            browser = self.create_browser(root)
            browser.cache_dir.mkdir()

            cache_path = Path(browser._copy_database())

            self.assertTrue(cache_path.exists())
            self.assertEqual(list(browser.cache_dir.glob("*.tmp")), [])
            self.assert_database_is_valid(cache_path)

    def test_corrupt_cache_is_rebuilt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            browser = self.create_browser(root)
            browser.cache_dir.mkdir()
            cache_path = Path(browser._copy_database())
            cache_path.write_bytes(b"not a sqlite database")

            results = browser.history()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].url, "https://example.com")
            self.assert_database_is_valid(cache_path)


if __name__ == "__main__":
    unittest.main()
