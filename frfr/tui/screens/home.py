"""Home screen showing all available sessions."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import DataTable, Static
from textual.containers import Container, VerticalScroll, Vertical, Horizontal
from textual.binding import Binding
from rich.text import Text

from frfr.tui.state import SessionInfo


class HomeScreen(Screen):
    """Home screen with session browser."""

    BINDINGS = [
        Binding("enter", "select_session", "Open Session"),
        Binding("n", "new_session", "New Session"),
        Binding("d", "delete_session", "Delete Session"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the home screen layout."""
        with Container():
            yield Static("[bold]Session Browser[/bold]", classes="title")
            with Horizontal():
                # Left panel: Commands
                with Vertical(id="left-panel"):
                    yield Static(self._build_commands_text(), id="commands-panel")

                # Right panel: Sessions table
                with Vertical(id="right-panel"):
                    yield DataTable(id="sessions-table")

    def _build_commands_text(self) -> str:
        """Build the commands help text."""
        commands = [
            "[bold cyan]Commands[/bold cyan]",
            "",
            "[cyan]↑/↓[/cyan]    Navigate",
            "[cyan]Enter[/cyan]  Open session",
            "[cyan]n[/cyan]      New session",
            "[cyan]r[/cyan]      Refresh list",
            "",
            "[cyan]?[/cyan]      Help",
            "[cyan]q[/cyan]      Quit",
        ]
        return "\n".join(commands)

    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        table = self.query_one("#sessions-table", DataTable)

        # Setup table columns
        table.add_columns(
            "Session Name",
            "Documents",
            "Facts",
            "Status",
            "Created",
        )

        # Populate table with sessions
        self.refresh_table()

        # Enable cursor and focus
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.focus()

    def refresh_table(self) -> None:
        """Refresh the sessions table."""
        table = self.query_one("#sessions-table", DataTable)
        table.clear()

        # Reload sessions from disk
        self.app.state.load_sessions()

        # Add sessions to table
        for session_info in self.app.state.sessions:
            # Format status with color
            status_text = Text(session_info.status)
            if session_info.status == "completed":
                status_text.stylize("green")
            elif session_info.status == "processing":
                status_text.stylize("yellow")
            elif session_info.status == "failed":
                status_text.stylize("red")

            # Format date
            date_str = session_info.created_at.strftime("%Y-%m-%d %H:%M")

            table.add_row(
                session_info.name,
                str(session_info.document_count),
                str(session_info.total_facts),
                status_text,
                date_str,
                key=session_info.session_id,
            )

        if len(self.app.state.sessions) == 0:
            self.app.notify("No sessions found. Press 'n' to create one.", severity="information")

    def action_select_session(self) -> None:
        """Open the selected session."""
        table = self.query_one("#sessions-table", DataTable)

        # Check if there are any sessions
        if len(self.app.state.sessions) == 0:
            self.app.notify("No sessions available", severity="warning")
            return

        # Check if cursor is positioned
        if table.cursor_row is None or table.cursor_row < 0:
            self.app.notify("No session selected", severity="warning")
            return

        # Get the session directly by index since we know the order
        try:
            session_info = self.app.state.sessions[table.cursor_row]
        except IndexError:
            self.app.notify(f"Invalid session index: {table.cursor_row}", severity="error")
            return

        # Load the session
        session = self.app.state.load_session(session_info.session_id)
        if session:
            self.app.notify(f"Loaded session: {session_info.name}", severity="success")
            # Navigate to session detail screen
            from frfr.tui.screens.session_detail import SessionDetailScreen
            self.app.push_screen(SessionDetailScreen(session_info))
        else:
            self.app.notify(f"Failed to load session: {session_info.session_id}", severity="error")

    def action_new_session(self) -> None:
        """Create a new session."""
        from frfr.tui.screens.new_session import NewSessionScreen
        from frfr.tui.screens.processing import ProcessingScreen

        def handle_file_selection(file_paths):
            """Handle the file paths returned from the dialog."""
            if file_paths:
                # Show processing screen
                self.app.push_screen(ProcessingScreen(
                    file_paths=file_paths,
                    is_new_session=True
                ))

                # Refresh the table when we return to this screen
                self.set_timer(0.5, self.refresh_table)

        # Show the file selection dialog with callback
        self.app.push_screen(NewSessionScreen(), handle_file_selection)

    def action_delete_session(self) -> None:
        """Delete the selected session."""
        table = self.query_one("#sessions-table", DataTable)

        if table.cursor_row is None:
            self.app.notify("No session selected", severity="warning")
            return

        # TODO: Implement session deletion with confirmation
        self.app.notify("Session deletion coming soon!", severity="information")

    def action_refresh(self) -> None:
        """Refresh the sessions list."""
        self.refresh_table()
        self.app.notify("Sessions refreshed", severity="success")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the sessions table."""
        self.action_select_session()
