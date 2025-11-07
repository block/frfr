"""TUI screens for frfr."""

from frfr.tui.screens.home import HomeScreen
from frfr.tui.screens.session_detail import SessionDetailScreen
from frfr.tui.screens.help import HelpScreen
from frfr.tui.screens.new_session import NewSessionScreen
from frfr.tui.screens.add_document import AddDocumentScreen
from frfr.tui.screens.processing import ProcessingScreen
from frfr.tui.screens.facts_browser import FactsBrowserScreen
from frfr.tui.screens.query import QueryScreen

__all__ = [
    "HomeScreen",
    "SessionDetailScreen",
    "HelpScreen",
    "NewSessionScreen",
    "AddDocumentScreen",
    "ProcessingScreen",
    "FactsBrowserScreen",
    "QueryScreen",
]
