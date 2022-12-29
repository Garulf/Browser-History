from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plugin.browsers import Browser

@dataclass
class HistoryItem:

    browser: 'Browser'
    url: str
    title: str
    last_visit_time: int