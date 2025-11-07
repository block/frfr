"""New session creation dialog."""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding

from frfr.tui.widgets import PathInput


class NewSessionScreen(ModalScreen[Optional[list]]):
    """Modal dialog for creating a new session with PDF files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    NewSessionScreen {
        align: center middle;
    }

    #dialog {
        width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 2;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container(id="dialog"):
            yield Label("[bold cyan]Create New Session[/bold cyan]")
            yield Static("\n[bold]Enter PDF file paths:[/bold]")
            yield Static("[dim]Press Tab for path autocomplete[/dim]")
            yield Static("[dim]Examples:[/dim]")
            yield Static("[dim]  documents/report.pdf[/dim]")
            yield Static("[dim]  /absolute/path/to/file.pdf[/dim]")
            yield Static("[dim]  documents/*.pdf (glob pattern)[/dim]\n")

            yield Label("PDF Files:")
            yield PathInput(
                placeholder="Enter file path or pattern...",
                id="file-input-1"
            )
            yield PathInput(
                placeholder="Additional file (optional)...",
                id="file-input-2"
            )
            yield PathInput(
                placeholder="Additional file (optional)...",
                id="file-input-3"
            )

            yield Static("", id="error-message")

            with Horizontal(id="buttons"):
                yield Button("Create & Process", variant="primary", id="create-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Initialize the dialog when mounted."""
        # Focus the first input
        file_input = self.query_one("#file-input-1", PathInput)
        file_input.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "create-btn":
            self.action_create()

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)

    def action_create(self) -> None:
        """Create the session with the provided files."""
        # Clear any previous error
        error_msg = self.query_one("#error-message", Static)
        error_msg.update("")

        # Collect file paths from inputs
        file_paths = []

        for i in range(1, 4):
            try:
                file_input = self.query_one(f"#file-input-{i}", PathInput)
                path_str = file_input.value.strip()

                if path_str:
                    # Expand user home directory
                    import os
                    path_str = os.path.expanduser(path_str)

                    # Handle glob patterns
                    if "*" in path_str:
                        from glob import glob
                        expanded = glob(path_str)
                        file_paths.extend(expanded)
                    else:
                        file_paths.append(path_str)
            except Exception as e:
                error_msg.update(f"[red]Error reading input {i}: {str(e)}[/red]")
                return

        # Validate that at least one file was provided
        if not file_paths:
            error_msg.update("[red]Please enter at least one PDF file path[/red]")
            return

        # Validate that files exist
        missing_files = []
        valid_files = []

        for path_str in file_paths:
            path = Path(path_str)
            if not path.exists():
                missing_files.append(path_str)
            elif not path.is_file():
                missing_files.append(f"{path_str} (not a file)")
            elif not path.suffix.lower() == '.pdf':
                missing_files.append(f"{path_str} (not a PDF)")
            else:
                valid_files.append(str(path.absolute()))

        if missing_files:
            error_msg = self.query_one("#error-message", Static)
            error_msg.update(
                f"[red]Invalid files:[/red]\n" + "\n".join(f"  • {f}" for f in missing_files[:3])
            )
            return

        # Return the valid file paths
        self.dismiss(valid_files)
