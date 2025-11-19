"""Add document to session dialog."""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, Label
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding


class AddDocumentScreen(ModalScreen[Optional[list]]):
    """Modal dialog for adding documents to an existing session."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    AddDocumentScreen {
        align: center middle;
    }

    #dialog {
        width: 80;
        height: auto;
        max-height: 40;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #selected-files-container {
        height: auto;
        max-height: 15;
        border: solid $accent;
        padding: 1;
        margin: 1 0;
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

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.selected_files: list[str] = []

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container(id="dialog"):
            yield Label(f"[bold cyan]Add Documents to Session[/bold cyan]")
            yield Static(f"\n[dim]Session: {self.session_id}[/dim]\n")
            yield Static("[bold]Select files to add:[/bold]")
            yield Static("[dim]Click 'Browse Files' to open your system's file picker.[/dim]")
            yield Static("[dim]Accepts PDF, TXT, and Markdown files. You can select multiple at once.[/dim]\n")

            yield Button("Browse Files...", variant="primary", id="browse-btn")

            yield Label("\n[bold]Selected Files:[/bold]")
            with ScrollableContainer(id="selected-files-container"):
                yield Static("[dim]No files selected[/dim]", id="selected-files")

            yield Static("", id="error-message")

            with Horizontal(id="buttons"):
                yield Button("Add & Process", variant="primary", id="add-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Initialize the dialog when mounted."""
        # Focus the browse button
        browse_btn = self.query_one("#browse-btn", Button)
        browse_btn.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "add-btn":
            self.action_add()
        elif event.button.id == "browse-btn":
            self.run_worker(self.action_browse(), exclusive=False)

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)

    async def action_browse(self) -> None:
        """Open system file picker to select PDF files."""
        from frfr.tui.utils.file_picker import open_file_picker

        try:
            # Show notification that dialog is opening
            self.app.notify("Opening file picker...", severity="information")

            # Open native file picker
            file_paths = await open_file_picker(
                title="Add Documents to Session",
                file_types=[("Documents", "*.pdf;*.txt;*.md"), ("All files", "*.*")],
                multiple=True,
                initial_dir=str(Path.home())
            )

            if file_paths:
                self.selected_files = file_paths
                self._update_selected_display()

                # Show notification
                self.app.notify(
                    f"Selected {len(file_paths)} file{'s' if len(file_paths) != 1 else ''}",
                    severity="success"
                )
            else:
                # User cancelled
                self.app.notify("File selection cancelled", severity="information")

        except Exception as e:
            self.app.notify(f"Error opening file picker: {e}", severity="error")

    def _update_selected_display(self) -> None:
        """Update the display of selected files."""
        selected_display = self.query_one("#selected-files", Static)

        if not self.selected_files:
            selected_display.update("[dim]No files selected[/dim]")
        else:
            # Show file names with paths
            file_list = "\n".join(
                f"• {Path(path).name}" for path in self.selected_files
            )
            selected_display.update(file_list)

    def action_add(self) -> None:
        """Add documents to the session."""
        # Clear any previous error
        error_msg = self.query_one("#error-message", Static)
        error_msg.update("")

        # Validate that at least one file was provided
        if not self.selected_files:
            error_msg.update("[red]Please select at least one file[/red]")
            return

        # Validate that files exist and have valid extensions
        missing_files = []
        valid_files = []
        allowed_extensions = {'.pdf', '.txt', '.md', '.markdown'}

        for path_str in self.selected_files:
            path = Path(path_str)
            if not path.exists():
                missing_files.append(path_str)
            elif not path.is_file():
                missing_files.append(f"{path_str} (not a file)")
            elif path.suffix.lower() not in allowed_extensions:
                missing_files.append(f"{path_str} (unsupported format)")
            else:
                valid_files.append(str(path.absolute()))

        if missing_files:
            error_msg.update(
                f"[red]Invalid files:[/red]\n" + "\n".join(f"  • {f}" for f in missing_files[:3])
            )
            return

        # Return the valid file paths
        self.dismiss(valid_files)
