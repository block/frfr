"""Recovery screen for enriching existing facts with LLM."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from frfr.config import default_config
from textual.screen import Screen
from textual.widgets import Static, ProgressBar, Label, RichLog, LoadingIndicator
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual.worker import Worker, WorkerState


class RecoveryScreen(Screen):
    """Screen for recovering/enriching facts without reprocessing."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    CSS = """
    #loading-indicator {
        width: auto;
        height: 1;
        padding: 0 1;
    }

    #status-message {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }

    Horizontal {
        width: 100%;
        height: auto;
        align: left middle;
    }
    """

    def __init__(self, session_id: str, document_name: Optional[str] = None):
        super().__init__()
        self.session_id = session_id
        self.document_name = document_name
        self.worker: Optional[Worker] = None
        self.last_progress_update = ""

    def compose(self) -> ComposeResult:
        """Compose the recovery screen layout."""
        with Container():
            yield Label("[bold cyan]Recovering Facts[/bold cyan]", classes="title")
            with Vertical():
                if self.document_name:
                    yield Static(f"[cyan]Document: {self.document_name}[/cyan]", id="doc-info")
                else:
                    yield Static(f"[cyan]Session: {self.session_id}[/cyan]", id="session-info")
                yield Static("\n[bold]Progress[/bold]")
                with Horizontal():
                    yield LoadingIndicator(id="loading-indicator")
                    yield Static("", id="status-message")
                yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                yield Label("\n[bold]Log[/bold]")
                yield RichLog(id="recovery-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        """Start recovery when mounted."""
        log = self.query_one("#recovery-log", RichLog)
        log.write("[cyan]Starting fact recovery...[/cyan]")

        # Start the recovery worker
        self.worker = self.run_worker(
            self.recover_facts(),
            exclusive=True,
            name="fact-recoverer"
        )

        # Start progress monitoring
        self.set_interval(0.5, self.update_progress_from_file)

    async def recover_facts(self) -> dict:
        """Recover facts using validation with LLM recovery."""
        log = self.query_one("#recovery-log", RichLog)
        status = self.query_one("#status-message", Static)
        progress = self.query_one("#progress-bar", ProgressBar)

        try:
            # Find the consolidated facts file and text file
            session_dir = Path(default_config.session_storage_dir) / self.session_id
            metadata_file = session_dir / "metadata.json"

            if not metadata_file.exists():
                return {
                    "success": False,
                    "error": f"Session metadata not found: {metadata_file}"
                }

            import json
            with open(metadata_file) as f:
                metadata = json.load(f)

            documents = metadata.get("document_registry", {})
            if not documents:
                return {
                    "success": False,
                    "error": "No documents found in session"
                }

            # If specific document requested, use that; otherwise use first document
            if self.document_name:
                doc_info = documents.get(self.document_name)
                if not doc_info:
                    return {
                        "success": False,
                        "error": f"Document {self.document_name} not found in session"
                    }
                docs_to_process = [(self.document_name, doc_info)]
            else:
                docs_to_process = list(documents.items())

            log.write(f"[cyan]Processing {len(docs_to_process)} document(s)[/cyan]\n")
            progress.update(progress=10)

            total_recovered = 0
            total_facts = 0

            for idx, (doc_name, doc_info) in enumerate(docs_to_process):
                doc_progress = (idx / len(docs_to_process)) * 80
                progress.update(progress=10 + doc_progress)

                log.write(f"[bold cyan]Document: {doc_name}[/bold cyan]")
                status.update(f"Processing {doc_name}...")

                facts_file = Path(doc_info.get("facts_file", ""))
                text_file = Path(doc_info.get("text_file", ""))

                if not facts_file.exists():
                    log.write(f"  [yellow]⚠ Facts file not found: {facts_file}[/yellow]")
                    continue

                if not text_file.exists():
                    log.write(f"  [yellow]⚠ Text file not found: {text_file}[/yellow]")
                    continue

                # Build recovery command using the validate-facts command
                cmd = [
                    sys.executable, "-m", "frfr.cli", "validate-facts",
                    str(facts_file),
                    str(text_file),
                    "--update-facts"  # This flag will save corrected facts
                ]

                log.write(f"  [dim]Running validation with recovery...[/dim]")

                # Run the validation/recovery process
                import asyncio
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(Path.cwd())
                )

                stdout, stderr = await process.communicate()
                returncode = await process.wait()

                if returncode == 0:
                    output = stdout.decode()
                    log.write(f"  [green]✓ Recovery completed[/green]")

                    # Parse output for stats
                    import re
                    recovered_match = re.search(r'Recovered.*?(\d+)', output)
                    total_match = re.search(r'Total.*?(\d+)', output)

                    if recovered_match:
                        recovered = int(recovered_match.group(1))
                        total_recovered += recovered
                        log.write(f"  [green]Recovered: {recovered} facts[/green]")

                    if total_match:
                        total = int(total_match.group(1))
                        total_facts += total
                else:
                    error_output = stderr.decode()
                    log.write(f"  [red]✗ Recovery failed: {error_output[:100]}[/red]")

                log.write("")  # Blank line

            progress.update(progress=100)
            status.update("Recovery complete!")

            log.write(f"\n[bold green]✓ Recovery Complete[/bold green]")
            log.write(f"[cyan]Total facts processed: {total_facts}[/cyan]")
            log.write(f"[green]Total recovered: {total_recovered}[/green]")

            return {
                "success": True,
                "total_facts": total_facts,
                "recovered": total_recovered
            }

        except Exception as e:
            log.write(f"\n[red bold]Error: {str(e)}[/red bold]")
            status.update(f"Error: {str(e)}")
            progress.update(progress=100)

            import traceback
            traceback.print_exc()

            return {
                "success": False,
                "error": str(e)
            }

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.SUCCESS:
            result = event.worker.result
            log = self.query_one("#recovery-log", RichLog)

            # Hide the loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = False

            if result.get("success"):
                log.write("\n[green bold]✓ All done![/green bold]")
                log.write("[dim]Press Escape to return[/dim]")
            else:
                log.write("\n[red bold]Recovery failed[/red bold]")
                log.write("[dim]Press Escape to return[/dim]")

        elif event.state == WorkerState.ERROR:
            log = self.query_one("#recovery-log", RichLog)

            # Hide the loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = False

            log.write(f"[red]Worker error: {event.worker.error}[/red]")
            log.write("[dim]Press Escape to return[/dim]")

    def update_progress_from_file(self) -> None:
        """Poll progress file and update UI."""
        try:
            from frfr.progress import get_document_progress

            session_dir = Path(default_config.session_storage_dir) / self.session_id

            # If specific document, check its progress
            if self.document_name:
                progress = get_document_progress(session_dir, self.document_name)
                if progress:
                    self._update_ui_from_progress(progress)
            else:
                # Check all documents
                from frfr.progress import get_all_progress
                all_progress = get_all_progress(session_dir)
                if all_progress:
                    # Use first document's progress for now
                    for doc_name, progress in all_progress.items():
                        self._update_ui_from_progress(progress)
                        break  # Just show first one for now

        except Exception:
            pass  # Silently ignore errors in progress polling

    def _update_ui_from_progress(self, progress) -> None:
        """Update UI elements from progress data."""
        try:
            progress_bar = self.query_one("#progress-bar", ProgressBar)
            status = self.query_one("#status-message", Static)
            log = self.query_one("#recovery-log", RichLog)

            # Calculate overall progress
            percentage = progress.get_progress_percentage()
            progress_bar.update(progress=percentage)

            # Get stage counts
            stage_counts = progress.get_stage_counts()

            # Build status message
            completed = stage_counts.get("completed", 0)
            total = progress.total_chunks
            extracting = stage_counts.get("extracting", 0)
            validating = stage_counts.get("validating", 0)

            if extracting > 0:
                status_msg = f"Extracting facts... ({completed}/{total} chunks complete)"
            elif validating > 0:
                status_msg = f"Validating facts... ({completed}/{total} chunks complete)"
            else:
                status_msg = f"Processing... ({completed}/{total} chunks complete)"

            status.update(status_msg)

            # Log progress updates (avoid spam)
            progress_key = f"{completed}/{total}"
            if progress_key != self.last_progress_update:
                # Calculate total facts
                total_facts = sum(c.facts_extracted for c in progress.chunks.values())
                total_valid = sum(c.facts_valid for c in progress.chunks.values())
                total_recovered = sum(c.facts_recovered for c in progress.chunks.values())

                if total_facts > 0:
                    log.write(f"[dim]Progress: {completed}/{total} chunks • {total_facts} facts • {total_valid} valid • {total_recovered} recovered[/dim]")

                self.last_progress_update = progress_key

        except Exception:
            pass  # Silently ignore UI update errors

    def action_cancel(self) -> None:
        """Cancel recovery and return."""
        if self.worker and self.worker.is_running:
            self.app.notify("Cancelling recovery...", severity="warning")
            self.worker.cancel()

        self.app.pop_screen()
