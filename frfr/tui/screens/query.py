"""Query interface screen for asking questions about facts."""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Button, RichLog, Label, LoadingIndicator, ProgressBar
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
        background: $boost;
        color: $text;
    }

    #query-progress {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    #query-results {
        height: 1fr;
        min-height: 20;
        border: solid $primary;
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
                    yield ProgressBar(id="query-progress", total=100, show_eta=False)
                    with Horizontal():
                        yield LoadingIndicator(id="query-loading")
                        yield Static("", id="query-status")
                    yield RichLog(id="query-results", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        # Focus the input
        query_input = self.query_one("#query-input", Input)
        query_input.focus()

        # Hide loading indicator and progress bar initially
        loading = self.query_one("#query-loading", LoadingIndicator)
        loading.display = False

        progress = self.query_one("#query-progress", ProgressBar)
        progress.display = False

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

        # Show query in results with immediate feedback
        results_log = self.query_one("#query-results", RichLog)
        results_log.write(f"\n[bold]Q: {query}[/bold]")
        results_log.write("[dim]⏳ Searching facts...[/dim]")

        # Run query in worker
        self.run_query_worker(query)

    def run_query_worker(self, query: str) -> None:
        """Run query in a background worker."""
        status_widget = self.query_one("#query-status", Static)
        status_widget.update("[bold cyan]⏳ Starting query...[/bold cyan]")

        # Show loading indicator and progress bar
        loading = self.query_one("#query-loading", LoadingIndicator)
        loading.display = True

        progress = self.query_one("#query-progress", ProgressBar)
        progress.display = True
        progress.update(progress=0)

        # Start worker to run query
        self.run_worker(self.execute_query(query), exclusive=True)

    async def execute_query(self, query: str) -> str:
        """Execute the query using Claude CLI."""
        try:
            # Helper function to update UI from async worker
            async def update_progress(stage_progress: int, status_text: str):
                """Update progress bar and status text."""
                self.query_one("#query-progress", ProgressBar).update(progress=stage_progress)
                self.query_one("#query-status", Static).update(f"[bold cyan]{status_text}[/bold cyan]")
                await asyncio.sleep(0)  # Yield to event loop to allow UI to render

            # Stage 1: Load session metadata (0-10%)
            await update_progress(5, "⏳ Loading session metadata...")

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

            await update_progress(10, "📄 Loading facts from JSON...")

            # Stage 2: Load facts from JSON (10-20%)
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

            total_facts = len(facts)
            await update_progress(20, f"🔨 Building context from {total_facts} facts...")

            # Stage 3: Build context from all facts (20-40%)
            facts_context = "Here are the extracted facts:\n\n"

            # Process all facts (removed 100 limit)
            for i, fact in enumerate(facts, 1):
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

                # Update progress every 10 facts to avoid too many UI updates
                if i % 10 == 0 or i == total_facts:
                    current_progress = 20 + int((i / total_facts) * 20)
                    self.query_one("#query-progress", ProgressBar).update(progress=current_progress)
                    await asyncio.sleep(0)  # Yield to event loop

            await update_progress(40, f"🤖 Querying Claude with {total_facts} facts...")

            # Stage 4: Query Claude (40-100%)
            # Animation pattern: 40% -> 90% over 15s, then 1%/5s to 99%, then 100% when done

            # Create prompt for Claude
            prompt = f"""{facts_context}

Based on the facts above, please answer the following question. Include citations to specific fact numbers in your answer.

Question: {query}"""

            # Run claude command asynchronously
            process = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Animate progress bar while waiting for Claude
            progress_bar = self.query_one("#query-progress", ProgressBar)
            async def animate_progress():
                """Animate progress with realistic timing:
                - 40% to 90% over 15 seconds
                - Then 1% every 5 seconds (90% -> 99%)
                """
                # Phase 1: 40% -> 90% over 15 seconds (50% progress)
                # Update every 0.3 seconds for smooth animation (15s / 50 steps = 0.3s per %)
                for i in range(40, 90):
                    progress_bar.update(progress=i)
                    await asyncio.sleep(0.3)

                # Phase 2: 90% -> 99% at 1% per 5 seconds
                for i in range(90, 99):
                    progress_bar.update(progress=i)
                    await asyncio.sleep(5)

            # Run animation and process communication concurrently
            animation_task = asyncio.create_task(animate_progress())

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
                stdout_text = stdout.decode('utf-8')
                stderr_text = stderr.decode('utf-8')
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return "[red]Query timed out[/red]"
            finally:
                # Cancel animation task
                animation_task.cancel()
                try:
                    await animation_task
                except asyncio.CancelledError:
                    pass

            # Quickly animate to 100% before returning
            progress_bar.update(progress=100)
            await asyncio.sleep(0)  # Yield to event loop

            if process.returncode == 0:
                return stdout_text
            else:
                return f"[red]Error running query: {stderr_text}[/red]"

        except Exception as e:
            return f"[red]Error: {str(e)}[/red]"

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.SUCCESS:
            # Get result
            result = event.worker.result

            # Hide loading indicator and progress bar
            loading = self.query_one("#query-loading", LoadingIndicator)
            loading.display = False

            progress = self.query_one("#query-progress", ProgressBar)
            progress.display = False

            # Display result
            results_log = self.query_one("#query-results", RichLog)
            results_log.write(f"[green]A:[/green] {result}\n")

            # Update status
            status_widget = self.query_one("#query-status", Static)
            status_widget.update("[bold green]✓ Query completed successfully![/bold green]")

            # Clear status after a delay
            self.set_timer(3, lambda: status_widget.update(""))

        elif event.state == WorkerState.ERROR:
            # Hide loading indicator and progress bar
            loading = self.query_one("#query-loading", LoadingIndicator)
            loading.display = False

            progress = self.query_one("#query-progress", ProgressBar)
            progress.display = False

            # Show error
            results_log = self.query_one("#query-results", RichLog)
            results_log.write(f"[red]Error: {event.worker.error}[/red]\n")

            # Update status
            status_widget = self.query_one("#query-status", Static)
            status_widget.update("[bold red]✗ Query failed[/bold red]")

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
