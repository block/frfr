"""Main Textual application for frfr TUI."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer

from frfr.tui.state import AppState
from frfr.tui.screens.home import HomeScreen
from frfr.tui.screens.help import HelpScreen


class FrfrApp(App):
    """Main TUI application for frfr."""

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        dock: top;
    }

    Footer {
        dock: bottom;
    }

    .box {
        border: solid $primary;
        background: $panel;
        padding: 1 2;
    }

    .title {
        text-style: bold;
        color: $text;
        background: $primary;
        padding: 0 1;
    }

    .success {
        color: $success;
    }

    .warning {
        color: $warning;
    }

    .error {
        color: $error;
    }

    .info {
        color: $accent;
    }

    DataTable {
        height: 1fr;
    }

    DataTable > .datatable--cursor {
        background: $accent 20%;
    }

    DataTable > .datatable--header {
        text-style: bold;
        background: $primary;
    }

    Tree {
        background: $panel;
        border: solid $primary;
    }

    #left-panel {
        width: 40%;
        border-right: solid $primary;
        padding: 1;
    }

    #right-panel {
        width: 1fr;
        padding: 1;
    }

    .fact-item {
        padding: 1;
        margin: 0 0 1 0;
        border: solid $primary;
        background: $panel;
    }

    .fact-claim {
        text-style: bold;
        color: $text;
    }

    .fact-evidence {
        color: $text-muted;
        margin: 1 0 0 0;
    }

    .fact-metadata {
        color: $accent;
        text-style: italic;
        margin: 1 0 0 0;
    }

    Input {
        border: solid $primary;
        padding: 0 1;
    }

    Button {
        border: solid $primary;
        background: $primary;
        color: $text;
        margin: 0 1;
    }

    Button:hover {
        background: $accent;
    }

    ProgressBar {
        background: $panel;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("ctrl+h", "go_home", "Home"),
        Binding("ctrl+q", "go_query", "Query"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("colon", "command_palette", "Command", key_display=":"),
    ]

    SCREENS = {"home": HomeScreen}

    def __init__(self):
        super().__init__()
        self.state = AppState()

    def on_mount(self) -> None:
        """Initialize the app when mounted."""
        self.title = "frfr - Document Q&A"
        self.sub_title = "Press ? for help"

        # Load available sessions
        self.state.load_sessions()

        # Show home screen
        self.push_screen("home")

    def compose(self) -> ComposeResult:
        """Compose the app layout."""
        yield Header()
        yield Footer()

    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    def action_go_home(self) -> None:
        """Go to home screen."""
        self.pop_screen()
        self.push_screen("home")

    def action_go_query(self) -> None:
        """Go to query screen."""
        if self.state.current_session:
            # TODO: Implement query screen
            self.notify("Query screen coming soon!", severity="information")
        else:
            self.notify("No session selected", severity="warning")

    def action_search(self) -> None:
        """Show search/filter interface."""
        # TODO: Implement search
        self.notify("Search coming soon!", severity="information")

    def action_command_palette(self) -> None:
        """Show command palette."""
        # TODO: Implement command palette
        self.notify("Command palette coming soon!", severity="information")


def run_tui() -> None:
    """Run the TUI application."""
    app = FrfrApp()
    app.run()
