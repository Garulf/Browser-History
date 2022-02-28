import shutil
import sqlite3
from tempfile import gettempdir
import os
from pathlib import Path
from datetime import datetime
import logging

log = logging.getLogger(__name__)

LOCAL_DATA = os.getenv('LOCALAPPDATA')
ROAMING = os.getenv('APPDATA')
CHROME_DIR = Path(LOCAL_DATA, 'Google', 'Chrome', 'User Data', 'Default', 'History')
FIREFOX_DIR = Path(ROAMING, 'Mozilla', 'Firefox', 'Profiles')
EDGE_DIR = Path(LOCAL_DATA, 'Microsoft', 'Edge', 'User Data', 'Default', 'History')

def get(browser_name):
    if browser_name == 'chrome':
        return Chrome()
    elif browser_name == 'firefox':
        return Firefox()
    elif browser_name == 'edge':
        return Edge()
    else:
        raise ValueError('Invalid browser name')

class Base(object):
    
    def __del__(self):
        if hasattr(self, 'temp_path'):
            # Probably best we don't leave browser history in the temp directory
            # This deletes the temporary database file after the object is destroyed
            os.remove(self.temp_path)

    def _copy_database(self, database_path):
        """
        Copies the database to a temporary location and returns the path to the
        copy.
        """
        temp_dir = gettempdir()
        temp_path = shutil.copy(database_path, temp_dir)
        self.temp_path = temp_path
        return temp_path

    def query_history(self, database_path, query, limit=10):
        """
        Query Browser history SQL Database.
        """
        # Copy the database to a temporary location.
        temp_path = self._copy_database(database_path)

        # Open the database.
        with sqlite3.connect(temp_path) as connection:
            cursor = connection.cursor()
            cursor.execute(f'{query} LIMIT {limit}')
            return cursor.fetchall()

    def get_history_items(self, results):
        """
        Converts the tuple returned by the query to a HistoryItem object.
        """
        data = []
        for result in results:
            data.append(HistoryItem(self, *result))
        return data


class Chrome(Base):
    """Google Chrome History"""

    def __init__(self, database_path=CHROME_DIR):
        self.database_path = database_path

    def history(self, limit=10):
        """
        Returns a list of the most recently visited sites in Chrome's history.
        """
        recents = self.query_history(self.database_path, 'SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC', limit)
        return self.get_history_items(recents)

class Firefox(Base):
    """Firefox Browser History"""

    def __init__(self, database_path=FIREFOX_DIR):
        # Firefox database is not in a static location, so we need to find it
        self.database_path = self.find_database(database_path)

    def find_database(self, path):
        """Find database in path"""
        release_folder = Path(path).glob('*.default-release').__next__()
        return Path(path, release_folder, 'places.sqlite')

    def history(self, limit=10):
        """Most recent Firefox history"""
        recents = self.query_history(self.database_path, 'SELECT url, title, visit_date FROM moz_places INNER JOIN moz_historyvisits on moz_historyvisits.place_id = moz_places.id ORDER BY visit_date DESC', limit)
        return self.get_history_items(recents)

class Edge(Base):
    """Microsoft Edge History"""

    def __init__(self, database_path=EDGE_DIR):
        self.database_path = database_path

    def history(self, limit=10):
        """
        Returns a list of the most recently visited sites in Chrome's history.
        """
        recents = self.query_history(self.database_path, 'SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC', limit)
        return self.get_history_items(recents)

class HistoryItem(object):
    """Representation of a history item"""

    def __init__(self, browser, url, title, last_visit_time):
        self.browser = browser
        self.url = url
        if title is None:
            title = ''
        if title.strip() == '':
            self.title = url
        else:
            self.title = title
        self.last_visit_time = last_visit_time

    def timestamp(self):
        if isinstance(self.browser, (Chrome)):
            return datetime((self.last_visit_time/1000000)-11644473600, 'unixepoch', 'localtime')
        elif isinstance(self.browser, (Firefox)):
            return datetime.fromtimestamp(self.last_visit_time / 1000000.0)
        elif isinstance(self.browser, (Edge)):
            return datetime((self.last_visit_time/1000000)-11644473600, 'unixepoch', 'localtime')