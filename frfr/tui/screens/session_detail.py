"""Session detail screen showing documents and session info."""

from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, DataTable, Label
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from rich.text import Text

from frfr.tui.state import SessionInfo


class SessionDetailScreen(Screen):
    """Screen showing details of a specific session."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("enter", "view_facts", "View Facts"),
        Binding("i", "query_session", "Query"),
        Binding("a", "add_document", "Add Document"),
        Binding("p", "reprocess_document", "Reprocess Document"),
        Binding("e", "enrich_facts", "Enrich Facts"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, session_info: SessionInfo):
        super().__init__()
        self.session_info = session_info

    def compose(self) -> ComposeResult:
        """Compose the session detail layout."""
        with Container():
            with Vertical():
                yield Static(
                    f"[bold]{self.session_info.name}[/bold]",
                    classes="title"
                )
                with Horizontal():
                    with Vertical(id="left-panel"):
                        yield Label("[bold]Session Info[/bold]")
                        yield Static(self._format_session_info(), id="session-info")
                        yield Label("\n[bold]Commands[/bold]")
                        yield Static(self._build_commands_text(), id="commands-panel")
                    with Vertical(id="right-panel"):
                        yield Label("[bold]Documents[/bold]")
                        yield DataTable(id="documents-table")

    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        table = self.query_one("#documents-table", DataTable)

        # Setup table columns
        table.add_columns(
            "Document Name",
            "Status",
            "Facts",
            "Text File",
        )

        # Populate documents table
        self.refresh_documents_table()

        # Enable cursor and focus
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.focus()

    def on_screen_resume(self) -> None:
        """Called when returning to this screen from another screen."""
        # Refresh session data when returning from processing/recovery screens
        self.action_refresh()

    def _format_session_info(self) -> str:
        """Format session information for display."""
        lines = []
        lines.append(f"[cyan]Session ID:[/cyan] {self.session_info.session_id}")
        lines.append(f"[cyan]Created:[/cyan] {self.session_info.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"[cyan]Status:[/cyan] {self.session_info.status}")
        lines.append(f"[cyan]Documents:[/cyan] {self.session_info.document_count}")
        lines.append(f"[cyan]Total Facts:[/cyan] {self.session_info.total_facts}")
        return "\n".join(lines)

    def _build_commands_text(self) -> str:
        """Build the commands help text."""
        commands = [
            "[cyan]↑/↓[/cyan]    Navigate",
            "[cyan]Enter[/cyan]  View facts",
            "[cyan]i[/cyan]      Query session",
            "[cyan]a[/cyan]      Add document",
            "[cyan]p[/cyan]      Reprocess doc",
            "[cyan]e[/cyan]      Enrich facts",
            "[cyan]r[/cyan]      Refresh",
            "",
            "[cyan]Esc[/cyan]    Back",
            "[cyan]?[/cyan]      Help",
        ]
        return "\n".join(commands)

    def refresh_documents_table(self) -> None:
        """Refresh the documents table."""
        table = self.query_one("#documents-table", DataTable)
        table.clear()

        # Add documents to table
        for doc in self.session_info.documents:
            doc_name = doc.get("original_pdf_path", "Unknown")
            if isinstance(doc_name, str):
                # Extract just the filename
                from pathlib import Path
                doc_name = Path(doc_name).name

            # Format status with color
            status = doc.get("status", "unknown")
            status_text = Text(status)
            if status == "completed":
                status_text.stylize("green")
            elif status == "processing":
                status_text.stylize("yellow")
            elif status == "failed":
                status_text.stylize("red")

            # Count facts (if available)
            # Facts file path is relative to project root, not session dir
            facts_file_path = doc.get("facts_file", "")
            fact_count = 0
            if facts_file_path:
                facts_file = Path(facts_file_path)
                if facts_file.exists():
                    try:
                        import json
                        with open(facts_file) as f:
                            facts_data = json.load(f)
                            # Handle nested structure
                            if "documents" in facts_data:
                                for nested_doc_data in facts_data.get("documents", {}).values():
                                    fact_count += len(nested_doc_data.get("facts", []))
                            else:
                                fact_count = len(facts_data.get("facts", []))
                    except Exception:
                        pass

            # Text file path
            text_file = doc.get("text_file", "N/A")

            table.add_row(
                doc_name,
                status_text,
                str(fact_count),
                text_file,
                key=doc_name,
            )

    def action_go_back(self) -> None:
        """Go back to the home screen."""
        self.app.pop_screen()

    def action_view_facts(self) -> None:
        """View facts for the selected document."""
        table = self.query_one("#documents-table", DataTable)

        if table.cursor_row is None:
            # No specific document selected, show all facts
            from frfr.tui.screens.facts_browser import FactsBrowserScreen
            self.app.push_screen(FactsBrowserScreen(self.session_info.session_id))
            return

        # Get the document by index
        try:
            doc = self.session_info.documents[table.cursor_row]
            # Use the document registry key (e.g., "test-doc" not "test-doc.pdf")
            doc_key = doc.get("_doc_key")
            if not doc_key:
                self.app.notify("Document key not found", severity="error")
                return
        except (IndexError, KeyError):
            self.app.notify("Could not find document", severity="error")
            return

        # Navigate to facts browser for this document
        from frfr.tui.screens.facts_browser import FactsBrowserScreen
        self.app.push_screen(FactsBrowserScreen(self.session_info.session_id, doc_key))

    def action_query_session(self) -> None:
        """Open query interface for this session."""
        # Navigate to query screen
        from frfr.tui.screens.query import QueryScreen
        self.app.push_screen(QueryScreen(self.session_info.session_id))

    def action_add_document(self) -> None:
        """Add documents to this session."""
        from frfr.tui.screens.add_document import AddDocumentScreen
        from frfr.tui.screens.processing import ProcessingScreen

        def handle_file_selection(file_paths):
            """Handle the file paths returned from the dialog."""
            if file_paths:
                # Show processing screen
                self.app.push_screen(ProcessingScreen(
                    file_paths=file_paths,
                    session_id=self.session_info.session_id,
                    is_new_session=False
                ))

        # Show the file selection dialog with callback
        self.app.push_screen(
            AddDocumentScreen(self.session_info.session_id),
            handle_file_selection
        )

    def action_reprocess_document(self) -> None:
        """Reprocess the selected document."""
        from frfr.tui.screens.processing import ProcessingScreen
        from frfr.tui.screens.resume_dialog import ResumeDialog
        from frfr.progress import get_progress_summary

        table = self.query_one("#documents-table", DataTable)

        if table.cursor_row is None:
            self.app.notify("No document selected", severity="warning")
            return

        # Get the document by index
        try:
            doc = self.session_info.documents[table.cursor_row]
            original_pdf_path = doc.get("original_pdf_path")
            doc_key = doc.get("_doc_key")

            if not original_pdf_path:
                self.app.notify("Could not find PDF path", severity="error")
                return

            if not doc_key:
                self.app.notify("Could not find document key", severity="error")
                return

            doc_name = Path(original_pdf_path).name if isinstance(original_pdf_path, str) else "document"

            # Check for incomplete chunks
            session_dir = Path(".frfr_sessions") / self.session_info.session_id
            progress_summary = get_progress_summary(session_dir, doc_key)

            if progress_summary and progress_summary["incomplete"] > 0:
                # Show resume dialog for incomplete chunks
                def handle_resume_choice(choice):
                    """Handle the user's choice from the resume dialog."""
                    if choice is None:
                        # User cancelled
                        return

                    resume_mode = (choice == "resume")
                    mode_text = "Resuming" if resume_mode else "Reprocessing"
                    self.app.notify(f"{mode_text} {doc_name}...", severity="information")

                    # Show processing screen
                    self.app.push_screen(ProcessingScreen(
                        file_paths=[original_pdf_path],
                        session_id=self.session_info.session_id,
                        is_new_session=False,
                        resume_incomplete=resume_mode
                    ))

                # Show the resume dialog
                self.app.push_screen(
                    ResumeDialog(
                        document_name=doc_name,
                        total_chunks=progress_summary["total"],
                        completed_chunks=progress_summary["completed"],
                        incomplete_chunks=progress_summary["incomplete"]
                    ),
                    handle_resume_choice
                )
            elif progress_summary and progress_summary["incomplete"] == 0 and progress_summary["total"] > 0:
                # All chunks completed - do full reprocess from scratch
                self.app.notify(f"Reprocessing {doc_name} from scratch...", severity="information")

                # Don't use resume mode - do a full reprocess
                self.app.push_screen(ProcessingScreen(
                    file_paths=[original_pdf_path],
                    session_id=self.session_info.session_id,
                    is_new_session=False,
                    resume_incomplete=False  # Full reprocess, not resume
                ))
            else:
                # No progress file - normal reprocess
                self.app.notify(f"Reprocessing {doc_name}...", severity="information")

                # Show processing screen to reprocess this document
                self.app.push_screen(ProcessingScreen(
                    file_paths=[original_pdf_path],
                    session_id=self.session_info.session_id,
                    is_new_session=False
                ))

        except (IndexError, KeyError) as e:
            self.app.notify(f"Could not find document: {str(e)}", severity="error")
            return

    def action_enrich_facts(self) -> None:
        """Enrich facts by recovering near matches with LLM."""
        from frfr.tui.screens.recovery import RecoveryScreen

        table = self.query_one("#documents-table", DataTable)

        # If a document is selected, enrich just that document; otherwise enrich all
        document_name = None
        if table.cursor_row is not None:
            try:
                doc = self.session_info.documents[table.cursor_row]
                document_name = doc.get("_doc_key")
            except (IndexError, KeyError):
                pass

        if document_name:
            self.app.notify(f"Enriching facts for {document_name}...", severity="information")
        else:
            self.app.notify(f"Enriching all facts in session...", severity="information")

        # Show recovery screen
        self.app.push_screen(RecoveryScreen(
            session_id=self.session_info.session_id,
            document_name=document_name
        ))

    def action_refresh(self) -> None:
        """Refresh the session data."""
        # Reload session info from disk
        from frfr.tui.state import SessionInfo
        self.session_info = SessionInfo.from_metadata_file(self.session_info.session_dir)
        if self.session_info:
            self.refresh_documents_table()
            info_widget = self.query_one("#session-info", Static)
            info_widget.update(self._format_session_info())
            self.app.notify("Session refreshed", severity="success")
        else:
            self.app.notify("Failed to refresh session", severity="error")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the documents table."""
        self.action_view_facts()
