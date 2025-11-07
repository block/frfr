"""Resume processing dialog."""

from typing import Optional, Literal

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding


ResumeChoice = Literal["resume", "restart"]


class ResumeDialog(ModalScreen[Optional[ResumeChoice]]):
    """Modal dialog for choosing resume or restart for incomplete processing."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    ResumeDialog {
        align: center middle;
    }

    #dialog {
        width: 70;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #stats {
        width: 100%;
        height: auto;
        padding: 1 0;
        background: $boost;
        border: solid $primary;
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
        document_name: str,
        total_chunks: int,
        completed_chunks: int,
        incomplete_chunks: int
    ):
        super().__init__()
        self.document_name = document_name
        self.total_chunks = total_chunks
        self.completed_chunks = completed_chunks
        self.incomplete_chunks = incomplete_chunks

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container(id="dialog"):
            yield Label("[bold cyan]Resume Processing?[/bold cyan]")
            yield Static(
                f"\n[dim]Incomplete processing run detected for:[/dim]\n"
                f"[bold]{self.document_name}[/bold]\n"
            )

            with Vertical(id="stats"):
                yield Static(
                    f"  [cyan]Total chunks:[/cyan] {self.total_chunks}\n"
                    f"  [green]Completed:[/green] {self.completed_chunks} ✓\n"
                    f"  [yellow]Incomplete:[/yellow] {self.incomplete_chunks}\n"
                )

            yield Static(
                "\n[bold]What would you like to do?[/bold]\n"
                "[dim]Resume will only process the incomplete chunks.[/dim]\n"
                "[dim]Start Over will reprocess all chunks from scratch.[/dim]\n"
            )

            with Horizontal(id="buttons"):
                yield Button(
                    f"Resume ({self.incomplete_chunks} chunks)",
                    variant="primary",
                    id="resume-btn"
                )
                yield Button(
                    f"Start Over ({self.total_chunks} chunks)",
                    variant="default",
                    id="restart-btn"
                )
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "resume-btn":
            self.dismiss("resume")
        elif event.button.id == "restart-btn":
            self.dismiss("restart")

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)
