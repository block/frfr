"""Query interface screen for asking questions about facts."""

import asyncio
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from textual.app import ComposeResult
from frfr.config import default_config
from textual.screen import Screen
from textual.widgets import Static, Input, Button, RichLog, Label, LoadingIndicator, ProgressBar
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from textual.worker import Worker, WorkerState
from textual.widgets._rich_log import RichLog as RichLogWidget
from rich.markdown import Markdown
from rich.text import Text

from frfr.conversation import ChunkManager, ChunkWithEvidence


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
        height: 3fr;
        min-height: 15;
        border: solid $primary;
    }

    #chunk-context-container {
        height: 2fr;
        min-height: 10;
        margin-top: 1;
    }

    #chunk-context-panel {
        height: 100%;
        border: solid $accent;
        padding: 1;
    }

    .chunk-header {
        background: $accent;
        color: $text;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, session_id: str, facts_file: Optional[Path] = None):
        super().__init__()
        self.session_id = session_id
        self.facts_file = facts_file
        self.query_history: List[str] = []
        self.history_index = -1
        self.conversation_history: List[Dict[str, str]] = []  # Store Q&A pairs for context
        self.current_query: str = ""  # Track current query for conversation history

        # Initialize ChunkManager for context-aware responses
        session_path = Path(default_config.session_storage_dir) / session_id
        self.chunk_manager = ChunkManager(session_path)
        self.current_chunks: List[ChunkWithEvidence] = []  # Track chunks used in current response
        self.current_facts: List[Dict] = []  # Track facts for interactive clicking

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

                # Right panel: Query interface and chunk context
                with Vertical(id="right-panel"):
                    with Horizontal():
                        yield Input(placeholder="Ask a question...", id="query-input")
                        yield Button("Submit", id="submit-button", variant="primary")
                    yield ProgressBar(id="query-progress", total=100, show_eta=False)
                    with Horizontal():
                        yield LoadingIndicator(id="query-loading")
                        yield Static("", id="query-status")
                    yield RichLog(id="query-results", highlight=True, markup=True, wrap=True)

                    # Chunk context panel
                    with Container(id="chunk-context-container"):
                        yield Static("[bold]📄 Source Context[/bold]", classes="chunk-header")
                        yield RichLog(id="chunk-context-panel", highlight=True, markup=True, wrap=True)

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
        results_log.write("[dim]Type your question and press Ctrl+Enter to submit.[/dim]")
        results_log.write("[dim]Tip: Type 'fact N' (e.g., 'fact 3') to view source context for a specific fact.[/dim]\n")

        # Initialize chunk context panel
        chunk_panel = self.query_one("#chunk-context-panel", RichLog)
        chunk_panel.write("[dim]Type 'fact N' (e.g., 'fact 3') to view source context for a specific fact.[/dim]")
        chunk_panel.write("[dim]Evidence will be highlighted in yellow.[/dim]")

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

        # Check if this is a "fact N" command to view specific fact context
        fact_match = re.match(r'^(?:show\s+)?fact\s+(\d+)$', query, re.IGNORECASE)
        if fact_match:
            fact_num = int(fact_match.group(1))
            self.show_fact_context(fact_num)
            query_input.value = ""
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
        # Store current query for conversation history
        self.current_query = query

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

    def _build_conversation_context(self, max_tokens: int = 20000) -> str:
        """Build conversation history context using sliding window.

        Args:
            max_tokens: Maximum token budget for conversation history (default 20k)

        Returns:
            Formatted conversation history string, or empty string if no history
        """
        if not self.conversation_history:
            return ""

        # Estimate tokens: rough approximation of 1 token per 4 characters
        def estimate_tokens(text: str) -> int:
            return len(text) // 4

        # Build context from most recent exchanges that fit in budget
        context_parts = []
        total_tokens = 0

        # Iterate backwards through history to prioritize recent exchanges
        for entry in reversed(self.conversation_history):
            question = entry["question"]
            answer = entry["answer"]

            # Format: "Q: ...\nA: ...\n\n"
            exchange = f"Q: {question}\nA: {answer}\n\n"
            exchange_tokens = estimate_tokens(exchange)

            # Check if adding this exchange would exceed budget
            if total_tokens + exchange_tokens > max_tokens:
                break

            context_parts.insert(0, exchange)  # Insert at beginning to maintain chronological order
            total_tokens += exchange_tokens

        if not context_parts:
            return ""

        return "Previous conversation:\n" + "".join(context_parts)

    async def execute_query(self, query: str) -> str:
        """Execute the query using Claude CLI with multi-pass processing to handle ALL facts."""
        try:
            # First, try single-pass with all facts (fastest)
            status_widget = self.query_one("#query-status", Static)
            status_widget.update("[bold cyan]⏳ Attempting single-pass query with all facts...[/bold cyan]")

            result = await self._execute_single_pass_query(query)
            return result

        except Exception as e:
            error_str = str(e)
            # Check if this is a context limit error
            if "prompt is too long" in error_str.lower() or "context_length_exceeded" in error_str.lower() or "maximum context length" in error_str.lower():
                # Context too large - switch to multi-pass strategy
                status_widget = self.query_one("#query-status", Static)
                status_widget.update("[bold yellow]⚠️ Context too large for single pass. Processing all facts in batches...[/bold yellow]")
                await asyncio.sleep(1)

                # Multi-pass: process all facts in batches, then synthesize
                result = await self._execute_multi_pass_query(query)
                return result
            else:
                # Non-context-limit error
                return f"[red]Error: {error_str}[/red]"

    async def _load_all_facts(self) -> List[Dict]:
        """Load all facts from the session."""
        session_dir = Path(default_config.session_storage_dir) / self.session_id

        if not self.facts_file:
            metadata_file = session_dir / "metadata.json"
            with open(metadata_file) as mf:
                metadata = json.load(mf)
                documents = metadata.get("document_registry", {})
                first_doc = list(documents.values())[0]
                self.facts_file = Path(first_doc.get("facts_file", ""))

        with open(self.facts_file) as f:
            facts_data = json.load(f)
            facts = []
            if "documents" in facts_data:
                for doc_name, doc_data in facts_data.get("documents", {}).items():
                    facts.extend(doc_data.get("facts", []))
            else:
                facts = facts_data.get("facts", [])

        # Store for interactive clicking
        self.current_facts = facts
        return facts

    async def _process_fact_batch(self, batch_facts: List[Dict], start_idx: int, query: str) -> Optional[Dict]:
        """
        Process a batch of facts and extract relevant insights.

        Args:
            batch_facts: Facts in this batch
            start_idx: Starting index of this batch in full facts list
            query: User query

        Returns:
            Dict with 'insights' and 'relevant_facts' keys, or None if error
        """
        # Build compressed facts context for this batch
        facts_context = f"Facts {start_idx + 1}-{start_idx + len(batch_facts)}:\n"
        for i, fact in enumerate(batch_facts, start=start_idx + 1):
            claim = fact.get("claim", "")
            location = fact.get("source_location", "")
            evidence = fact.get("evidence_quote", "")
            if "evidence_quotes" in fact and fact["evidence_quotes"]:
                evidence_list = fact["evidence_quotes"]
                if isinstance(evidence_list, list) and len(evidence_list) > 0:
                    evidence = evidence_list[0].get("quote", "") if isinstance(evidence_list[0], dict) else evidence_list[0]

            facts_context += f"[{i}] {claim} | {location} | {evidence}\n"

        # Query Claude to extract relevant insights
        prompt = f"""{facts_context}

Query: {query}

Task: Analyze these facts and identify which are relevant to answering the query.

Output JSON format:
{{
  "relevant_facts": [list of fact numbers that are relevant],
  "insights": "Brief summary of key insights from relevant facts (2-3 sentences)"
}}

RESPOND WITH ONLY THE JSON OBJECT:"""

        try:
            process = await asyncio.create_subprocess_exec(
                "claude", "-p",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode('utf-8')),
                timeout=60
            )

            if process.returncode != 0:
                return None

            response = stdout.decode('utf-8')

            # Parse JSON response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()

            result = json.loads(response)
            return result

        except Exception:
            return None

    async def _synthesize_final_answer(
        self,
        query: str,
        insights: List[str],
        relevant_fact_numbers: Set[int],
        all_facts: List[Dict]
    ) -> str:
        """
        Synthesize final answer from accumulated insights.

        Args:
            query: User query
            insights: List of insights from each batch
            relevant_fact_numbers: Set of all relevant fact numbers
            all_facts: All facts for reference

        Returns:
            Final answer
        """
        # Build context with just relevant facts
        relevant_facts_context = "Relevant facts:\n"
        for fact_num in sorted(relevant_fact_numbers):
            if 1 <= fact_num <= len(all_facts):
                fact = all_facts[fact_num - 1]
                claim = fact.get("claim", "")
                location = fact.get("source_location", "")
                evidence = fact.get("evidence_quote", "")
                if "evidence_quotes" in fact and fact["evidence_quotes"]:
                    evidence_list = fact["evidence_quotes"]
                    if isinstance(evidence_list, list) and len(evidence_list) > 0:
                        evidence = evidence_list[0].get("quote", "") if isinstance(evidence_list[0], dict) else evidence_list[0]

                relevant_facts_context += f"[{fact_num}] {claim} | {location} | {evidence}\n"

        # Combine accumulated insights
        accumulated_insights = "\n\nInsights from batches:\n" + "\n".join(f"- {insight}" for insight in insights if insight)

        prompt = f"""{relevant_facts_context}

{accumulated_insights}

Query: {query}

Using the relevant facts and accumulated insights above, provide a comprehensive answer to the query.
- Cite specific fact numbers (e.g., "According to [5]...")
- Synthesize information from multiple facts when relevant
- Be thorough and detailed

Answer:"""

        try:
            process = await asyncio.create_subprocess_exec(
                "claude", "-p",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=prompt.encode('utf-8')),
                timeout=120
            )

            if process.returncode == 0:
                return stdout.decode('utf-8')
            else:
                return f"[red]Error synthesizing final answer: {stderr.decode('utf-8')}[/red]"

        except Exception as e:
            return f"[red]Error synthesizing final answer: {e}[/red]"

    def _filter_facts_by_query(self, facts: List[Dict], query: str, max_facts: Optional[int] = None) -> List[Dict]:
        """
        Filter and rank facts by relevance to query.

        Args:
            facts: All facts from the document
            query: User query string
            max_facts: Maximum number of facts to return (None = all facts)

        Returns:
            Filtered and ranked list of facts
        """
        if max_facts is None:
            return facts  # Return all facts if no limit

        # Extract query keywords (remove common stop words)
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'when', 'where',
                      'who', 'why', 'how', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
        query_keywords = set(word.lower() for word in query.split() if word.lower() not in stop_words and len(word) > 2)

        if not query_keywords:
            # No meaningful keywords, return first N facts
            return facts[:max_facts]

        # Score each fact by keyword overlap
        scored_facts = []
        for fact in facts:
            # Build searchable text from fact
            fact_text = f"{fact.get('claim', '')} {fact.get('evidence_quote', '')}".lower()

            # Count keyword matches
            matches = sum(1 for keyword in query_keywords if keyword in fact_text)

            # Boost score for title/heading-like facts (often more important)
            if fact.get('claim', '').isupper() or len(fact.get('claim', '')) < 100:
                matches += 0.5

            scored_facts.append((matches, fact))

        # Sort by score (descending) and take top N
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        return [fact for _, fact in scored_facts[:max_facts]]

    async def _execute_single_pass_query(self, query: str) -> str:
        """
        Execute query in single pass with all facts.

        Args:
            query: User query string

        Raises:
            Exception: If context limit exceeded
        """
        # Use generous budgets for single-pass
        chunk_budget = 5000
        history_budget = 5000
        max_facts = None  # All facts

        return await self._execute_query_with_facts(
            query,
            chunk_budget=chunk_budget,
            history_budget=history_budget,
            max_facts=max_facts
        )

    async def _execute_multi_pass_query(self, query: str) -> str:
        """
        Execute query by processing all facts in batches (map-reduce).

        Strategy:
        1. Map phase: Process facts in batches of 500, extract relevant insights
        2. Reduce phase: Synthesize insights to answer the query

        Args:
            query: User query string

        Returns:
            Query answer
        """
        # Load all facts
        results_log = self.query_one("#query-results", RichLog)
        status_widget = self.query_one("#query-status", Static)
        progress_bar = self.query_one("#query-progress", ProgressBar)

        progress_bar.display = True
        progress_bar.update(progress=0)

        # Load facts
        status_widget.update("[bold cyan]📄 Loading all facts...[/bold cyan]")
        await asyncio.sleep(0)

        facts = await self._load_all_facts()
        total_facts = len(facts)

        # Map phase: Process in batches
        batch_size = 500
        num_batches = (total_facts + batch_size - 1) // batch_size

        results_log.write(f"[bold cyan]📊 Processing {total_facts} facts in {num_batches} batches...[/bold cyan]")

        relevant_insights = []
        relevant_fact_numbers = set()

        for batch_num in range(num_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, total_facts)
            batch_facts = facts[start_idx:end_idx]

            # Update progress
            progress = int((batch_num / num_batches) * 70)  # 0-70% for map phase
            progress_bar.update(progress=progress)
            status_widget.update(f"[bold cyan]🔍 Batch {batch_num + 1}/{num_batches}: Analyzing facts {start_idx + 1}-{end_idx}...[/bold cyan]")
            await asyncio.sleep(0)

            # Process this batch
            batch_result = await self._process_fact_batch(
                batch_facts,
                start_idx,
                query
            )

            if batch_result:
                relevant_insights.append(batch_result["insights"])
                relevant_fact_numbers.update(batch_result["relevant_facts"])

        # Reduce phase: Synthesize insights
        progress_bar.update(progress=75)
        status_widget.update(f"[bold cyan]🧩 Synthesizing insights from {len(relevant_fact_numbers)} relevant facts...[/bold cyan]")
        await asyncio.sleep(0)

        results_log.write(f"[dim]Found {len(relevant_fact_numbers)} relevant facts across all batches[/dim]")

        # Build final answer using accumulated insights
        final_answer = await self._synthesize_final_answer(
            query,
            relevant_insights,
            relevant_fact_numbers,
            facts
        )

        progress_bar.update(progress=100)
        progress_bar.display = False

        return final_answer

    async def _execute_query_with_facts(
        self,
        query: str,
        chunk_budget: int = 10000,
        history_budget: int = 10000,
        max_facts: Optional[int] = None
    ) -> str:
        """
        Execute a query with specified facts and budgets.

        Args:
            query: User query string
            chunk_budget: Token budget for chunks
            history_budget: Token budget for conversation history
            max_facts: Maximum number of facts to include (None = all facts)

        Raises:
            Exception: If context limit exceeded
        """
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
                session_dir = Path(default_config.session_storage_dir) / self.session_id

                # Load session metadata to find facts files
                metadata_file = session_dir / "metadata.json"
                if not metadata_file.exists():
                    # Enhanced error message with debugging info
                    import os
                    error_msg = f"Session metadata not found.\n"
                    error_msg += f"  Looking for: {metadata_file}\n"
                    error_msg += f"  session_storage_dir: {default_config.session_storage_dir}\n"
                    error_msg += f"  session_id: {self.session_id}\n"
                    error_msg += f"  session_dir: {session_dir}\n"
                    error_msg += f"  session_dir exists: {session_dir.exists()}\n"
                    error_msg += f"  cwd: {os.getcwd()}\n"
                    error_msg += f"  metadata_file.is_absolute(): {metadata_file.is_absolute()}"
                    raise FileNotFoundError(error_msg)

                with open(metadata_file) as mf:
                    metadata = json.load(mf)
                    documents = metadata.get("document_registry", {})

                    if not documents:
                        raise ValueError(f"No documents found in session {self.session_id}")

                    # Use first document's facts file
                    first_doc = list(documents.values())[0]
                    facts_file_path = first_doc.get("facts_file", "")

                    if not facts_file_path:
                        raise ValueError("Document has no facts_file path in metadata")

                    self.facts_file = Path(facts_file_path)

            if not self.facts_file:
                raise ValueError(f"Could not determine facts file path for session {self.session_id}")

            if not self.facts_file.exists():
                raise FileNotFoundError(f"Facts file not found at {self.facts_file}")

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
                raise ValueError("No facts found in file")

            # Store all facts for interactive clicking (always need full list)
            self.current_facts = facts

            total_facts = len(facts)

            # Stage 3: Filter facts by query relevance and build context (20-40%)
            # Filter facts if max_facts is specified
            filtered_facts = self._filter_facts_by_query(facts, query, max_facts)
            facts_to_use = len(filtered_facts)

            if max_facts is not None and facts_to_use < total_facts:
                await update_progress(20, f"🔨 Selecting top {facts_to_use} of {total_facts} facts...")
            else:
                await update_progress(20, f"🔨 Building context from {total_facts} facts...")

            # Use compressed format to save tokens (critical for large documents)
            facts_context = "Facts"
            if max_facts is not None and facts_to_use < total_facts:
                facts_context += f" (top {facts_to_use} of {total_facts}, most relevant)"
            facts_context += ":\n"

            # Process filtered facts - use compressed format to save ~30% tokens
            for i, fact in enumerate(filtered_facts, 1):
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

                # Compressed format: [N] Claim | Location | Evidence
                # Saves ~30% tokens vs verbose format
                facts_context += f"[{i}] {claim} | {location} | {evidence}\n"

                # Update progress every 10 facts to avoid too many UI updates
                if i % 10 == 0 or i == facts_to_use:
                    current_progress = 20 + int((i / facts_to_use) * 20)
                    self.query_one("#query-progress", ProgressBar).update(progress=current_progress)
                    await asyncio.sleep(0)  # Yield to event loop

            await update_progress(40, f"🧩 Building chunk context from source documents...")

            # Stage 4: Build chunk context for richer responses (40-50%)
            # Use separate budgets for chunks and conversation history
            # Build chunk context from facts
            chunk_context, used_chunks = self.chunk_manager.build_chunk_context(
                facts=facts,
                query=query,
                token_budget=chunk_budget
            )

            # Store chunks for display in context panel
            self.current_chunks = used_chunks

            chunk_info = f"{len(used_chunks)} source chunks" if chunk_budget > 0 else "no chunks"
            await update_progress(50, f"🤖 Querying Claude with {facts_to_use} facts and {chunk_info}...")

            # Stage 5: Query Claude (50-100%)
            # Animation pattern: 50% -> 90% over 15s, then 1%/5s to 99%, then 100% when done

            # Build conversation context using sliding window with specified token budget
            conversation_context = self._build_conversation_context(max_tokens=history_budget)

            # Create prompt for Claude with enhanced multi-hop reasoning support
            prompt_parts = [facts_context]

            # Add chunk context for richer understanding
            if chunk_context:
                prompt_parts.append(chunk_context)

            if conversation_context:
                prompt_parts.append(conversation_context)

            prompt_parts.append("""Answer the following question using the facts above. Facts are in format: [N] Claim | Location | Evidence

When answering:
- Cite fact numbers (e.g., "According to Fact 3..." or "As stated in [15]...")
- Use chunk context to find connections across sections/documents (multi-hop reasoning)
- Include relevant details from chunks not captured in extracted facts
- Synthesize information from multiple facts when relevant""")

            if conversation_context:
                prompt_parts.append("""If this question references previous answers (e.g., "it", "that", "the document"), use the conversation history to understand the context.""")

            prompt_parts.append(f"\nQuestion: {query}")

            prompt = "\n\n".join(prompt_parts)

            # Run claude command asynchronously
            # Pass prompt via stdin to avoid ARG_MAX limitations with large prompts
            process = await asyncio.create_subprocess_exec(
                "claude", "-p",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Animate progress bar while waiting for Claude
            progress_bar = self.query_one("#query-progress", ProgressBar)
            async def animate_progress():
                """Animate progress with realistic timing:
                - 50% to 90% over 15 seconds
                - Then 1% every 5 seconds (90% -> 99%)
                """
                # Phase 1: 50% -> 90% over 15 seconds (40% progress)
                # Update every 0.375 seconds for smooth animation (15s / 40 steps = 0.375s per %)
                for i in range(50, 90):
                    progress_bar.update(progress=i)
                    await asyncio.sleep(0.375)

                # Phase 2: 90% -> 99% at 1% per 5 seconds
                for i in range(90, 99):
                    progress_bar.update(progress=i)
                    await asyncio.sleep(5)

            # Run animation and process communication concurrently
            animation_task = asyncio.create_task(animate_progress())

            try:
                # Send prompt via stdin and wait for response
                # Use longer timeout for large prompts (3 minutes)
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=prompt.encode('utf-8')),
                    timeout=180
                )
                stdout_text = stdout.decode('utf-8')
                stderr_text = stderr.decode('utf-8')
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError(f"Query timed out after 180 seconds. Prompt size: {len(prompt)} bytes")
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
                # Raise error so retry logic can catch it
                error_msg = stderr_text.strip() if stderr_text.strip() else stdout_text.strip()
                if not error_msg:
                    error_msg = f"Claude CLI exited with code {process.returncode} but provided no error message. Prompt size: {len(prompt)} bytes"
                raise RuntimeError(f"Error running query: {error_msg}")

        except Exception as e:
            # Re-raise exception so retry logic can handle it
            raise

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle worker state changes."""
        if event.state == WorkerState.SUCCESS:
            # Get result
            result = event.worker.result

            # Add Q&A to conversation history for context in future queries
            if self.current_query and result:
                self.conversation_history.append({
                    "question": self.current_query,
                    "answer": result
                })

            # Hide loading indicator and progress bar
            loading = self.query_one("#query-loading", LoadingIndicator)
            loading.display = False

            progress = self.query_one("#query-progress", ProgressBar)
            progress.display = False

            # Display result
            results_log = self.query_one("#query-results", RichLog)
            results_log.write(f"[green]A:[/green] {result}\n")

            # Don't automatically display chunk context - let user request it with "fact N"
            # self._display_chunk_context()

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

    def show_fact_context(self, fact_num: int) -> None:
        """Show context for a specific fact number."""
        # Validate fact number
        if not self.current_facts:
            self.app.notify("No facts loaded yet. Please run a query first.", severity="warning")
            return

        if fact_num < 1 or fact_num > len(self.current_facts):
            self.app.notify(f"Invalid fact number. Please use 1-{len(self.current_facts)}.", severity="error")
            return

        # Get the specific fact (1-indexed)
        fact = self.current_facts[fact_num - 1]

        # Update results panel with fact info
        results_log = self.query_one("#query-results", RichLog)
        results_log.write(f"\n[bold cyan]📌 Viewing Fact {fact_num}:[/bold cyan]")
        results_log.write(f"[bold]{fact.get('claim', 'No claim')}[/bold]")
        results_log.write(f"[dim]Source: {fact.get('source_location', 'Unknown')}[/dim]")
        results_log.write(f"[dim]Document: {fact.get('source_doc', 'Unknown')}[/dim]\n")

        # Get chunk for this fact
        document = fact.get("source_doc", "").replace(".pdf", "")
        chunk = self.chunk_manager.find_chunk_for_fact(fact, document)

        # Debug info
        if chunk:
            results_log.write(f"[dim]Found in chunk: {chunk.chunk_id} (lines {chunk.line_start}-{chunk.line_end})[/dim]\n")

        chunk_panel = self.query_one("#chunk-context-panel", RichLog)
        chunk_panel.clear()

        if not chunk:
            chunk_panel.write(f"[yellow]⚠️ Could not find source chunk for Fact {fact_num}[/yellow]")
            chunk_panel.write(f"[dim]The chunk file may not exist in the session.[/dim]")
            return

        # Display chunk header
        chunk_panel.write(f"[bold cyan]📄 Source Context for Fact {fact_num}:[/bold cyan]\n")
        chunk_panel.write(f"[bold yellow]{chunk.document}[/bold yellow]")
        chunk_panel.write(f"[dim]Lines {chunk.line_start}-{chunk.line_end}[/dim]")
        chunk_panel.write("")  # Blank line

        # STRATEGY 1: Search for evidence text in chunk (most reliable!)
        # Note: Line numbers in source_location are often incorrect due to:
        # 1. Adaptive chunking makes chunk line calculations unreliable
        # 2. Facts inherit chunk's line range, not precise evidence location
        # Therefore, we search for evidence text directly instead of using line numbers

        focused_text = None
        successful_strategy = None
        search_attempts = []

        # Try evidence quotes
        if "evidence_quotes" in fact and fact["evidence_quotes"]:
            evidence_texts = [eq["quote"] for eq in fact["evidence_quotes"] if isinstance(eq, dict)]
            if evidence_texts:
                search_attempts.append(("evidence quotes", evidence_texts))
        elif "evidence_quote" in fact and fact["evidence_quote"]:
            search_attempts.append(("evidence quote", [fact["evidence_quote"]]))

        # Try claim text
        claim = fact.get('claim', '')
        if claim:
            claim_words = claim.split()
            if len(claim_words) >= 5:
                search_attempts.append(("full claim", [claim]))
                mid = len(claim_words) // 2
                first_half = ' '.join(claim_words[:mid+2])
                second_half = ' '.join(claim_words[mid-2:])
                if len(first_half.split()) >= 4:
                    search_attempts.append(("first half of claim", [first_half]))
                if len(second_half.split()) >= 4:
                    search_attempts.append(("second half of claim", [second_half]))

        # Try each search strategy
        for strategy_name, search_texts in search_attempts:
            focused_text = self.chunk_manager.get_focused_context(
                chunk.text,
                search_texts,
                context_lines=5,
                start_line_num=chunk.line_start
            )

            if focused_text and "not found" not in focused_text.lower():
                successful_strategy = (strategy_name, search_texts[0] if search_texts else "")
                preview = search_texts[0][:60] + "..." if len(search_texts[0]) > 60 else search_texts[0]
                chunk_panel.write(f"[dim]Found using {strategy_name}: \"{preview}\"[/dim]")
                chunk_panel.write("")  # Blank line
                break

        # STRATEGY 2: Show full chunk if nothing worked
        if not focused_text or "not found" in focused_text.lower():
            chunk_panel.write("[yellow]⚠️ Could not locate specific lines in chunk.[/yellow]")
            chunk_panel.write("[dim]Showing first 30 lines of chunk:[/dim]\n")

            lines = chunk.text.split('\n')
            for i, line in enumerate(lines[:30]):
                line_num = chunk.line_start + i
                chunk_panel.write(f"[dim]{line_num:4d} │ {line}[/dim]")

            if len(lines) > 30:
                chunk_panel.write(f"[dim]     │ ... ({len(lines) - 30} more lines)[/dim]")

            focused_text = None

        # Write the focused text if we have it
        if focused_text:
            chunk_panel.write(focused_text)
            chunk_panel.write("")  # Blank line

        chunk_panel.write("[dim]Legend: Line numbers shown on left. Highlighted lines (yellow) contain evidence.[/dim]")
        chunk_panel.write("[dim]Type 'fact N' to view another fact.[/dim]")

        # Notify user
        self.app.notify(f"Showing context for Fact {fact_num}", severity="information")

    def _display_chunk_context(self) -> None:
        """Display chunk context in the context panel."""
        chunk_panel = self.query_one("#chunk-context-panel", RichLog)

        # Clear previous content
        chunk_panel.clear()

        if not self.current_chunks:
            chunk_panel.write("[dim]No source chunks were used for this query.[/dim]")
            return

        chunk_panel.write(f"[bold cyan]Showing {len(self.current_chunks)} relevant source excerpts:[/bold cyan]\n")

        for i, chunk_with_evidence in enumerate(self.current_chunks, 1):
            chunk_info = chunk_with_evidence.chunk_info

            # Header with metadata
            header = f"\n[bold yellow]─── Excerpt {i}: {chunk_info.document} ───[/bold yellow]"
            chunk_panel.write(header)

            metadata = f"[dim]Lines {chunk_info.line_start}-{chunk_info.line_end} | Referenced by Facts: {', '.join(map(str, chunk_with_evidence.fact_ids))}[/dim]"
            chunk_panel.write(metadata)

            chunk_panel.write("")  # Blank line

            # Use focused context with line numbers instead of full chunk
            focused_text = self.chunk_manager.get_focused_context(
                chunk_info.text,
                chunk_with_evidence.evidence_texts,
                context_lines=5,
                start_line_num=chunk_info.line_start
            )

            chunk_panel.write(focused_text)
            chunk_panel.write("")  # Blank line

    def _build_commands_text(self) -> str:
        """Build the commands help text."""
        commands = [
            "[cyan]Ctrl+Enter[/cyan] Submit",
            "[cyan]↑[/cyan]          Previous",
            "[cyan]↓[/cyan]          Next",
            "[cyan]fact N[/cyan]     View fact",
            "",
            "[cyan]Esc[/cyan]        Back",
            "[cyan]?[/cyan]          Help",
        ]
        return "\n".join(commands)
