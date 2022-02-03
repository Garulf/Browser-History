from flox import Flox, ICON_HISTORY, ICON_BROWSER

import browsers

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
        self.default_browser = self.settings.get('default_browser', DEFAULT_BROWSER)
        self.browser = browsers.get(self.default_browser.lower())

    def _query(self, query):
        try:
            self.query(query)
        except FileNotFoundError:
            self.add_item(
                title='History not found!',
                subtitle='Check your logs for more information.',
            )
        finally:
            return self._results

    def query(self, query):
        history = self.browser.history(limit=10000)
        for idx, item in enumerate(history):
            if query.lower() in item.title.lower() or query.lower() in item.url.lower():
                subtitle = f"{idx}. {item.url}"
                self.add_item(
                    title=item.title,
                    subtitle=subtitle,
                    icon=ICON_HISTORY,
                    glyph=HISTORY_GLYPH,
                    method=self.browser_open,
                    parameters=[item.url],
                    context=[item.title, item.url]
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
