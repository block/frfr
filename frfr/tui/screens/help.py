"""Help screen showing keybindings and application info."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Container, VerticalScroll
from textual.binding import Binding
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown


class HelpScreen(Screen):
    """Help screen with keybindings and usage information."""

    BINDINGS = [
        Binding("escape", "close", "Close Help", priority=True),
        Binding("q", "close", "Close Help", priority=True),
    ]

    def compose(self) -> ComposeResult:
        """Compose the help screen layout."""
        with Container():
            yield Static("[bold cyan]Frfr TUI - Help[/bold cyan]", classes="title")
            with VerticalScroll():
                yield Static(self._build_help_content())

    def _build_help_content(self) -> str:
        """Build the help content with keybindings and information."""
        content = []

        # App Overview
        content.append("\n[bold yellow]About Frfr TUI[/bold yellow]")
        content.append("─" * 60)
        content.append(
            "Terminal User Interface for browsing extracted facts from documents."
        )
        content.append(
            "Navigate sessions, search facts, and query your document collection.\n"
        )

        # Global Keybindings
        content.append("\n[bold yellow]Global Keybindings[/bold yellow]")
        content.append("─" * 60)
        self._add_keybinding(content, "?", "Show this help screen")
        self._add_keybinding(content, "Ctrl+c", "Quit application")
        self._add_keybinding(content, "Ctrl+h", "Go to home screen")
        self._add_keybinding(content, "Ctrl+q", "Go to query screen (if session selected)")
        self._add_keybinding(content, "/", "Search/filter (coming soon)")
        self._add_keybinding(content, ":", "Command palette (coming soon)")

        # Home Screen
        content.append("\n[bold yellow]Home Screen (Session Browser)[/bold yellow]")
        content.append("─" * 60)
        self._add_keybinding(content, "Enter", "Open selected session")
        self._add_keybinding(content, "n", "Create new session (coming soon)")
        self._add_keybinding(content, "d", "Delete selected session")
        self._add_keybinding(content, "r", "Refresh session list")
        self._add_keybinding(content, "↑/↓", "Navigate session list")

        # Session Detail Screen
        content.append("\n[bold yellow]Session Detail Screen[/bold yellow]")
        content.append("─" * 60)
        self._add_keybinding(content, "Enter", "View facts for selected document")
        self._add_keybinding(content, "i", "Open query interface for session")
        self._add_keybinding(content, "a", "Add documents to session")
        self._add_keybinding(content, "p", "Reprocess selected document")
        self._add_keybinding(content, "e", "Enrich facts (recover near matches with LLM)")
        self._add_keybinding(content, "r", "Refresh session data")
        self._add_keybinding(content, "Escape", "Return to home screen")
        self._add_keybinding(content, "↑/↓", "Navigate document list")

        # Facts Browser Screen
        content.append("\n[bold yellow]Facts Browser Screen[/bold yellow]")
        content.append("─" * 60)
        self._add_keybinding(content, "Enter", "View detailed fact information")
        self._add_keybinding(content, "/", "Focus search input")
        self._add_keybinding(content, "f", "Toggle filters (coming soon)")
        self._add_keybinding(content, "Escape", "Return to previous screen")
        self._add_keybinding(content, "↑/↓", "Navigate fact list")

        # Query Screen
        content.append("\n[bold yellow]Query Screen[/bold yellow]")
        content.append("─" * 60)
        self._add_keybinding(content, "Ctrl+Enter", "Submit query")
        self._add_keybinding(content, "↑", "Previous query in history")
        self._add_keybinding(content, "↓", "Next query in history")
        self._add_keybinding(content, "Escape", "Return to previous screen")

        # Navigation Tips
        content.append("\n[bold yellow]Navigation Tips[/bold yellow]")
        content.append("─" * 60)
        content.append("  • Use [cyan]Tab[/cyan] to cycle through interactive elements")
        content.append("  • Use [cyan]Shift+Tab[/cyan] to cycle backwards")
        content.append("  • Use [cyan]Escape[/cyan] to go back to previous screen")
        content.append("  • Most screens support [cyan]arrow keys[/cyan] for navigation")

        # Workflow
        content.append("\n[bold yellow]Typical Workflow[/bold yellow]")
        content.append("─" * 60)
        content.append("  1. [cyan]Home Screen[/cyan]: Browse and select a session")
        content.append("  2. [cyan]Session Detail[/cyan]: View documents in the session")
        content.append("  3. [cyan]Facts Browser[/cyan]: Search and filter extracted facts")
        content.append("  4. [cyan]Query Screen[/cyan]: Ask questions about your facts")

        # Additional Information
        content.append("\n[bold yellow]Additional Information[/bold yellow]")
        content.append("─" * 60)
        content.append("  • Sessions are stored in [cyan].frfr_sessions/[/cyan]")
        content.append("  • Facts are validated against source documents")
        content.append("  • Use [cyan]frfr --help[/cyan] for CLI options")
        content.append("  • See docs at [cyan]docs/DOCS_INDEX.md[/cyan] for more info")

        # Footer
        content.append("\n")
        content.append("─" * 60)
        content.append("[dim]Press Escape or q to close this help screen[/dim]")
        content.append("\n")

        return "\n".join(content)

    def _add_keybinding(self, content: list, key: str, description: str) -> None:
        """Add a formatted keybinding line to content."""
        content.append(f"  [cyan]{key:15s}[/cyan] {description}")

    def action_close(self) -> None:
        """Close the help screen."""
        self.app.pop_screen()
