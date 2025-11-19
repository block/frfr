"""Delete session confirmation dialog."""

from typing import Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label
from textual.containers import Container, Horizontal
from textual.binding import Binding


class DeleteConfirmDialog(ModalScreen[bool]):
    """Modal dialog for confirming session deletion."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    DeleteConfirmDialog {
        align: center middle;
    }

    #dialog {
        width: 70;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }

    #warning {
        width: 100%;
        height: auto;
        padding: 1 0;
        background: $error;
        border: solid $error;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1 0;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        session_name: str,
        document_count: int
    ):
        super().__init__()
        self.session_name = session_name
        self.document_count = document_count

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container(id="dialog"):
            yield Label("[bold red]⚠️  Delete Session?[/bold red]")
            yield Static(
                f"\n[dim]You are about to delete:[/dim]\n"
                f"[bold]{self.session_name}[/bold]\n"
            )

            if self.document_count > 0:
                yield Static(
                    f"[yellow]This session contains {self.document_count} document(s)[/yellow]\n"
                )

            with Container(id="warning"):
                yield Static(
                    "[bold]This will permanently delete:[/bold]\n"
                    "  • Session directory and metadata\n"
                    "  • All extracted facts and summaries\n"
                    "  • Associated text files and symlinks\n"
                    "  • [green]Original PDFs will NOT be deleted[/green]\n"
                )

            yield Static(
                "\n[bold red]This action cannot be undone![/bold red]\n"
            )

            with Horizontal(id="buttons"):
                yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Cancel", variant="primary", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(False)
        elif event.button.id == "delete-btn":
            self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(False)
