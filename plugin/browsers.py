import shutil
import sqlite3
from tempfile import mktemp
import os
from pathlib import Path
import logging
import time
from typing import List
from dataclasses import dataclass

from history_item import HistoryItem

log = logging.getLogger(__name__)

LOCAL_DATA = os.getenv('LOCALAPPDATA')
ROAMING = os.getenv('APPDATA')
CHROME_DIR = Path(LOCAL_DATA, 'Google', 'Chrome', 'User Data', 'Default', 'History')
FIREFOX_DIR = Path(ROAMING, 'Mozilla', 'Firefox', 'Profiles').glob('*.default-release').__next__()
EDGE_DIR = Path(LOCAL_DATA, 'Microsoft', 'Edge', 'User Data', 'Default', 'History')
BRAVE_DIR = Path(LOCAL_DATA, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'History')

CHROME_QUERY = 'SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC'
FIREFOX_QUERY = 'SELECT url, title, visit_date FROM moz_places INNER JOIN moz_historyvisits on moz_historyvisits.place_id = moz_places.id ORDER BY visit_date DESC'


class HistoryDB:
    """
    Creates a temporary copy of the browser history database and deletes it when the object is destroyed.

    This is necessary because the database is locked when the browser is open.
    """

    def __init__(self, original_file_path: str):
        self.original_file_path = original_file_path

    def __enter__(self):
        """Copy the database to a temporary location and return the path to the copy."""
        # Documentation states this is the most secure way to make a temp file.
        _temp_file = mktemp() # Documentation: https://docs.python.org/3/library/tempfile.html#tempfile.mktemp
        self.temp_file_path = shutil.copyfile(self.original_file_path, _temp_file)
        return self.temp_file_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Delete the temporary database file after the object is destroyed."""
        for _ in range(10):
            try:
                os.remove(self.temp_file_path)
            except PermissionError:
                time.sleep(0.5)
            else:
                break
        else:
            raise PermissionError(f'Could not delete temp file!')

class Browser:

    def __init__(self, database_path: str = CHROME_DIR, db_query: str = CHROME_QUERY):
        self.database_path = database_path
        self.db_query = db_query

    def _query_db(self, db_file: str, limit: int = 10):
        """Query Browser history SQL Database."""
        with sqlite3.connect(db_file) as connection:
            cursor = connection.cursor()
            cursor.execute(f'{self.db_query} LIMIT {limit}')
            results = cursor.fetchall()
        connection.close() # Context manager doesn't close the db file
        return results

    def get_history(self, limit: int = 10) -> List[HistoryItem]:
        """Returns a list of the most recently visited sites in Chrome's history."""
        with HistoryDB(self.database_path) as db_file:
            recents = self._query_db(db_file, limit)
            return [HistoryItem(self, *result) for result in recents]

BROWSERS = {
    'chrome': Browser(CHROME_DIR, CHROME_QUERY),
    'firefox': Browser(FIREFOX_DIR, FIREFOX_QUERY),
    'edge': Browser(EDGE_DIR, CHROME_QUERY),
    'brave': Browser(BRAVE_DIR, CHROME_QUERY)
}