"""Processing screen for document extraction."""

import subprocess
import sys
from pathlib import Path
from typing import Optional, List

from textual.app import ComposeResult
from frfr.config import default_config
from textual.screen import Screen
from textual.widgets import Static, ProgressBar, Label, RichLog, LoadingIndicator
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual.worker import Worker, WorkerState


class ProcessingScreen(Screen):
    """Screen for processing documents with progress feedback."""

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

    def __init__(
        self,
        file_paths: List[str],
        session_id: Optional[str] = None,
        is_new_session: bool = True,
        resume_incomplete: bool = False
    ):
        super().__init__()
        self.file_paths = file_paths
        self.session_id = session_id
        self.is_new_session = is_new_session
        self.resume_incomplete = resume_incomplete
        self.worker: Optional[Worker] = None
        self.result_session_id: Optional[str] = None
        self.total_chunks: Optional[int] = None
        self.current_chunk: int = 0
        self.total_facts_extracted: int = 0
        self.last_progress_update = ""

    def compose(self) -> ComposeResult:
        """Compose the processing screen layout."""
        with Container():
            yield Label("[bold cyan]Processing Documents[/bold cyan]", classes="title")
            with Vertical():
                yield Static(self._format_files_info(), id="files-info")
                yield Static("\n[bold]Progress[/bold]")
                with Horizontal():
                    yield LoadingIndicator(id="loading-indicator")
                    yield Static("", id="status-message")
                yield Static("", id="chunk-info")
                yield ProgressBar(total=100, show_eta=False, id="progress-bar")
                yield Label("\n[bold]Log[/bold]")
                yield RichLog(id="process-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        """Start processing when mounted."""
        log = self.query_one("#process-log", RichLog)
        log.write("[cyan]Starting document processing...[/cyan]")

        # Start the processing worker
        self.worker = self.run_worker(
            self.process_documents(),
            exclusive=True,
            name="document-processor"
        )

        # Start progress monitoring
        self.set_interval(0.5, self.update_progress_from_file)

    def _format_files_info(self) -> str:
        """Format information about files being processed."""
        lines = []
        if self.is_new_session:
            lines.append("[cyan]Creating new session[/cyan]")
        else:
            lines.append(f"[cyan]Adding to session: {self.session_id}[/cyan]")

        if self.resume_incomplete:
            lines.append("[yellow]Mode: Resume incomplete chunks[/yellow]")

        lines.append(f"\n[bold]Files to process:[/bold] {len(self.file_paths)}")
        for i, path in enumerate(self.file_paths[:5], 1):
            lines.append(f"  {i}. {Path(path).name}")
        if len(self.file_paths) > 5:
            lines.append(f"  ... and {len(self.file_paths) - 5} more")

        return "\n".join(lines)

    async def process_documents(self) -> dict:
        """Process documents using the CLI with streaming output."""
        log = self.query_one("#process-log", RichLog)
        status = self.query_one("#status-message", Static)
        progress = self.query_one("#progress-bar", ProgressBar)

        try:
            # Build the command
            cmd = [sys.executable, "-m", "frfr.cli", "process"]
            cmd.extend(self.file_paths)

            if self.session_id:
                cmd.extend(["--session-id", self.session_id])

            # Add flags for better quality
            cmd.extend(["--max-workers", "20"])  # Use more workers for faster processing
            # Use adaptive chunking (default) - removes --chunk-size and --overlap to enable it
            cmd.append("--no-interactive")  # Don't enter interactive mode

            if self.resume_incomplete:
                cmd.append("--resume-incomplete")  # Resume mode: only process incomplete chunks

            log.write("[cyan]Using enriched extraction settings:[/cyan]")
            log.write("[dim]  • Multi-pass extraction enabled[/dim]")
            log.write("[dim]  • 20 parallel workers (auto-optimized per document)[/dim]")
            log.write("[dim]  • Adaptive chunking (3k-8k chars/chunk, semantic boundaries)[/dim]")
            if self.resume_incomplete:
                log.write("[dim]  • Resume mode: processing incomplete chunks only[/dim]")
            log.write("\n")

            log.write(f"[dim]Command: {' '.join(cmd)}[/dim]\n")
            status.update("Starting extraction...")
            progress.update(progress=5)

            # Run the process with streaming output
            import asyncio

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path.cwd())
            )

            output_lines = []
            stderr_lines = []
            progress_value = 10

            # Read output line by line
            async def read_stream(stream, is_stderr=False):
                nonlocal progress_value
                while True:
                    line = await stream.readline()
                    if not line:
                        break

                    line_text = line.decode().strip()
                    if not line_text:
                        continue

                    if is_stderr:
                        stderr_lines.append(line_text)
                        log.write(f"[yellow]{line_text}[/yellow]")
                    else:
                        output_lines.append(line_text)

                        # Parse chunk information for granular progress
                        import re

                        # Look for total chunks: "Document: X lines → Y chunks"
                        total_chunks_match = re.search(r'(\d+)\s+chunks', line_text)
                        if total_chunks_match:
                            new_chunk_count = int(total_chunks_match.group(1))

                            # Always update if we see a new chunk count (handles algorithm changes)
                            if self.total_chunks != new_chunk_count:
                                if self.total_chunks is not None:
                                    log.write(f"[yellow]⚠️  Chunk count changed: {self.total_chunks} → {new_chunk_count}[/yellow]")
                                self.total_chunks = new_chunk_count
                                log.write(f"[cyan]Document split into {self.total_chunks} chunks[/cyan]")
                                # Update chunk info display
                                chunk_info = self.query_one("#chunk-info", Static)
                                chunk_info.update(f"[cyan]Chunks: 0/{self.total_chunks} (0%)[/cyan]")

                        # Look for chunk completion: "Chunk X/Y • Z facts extracted" or "Completed chunk X/Y"
                        chunk_progress_match = re.search(r'[Cc]hunk\s+(\d+)/(\d+)', line_text)
                        facts_extracted_match = re.search(r'(\d+)\s+facts', line_text)

                        if chunk_progress_match:
                            current = int(chunk_progress_match.group(1))
                            total = int(chunk_progress_match.group(2))

                            if self.total_chunks is None:
                                self.total_chunks = total

                            self.current_chunk = current

                            # Calculate progress: 10% setup + 80% extraction + 10% finalization
                            chunk_progress = (current / total) * 80
                            progress_value = 10 + chunk_progress
                            progress.update(progress=min(progress_value, 95))

                            # Extract fact count if available and update running total
                            facts_info = ""
                            if facts_extracted_match:
                                facts_count = int(facts_extracted_match.group(1))
                                self.total_facts_extracted = facts_count  # Running total from CLI
                                facts_info = f" • {facts_count} facts total"

                            # Update status and chunk info
                            chunk_percent = int((current / total) * 100)
                            status.update(f"Extracting facts from chunks...")
                            chunk_info = self.query_one("#chunk-info", Static)
                            chunk_info.update(f"[cyan]Chunks: {current}/{total} ({chunk_percent}%){facts_info}[/cyan]")

                            # Only log every 10th chunk to avoid spam, or if facts mentioned, or first/last
                            if current % 10 == 0 or current == 1 or current == total or facts_extracted_match:
                                log.write(f"[dim]Chunk {current}/{total}{facts_info}[/dim]")

                        # Parse final extraction results
                        total_facts_match = re.search(r'Total Facts.*?(\d+)', line_text)
                        if total_facts_match:
                            total_facts = int(total_facts_match.group(1))
                            self.total_facts_extracted = total_facts
                            log.write(f"[green bold]Total Facts Extracted: {total_facts}[/green bold]")

                        # Show all output in real-time with color coding
                        if "Session:" in line_text or "sess_" in line_text:
                            log.write(f"[cyan]{line_text}[/cyan]")
                        elif "✓" in line_text or "✅" in line_text or "success" in line_text.lower():
                            log.write(f"[green]{line_text}[/green]")
                        elif "error" in line_text.lower() or "failed" in line_text.lower():
                            log.write(f"[red]{line_text}[/red]")
                        elif "Extraction Results" in line_text or "Metric" in line_text:
                            log.write(f"[cyan]{line_text}[/cyan]")
                        elif "Extracting" in line_text and "chunk" not in line_text.lower():
                            log.write(f"[cyan]{line_text}[/cyan]")
                        elif "Processing" in line_text and not chunk_progress_match:
                            log.write(f"[cyan]{line_text}[/cyan]")
                        elif "Validating facts" in line_text:
                            log.write(f"[cyan]{line_text}[/cyan]")
                            status.update("Validating facts...")
                            progress.update(progress=92)
                        elif chunk_progress_match or total_chunks_match or total_facts_match:
                            # Already logged above
                            pass
                        else:
                            # Only log non-empty informative lines
                            if line_text and not line_text.startswith("│"):
                                log.write(f"[dim]{line_text}[/dim]")

                    # Update status based on content (if not already updated by chunk progress)
                    if self.current_chunk == 0:
                        if "Extracting text" in line_text:
                            status.update("Extracting text from PDF...")
                        elif "Validating" in line_text:
                            status.update("Validating facts...")
                        elif "Session" in line_text:
                            status.update("Finalizing session...")

            # Read both stdout and stderr concurrently
            await asyncio.gather(
                read_stream(process.stdout, is_stderr=False),
                read_stream(process.stderr, is_stderr=True)
            )

            # Wait for process to complete
            returncode = await process.wait()
            progress.update(progress=100)

            # Extract session ID from output if available
            for line in output_lines:
                if "sess_" in line:
                    import re
                    match = re.search(r'(sess_[a-zA-Z0-9_]+)', line)
                    if match:
                        self.result_session_id = match.group(1)
                        break

            # Check result
            if returncode == 0:
                log.write("\n[green bold]✓ Processing completed successfully[/green bold]")

                # Show final summary
                if self.total_chunks:
                    log.write(f"[cyan]Final: {self.current_chunk}/{self.total_chunks} chunks processed[/cyan]")
                if self.total_facts_extracted:
                    log.write(f"[cyan]Final: {self.total_facts_extracted} facts extracted[/cyan]")
                    if self.total_chunks:
                        avg_facts = self.total_facts_extracted / self.total_chunks
                        log.write(f"[cyan]Average: {avg_facts:.1f} facts per chunk[/cyan]")

                status.update("Processing complete!")
                chunk_info = self.query_one("#chunk-info", Static)
                chunk_info.update(f"[green]Complete: {self.current_chunk}/{self.total_chunks} chunks • {self.total_facts_extracted} facts[/green]")

                return {
                    "success": True,
                    "session_id": self.result_session_id or self.session_id,
                    "output": "\n".join(output_lines)
                }
            else:
                log.write("\n[red bold]✗ Processing failed[/red bold]")
                status.update("Processing failed")

                return {
                    "success": False,
                    "error": "\n".join(stderr_lines) if stderr_lines else "Unknown error"
                }

        except Exception as e:
            log.write(f"\n[red bold]Error: {str(e)}[/red bold]")
            status.update(f"Error: {str(e)}")
            progress.update(progress=100)

            return {
                "success": False,
                "error": str(e)
            }


    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.SUCCESS:
            result = event.worker.result
            log = self.query_one("#process-log", RichLog)

            # Hide the loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = False

            if result.get("success"):
                log.write("\n[green bold]✓ All done![/green bold]")
                log.write("[dim]Press Escape to return[/dim]")

                # Store the session ID for navigation
                self.result_session_id = result.get("session_id")
            else:
                log.write("\n[red bold]Processing failed[/red bold]")
                log.write("[dim]Press Escape to return[/dim]")

        elif event.state == WorkerState.ERROR:
            log = self.query_one("#process-log", RichLog)

            # Hide the loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = False

            log.write(f"[red]Worker error: {event.worker.error}[/red]")
            log.write("[dim]Press Escape to return[/dim]")

    def update_progress_from_file(self) -> None:
        """Poll progress file and update UI from progress file."""
        if not self.session_id:
            return

        try:
            from frfr.progress import get_all_progress

            session_dir = Path(default_config.session_storage_dir) / self.session_id
            all_progress = get_all_progress(session_dir)

            if all_progress:
                # Use first document's progress (assuming single doc processing)
                for doc_name, progress in all_progress.items():
                    self._update_ui_from_progress(progress)
                    break

        except Exception:
            pass  # Silently ignore errors

    def _update_ui_from_progress(self, progress) -> None:
        """Update UI from progress data."""
        try:
            progress_bar = self.query_one("#progress-bar", ProgressBar)
            status = self.query_one("#status-message", Static)
            chunk_info = self.query_one("#chunk-info", Static)
            log = self.query_one("#process-log", RichLog)

            # Calculate overall progress
            percentage = progress.get_progress_percentage()
            progress_bar.update(progress=percentage)

            # Get stage counts
            stage_counts = progress.get_stage_counts()

            # Update chunk info
            completed = stage_counts.get("completed", 0)
            total_from_progress = progress.total_chunks

            # Only update total_chunks if we haven't seen a newer value from logs
            # (Logs parsing takes precedence over progress file to handle chunking changes)
            if self.total_chunks is None:
                # First time - use progress file value
                self.total_chunks = total_from_progress
            elif total_from_progress != self.total_chunks:
                # Mismatch - prefer the value from logs if we've seen one
                # But if total_from_progress is smaller (chunking improved), use it
                if total_from_progress < self.total_chunks:
                    log.write(f"[yellow]Updating to new chunk count from progress: {total_from_progress}[/yellow]")
                    self.total_chunks = total_from_progress

            self.current_chunk = completed

            # Calculate total facts from progress
            total_facts = sum(c.facts_extracted for c in progress.chunks.values())
            total_valid = sum(c.facts_valid for c in progress.chunks.values())
            total_recovered = sum(c.facts_recovered for c in progress.chunks.values())
            self.total_facts_extracted = total_valid

            # Determine current stage
            extracting = stage_counts.get("extracting", 0)
            validating = stage_counts.get("validating", 0)

            if extracting > 0:
                status.update("Extracting facts from chunks...")
            elif validating > 0:
                status.update("Validating and recovering facts...")
            elif completed == total:
                status.update("Processing complete!")
            else:
                status.update("Processing chunks...")

            # Update chunk info display
            chunk_percent = int((completed / total) * 100) if total > 0 else 0
            facts_info = f" • {total_valid} facts"
            if total_recovered > 0:
                facts_info += f" ({total_recovered} recovered)"

            chunk_info.update(f"[cyan]Chunks: {completed}/{total} ({chunk_percent}%){facts_info}[/cyan]")

            # Log progress updates (avoid spam - only log every 10 chunks or milestones)
            progress_key = f"{completed}/{total}"
            if progress_key != self.last_progress_update and (completed % 10 == 0 or completed == 1 or completed == total):
                log.write(f"[dim]Chunk {completed}/{total}{facts_info}[/dim]")
                self.last_progress_update = progress_key

        except Exception:
            pass  # Silently ignore UI update errors

    def action_cancel(self) -> None:
        """Cancel processing and return."""
        if self.worker and self.worker.is_running:
            self.app.notify("Cancelling processing...", severity="warning")
            self.worker.cancel()

        self.app.pop_screen()
