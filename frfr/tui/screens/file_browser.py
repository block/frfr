"""File browser for selecting PDF documents."""

from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Static, Button, DirectoryTree, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding


class PDFDirectoryTree(DirectoryTree):
    """DirectoryTree that highlights PDF files."""

    def filter_paths(self, paths):
        """Filter to show all directories and PDF files."""
        return [
            path for path in paths
            if path.is_dir() or path.suffix.lower() == '.pdf'
        ]


class FileBrowserScreen(ModalScreen[Optional[list]]):
    """Modal file browser for selecting PDF files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("space", "toggle_selection", "Select/Deselect"),
        Binding("a", "select_all", "Select All PDFs"),
        Binding("c", "clear_selection", "Clear Selection"),
    ]

    CSS = """
    FileBrowserScreen {
        align: center middle;
    }

    #dialog {
        width: 90;
        height: 35;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #tree-container {
        height: 1fr;
        border: solid $primary;
        margin: 1 0;
    }

    #selected-files {
        height: 6;
        border: solid $accent;
        padding: 0 1;
        margin: 1 0;
        overflow-y: auto;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 2;
    }

    DirectoryTree {
        height: 100%;
    }
    """

    def __init__(self, start_path: Optional[Path] = None):
        super().__init__()
        self.start_path = start_path or Path.cwd()
        self.selected_files: set[Path] = set()

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        with Container(id="dialog"):
            yield Label("[bold cyan]Browse PDF Files[/bold cyan]")
            yield Static(
                "[dim]Navigate: ↑/↓  Expand: →  Collapse: ←  Select: Space[/dim]\n"
                "[dim]Select All: a  Clear: c  Confirm: Enter  Cancel: Esc[/dim]"
            )

            with Container(id="tree-container"):
                yield PDFDirectoryTree(str(self.start_path))

            yield Label("[bold]Selected Files:[/bold]")
            yield Static("", id="selected-files")

            with Horizontal(id="buttons"):
                yield Button("Confirm Selection", variant="primary", id="confirm-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        """Initialize the dialog when mounted."""
        tree = self.query_one(DirectoryTree)
        tree.focus()
        tree.show_root = True

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in the tree."""
        path = event.path

        # Only handle PDF files
        if path.suffix.lower() == '.pdf':
            if path in self.selected_files:
                self.selected_files.remove(path)
            else:
                self.selected_files.add(path)

            self._update_selected_display()

    def action_toggle_selection(self) -> None:
        """Toggle selection of the currently highlighted file."""
        tree = self.query_one(DirectoryTree)
        node = tree.cursor_node

        if node and node.data and hasattr(node.data, 'path'):
            path = node.data.path
            if isinstance(path, Path) and path.suffix.lower() == '.pdf':
                if path in self.selected_files:
                    self.selected_files.remove(path)
                else:
                    self.selected_files.add(path)

                self._update_selected_display()

    def action_select_all(self) -> None:
        """Select all PDF files in the current directory."""
        tree = self.query_one(DirectoryTree)
        node = tree.cursor_node

        if node and node.data and hasattr(node.data, 'path'):
            current_path = node.data.path
            if isinstance(current_path, Path):
                # If it's a directory, select all PDFs in it
                search_dir = current_path if current_path.is_dir() else current_path.parent

                for pdf_file in search_dir.glob("*.pdf"):
                    self.selected_files.add(pdf_file)

                self._update_selected_display()
                self.app.notify(f"Selected all PDFs in {search_dir.name}", severity="information")

    def action_clear_selection(self) -> None:
        """Clear all selected files."""
        self.selected_files.clear()
        self._update_selected_display()
        self.app.notify("Selection cleared", severity="information")

    def _update_selected_display(self) -> None:
        """Update the display of selected files."""
        selected_display = self.query_one("#selected-files", Static)

        if not self.selected_files:
            selected_display.update("[dim]No files selected[/dim]")
        else:
            # Show file names only (not full paths)
            file_list = "\n".join(
                f"• {path.name}" for path in sorted(self.selected_files)
            )
            selected_display.update(file_list)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel-btn":
            self.action_cancel()
        elif event.button.id == "confirm-btn":
            self.action_confirm()

    def action_cancel(self) -> None:
        """Cancel the dialog."""
        self.dismiss(None)

    def action_confirm(self) -> None:
        """Confirm selection and return files."""
        if not self.selected_files:
            error_display = self.query_one("#selected-files", Static)
            error_display.update("[red]Please select at least one PDF file[/red]")
            return

        # Return list of absolute path strings
        self.dismiss([str(path.absolute()) for path in sorted(self.selected_files)])
