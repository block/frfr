"""Query interface screen for asking questions about facts."""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Button, RichLog, Label, LoadingIndicator
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual.worker import Worker, WorkerState
from rich.markdown import Markdown


class QueryScreen(Screen):
    """Screen for querying facts with natural language questions."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("ctrl+enter", "submit_query", "Submit Query"),
        Binding("up", "history_prev", "Previous Query"),
        Binding("down", "history_next", "Next Query"),
    ]

    CSS = """
    #query-loading {
        width: auto;
        height: 1;
        padding: 0 1;
    }

    #query-status {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, session_id: str, facts_file: Optional[Path] = None):
        super().__init__()
        self.session_id = session_id
        self.facts_file = facts_file
        self.query_history: List[str] = []
        self.history_index = -1

    def compose(self) -> ComposeResult:
        """Compose the query interface layout."""
        with Container():
            yield Static("[bold]Query Interface[/bold]", classes="title")
            with Horizontal():
                # Left panel: Commands and info
                with Vertical(id="left-panel"):
                    yield Label("[bold]Info[/bold]")
                    yield Static(
                        "Ask questions about\nthe facts in this\nsession.",
                        id="query-help"
                    )
                    yield Label("\n[bold]Commands[/bold]")
                    yield Static(self._build_commands_text(), id="commands-panel")

                # Right panel: Query interface
                with Vertical(id="right-panel"):
                    with Horizontal():
                        yield Input(placeholder="Ask a question...", id="query-input")
                        yield Button("Submit", id="submit-button", variant="primary")
                    with Horizontal():
                        yield LoadingIndicator(id="query-loading")
                        yield Static("", id="query-status")
                    yield RichLog(id="query-results", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        # Focus the input
        query_input = self.query_one("#query-input", Input)
        query_input.focus()

        # Hide loading indicator initially
        loading = self.query_one("#query-loading", LoadingIndicator)
        loading.display = False

        # Show welcome message
        results_log = self.query_one("#query-results", RichLog)
        results_log.write("[bold cyan]Welcome to the Query Interface[/bold cyan]")
        results_log.write("[dim]Type your question and press Ctrl+Enter to submit.[/dim]\n")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "submit-button":
            self.action_submit_query()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "query-input":
            self.action_submit_query()

    def action_submit_query(self) -> None:
        """Submit the query."""
        query_input = self.query_one("#query-input", Input)
        query = query_input.value.strip()

        if not query:
            self.app.notify("Please enter a question", severity="warning")
            return

        # Add to history
        self.query_history.append(query)
        self.history_index = len(self.query_history)

        # Clear input
        query_input.value = ""

        # Show query in results
        results_log = self.query_one("#query-results", RichLog)
        results_log.write(f"\n[bold]Q: {query}[/bold]")

        # Run query in worker
        self.run_query_worker(query)

    def run_query_worker(self, query: str) -> None:
        """Run query in a background worker."""
        status_widget = self.query_one("#query-status", Static)
        status_widget.update("Searching facts and generating answer...")

        # Show loading indicator
        loading = self.query_one("#query-loading", LoadingIndicator)
        loading.display = True

        # Start worker to run query
        self.run_worker(self.execute_query(query), exclusive=True)

    async def execute_query(self, query: str) -> str:
        """Execute the query using Claude CLI."""
        try:
            # Find the facts file (from project root outputs/, not session dir)
            if not self.facts_file:
                session_dir = Path(".frfr_sessions") / self.session_id

                # Load session metadata to find facts files
                metadata_file = session_dir / "metadata.json"
                if not metadata_file.exists():
                    return f"[red]Error: Session metadata not found at {metadata_file}[/red]"

                with open(metadata_file) as mf:
                    metadata = json.load(mf)
                    documents = metadata.get("document_registry", {})

                    if not documents:
                        return f"[red]Error: No documents found in session {self.session_id}[/red]"

                    # Use first document's facts file
                    first_doc = list(documents.values())[0]
                    facts_file_path = first_doc.get("facts_file", "")

                    if not facts_file_path:
                        return f"[red]Error: Document has no facts_file path in metadata[/red]"

                    self.facts_file = Path(facts_file_path)

            if not self.facts_file:
                return f"[red]Error: Could not determine facts file path for session {self.session_id}[/red]"

            if not self.facts_file.exists():
                return f"[red]Error: Facts file not found at {self.facts_file}[/red]"

            # Load facts with nested structure support
            with open(self.facts_file) as f:
                facts_data = json.load(f)

                # Facts might be nested under documents > doc_name > facts
                facts = []
                if "documents" in facts_data:
                    for doc_name, doc_data in facts_data.get("documents", {}).items():
                        facts.extend(doc_data.get("facts", []))
                else:
                    # Fallback to top-level facts
                    facts = facts_data.get("facts", [])

            if not facts:
                return "[red]Error: No facts found in file[/red]"

            # Build context for Claude
            facts_context = "Here are the extracted facts:\n\n"
            for i, fact in enumerate(facts[:100], 1):  # Limit to first 100 facts
                claim = fact.get("claim", "")
                location = fact.get("source_location", "")

                # Support both V4 (evidence_quote) and V5 (evidence_quotes) formats
                evidence = ""
                if "evidence_quotes" in fact and fact["evidence_quotes"]:
                    # V5 format: multiple quotes
                    evidence_list = fact["evidence_quotes"]
                    if isinstance(evidence_list, list):
                        evidence = evidence_list[0].get("quote", "") if isinstance(evidence_list[0], dict) else evidence_list[0]
                else:
                    # V4 format: single quote
                    evidence = fact.get("evidence_quote", "")

                facts_context += f"{i}. {claim}\n   Source: {location}\n   Evidence: {evidence}\n\n"

            # Create prompt for Claude
            prompt = f"""{facts_context}

Based on the facts above, please answer the following question. Include citations to specific fact numbers in your answer.

Question: {query}"""

            # Run claude command
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return f"[red]Error running query: {result.stderr}[/red]"

        except subprocess.TimeoutExpired:
            return "[red]Query timed out[/red]"
        except Exception as e:
            return f"[red]Error: {str(e)}[/red]"

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.SUCCESS:
            # Get result
            result = event.worker.result

            # Hide loading indicator
            loading = self.query_one("#query-loading", LoadingIndicator)
            loading.display = False

            # Display result
            results_log = self.query_one("#query-results", RichLog)
            results_log.write(f"[green]A:[/green] {result}\n")

            # Update status
            status_widget = self.query_one("#query-status", Static)
            status_widget.update("Query completed")

            # Clear status after a delay
            self.set_timer(3, lambda: status_widget.update(""))

        elif event.state == WorkerState.ERROR:
            # Hide loading indicator
            loading = self.query_one("#query-loading", LoadingIndicator)
            loading.display = False

            # Show error
            results_log = self.query_one("#query-results", RichLog)
            results_log.write(f"[red]Error: {event.worker.error}[/red]\n")

            # Update status
            status_widget = self.query_one("#query-status", Static)
            status_widget.update("Query failed")

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_history_prev(self) -> None:
        """Navigate to previous query in history."""
        if self.query_history and self.history_index > 0:
            self.history_index -= 1
            query_input = self.query_one("#query-input", Input)
            query_input.value = self.query_history[self.history_index]

    def action_history_next(self) -> None:
        """Navigate to next query in history."""
        if self.query_history and self.history_index < len(self.query_history) - 1:
            self.history_index += 1
            query_input = self.query_one("#query-input", Input)
            query_input.value = self.query_history[self.history_index]
        elif self.history_index == len(self.query_history) - 1:
            self.history_index = len(self.query_history)
            query_input = self.query_one("#query-input", Input)
            query_input.value = ""

    def _build_commands_text(self) -> str:
        """Build the commands help text."""
        commands = [
            "[cyan]Ctrl+Enter[/cyan] Submit",
            "[cyan]↑[/cyan]          Previous",
            "[cyan]↓[/cyan]          Next",
            "",
            "[cyan]Esc[/cyan]        Back",
            "[cyan]q[/cyan]          Quit",
            "[cyan]?[/cyan]          Help",
        ]
        return "\n".join(commands)
