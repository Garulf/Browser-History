from flox import Flox, ICON_HISTORY, ICON_BROWSER
from flox.string_matcher import string_matcher

from browsers import BROWSERS

HISTORY_GLYPH = ''
DEFAULT_BROWSER = 'chrome'

def remove_duplicates(results):
    for item in results:
        if item in results:
            results.remove(item)
    return results

class BrowserHistory(Flox):

    def __init__(self):
        super().__init__()
        self.default_browser = self.settings.get('default_browser', DEFAULT_BROWSER).lower()
        self.browser = BROWSERS[self.default_browser]

    def _query(self, query):
        try:
            self.query(query)
        except FileNotFoundError:
            self.add_item(
                title='History not found!',
                subtitle='Check your logs for more information.',
            )
        except Exception as e:
            self.add_item(
                title='Something went wrong!',
                subtitle=f'Check your logs for more information: {e}',
            )
            self.logger.exception(e)
        finally:
            return self._results

    def query(self, query):
        history = self.browser.get_history(limit=10000)
        for idx, item in enumerate(history):
            title_match = string_matcher(query, item.title)
            title_score = title_match.score if title_match else 0
            url_match = string_matcher(query, item.url)
            url_score = url_match.score if url_match else 0
            subtitle = f"{idx}. {item.url}"
            self.add_item(
                title=item.title,
                subtitle=subtitle,
                icon=ICON_HISTORY,
                glyph=HISTORY_GLYPH,
                method=self.browser_open,
                parameters=[item.url],
                context=[item.title, item.url],
                score=int(max(title_score, url_score)),
            )

    def context_menu(self, data):
        self.add_item(
            title='Open in browser',
            subtitle=data[0],
            icon=ICON_BROWSER,
            method=self.browser_open,
            parameters=[data[1]],

        )

if __name__ == "__main__":
    BrowserHistory()
