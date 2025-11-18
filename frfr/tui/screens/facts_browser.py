"""Facts browser screen for viewing and filtering facts."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Input, Select, ListView, ListItem, Label
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel


class FactItem(ListItem):
    """A list item representing a single fact."""

    def __init__(self, fact: Dict[str, Any], index: int):
        super().__init__()
        self.fact = fact
        self.fact_index = index

    def compose(self) -> ComposeResult:
        """Compose the fact item."""
        # Build the fact display
        claim = self.fact.get("claim", "No claim")
        confidence = self.fact.get("confidence", 0.0)
        fact_type = self.fact.get("fact_type", "unknown")
        source_location = self.fact.get("source_location", "Unknown")

        # Confidence indicator
        confidence_stars = "●" * int(confidence * 5) + "○" * (5 - int(confidence * 5))

        # Fact type badge
        type_badge = f"[{fact_type}]" if fact_type else ""

        # Format the display
        header = f"[bold cyan]Fact #{self.fact_index + 1}[/bold cyan] {type_badge} {confidence_stars}"
        yield Static(header, classes="fact-claim")
        yield Static(f"{claim}", classes="fact-claim")
        yield Static(f"[dim]{source_location}[/dim]", classes="fact-metadata")


class FactsBrowserScreen(Screen):
    """Screen for browsing and filtering facts."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("enter", "view_detail", "Detail"),
        Binding("slash", "focus_search", "Search", key_display="/"),
        Binding("f", "toggle_filter", "Filter"),
    ]

    def __init__(self, session_id: str, document_name: Optional[str] = None):
        super().__init__()
        self.session_id = session_id
        self.document_name = document_name
        self.all_facts: List[Dict[str, Any]] = []
        self.filtered_facts: List[Dict[str, Any]] = []
        self.selected_fact: Optional[Dict[str, Any]] = None
        self._search_timer: Optional[Any] = None  # Debounce timer for search
        self._pending_search: str = ""  # Pending search term

    def compose(self) -> ComposeResult:
        """Compose the facts browser layout."""
        with Container():
            yield Static("[bold]Facts Browser[/bold]", classes="title")
            with Horizontal():
                # Left panel: Search and filters
                with Vertical(id="left-panel"):
                    yield Label("[bold]Search & Filters[/bold]")
                    yield Input(placeholder="Search facts...", id="search-input")
                    yield Label("\n[bold]Filters[/bold]")
                    yield Static("Type: [dim]All[/dim]", id="filter-type")
                    yield Static("Confidence: [dim]> 0.0[/dim]", id="filter-confidence")
                    yield Static(f"\n[cyan]{len(self.filtered_facts)} facts[/cyan]", id="fact-count")
                    yield Label("\n[bold]Commands[/bold]")
                    yield Static(self._build_commands_text(), id="commands-panel")

                # Middle panel: Facts list
                with Vertical(id="right-panel"):
                    yield Label("[bold]Facts[/bold]")
                    yield ListView(id="facts-list")

    def on_mount(self) -> None:
        """Initialize the screen when mounted."""
        # Load facts
        self.load_facts()

        # Set initial filtered facts
        self.filtered_facts = self.all_facts.copy()

        # Show notification if no facts found
        if not self.all_facts:
            self.app.notify(
                f"No facts found for session {self.session_id}",
                severity="warning"
            )

        # Populate the list
        self.refresh_facts_list()

    def load_facts(self) -> None:
        """Load facts from the session."""
        session_dir = Path(".frfr_sessions") / self.session_id

        # Load facts from session metadata
        metadata_file = session_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file) as f:
                metadata = json.load(f)
                documents = metadata.get("document_registry", {})

                # Collect facts from specified document or all documents
                for doc_name, doc_info in documents.items():
                    # If specific document requested, skip others
                    if self.document_name and doc_name != self.document_name:
                        continue

                    # Facts file path is relative to project root
                    facts_file_path = doc_info.get("facts_file", "")
                    if facts_file_path:
                        facts_file = Path(facts_file_path)
                        if facts_file.exists():
                            with open(facts_file) as ff:
                                facts_data = json.load(ff)
                                # Facts might be nested under documents > doc_name > facts
                                if "documents" in facts_data:
                                    for nested_doc_name, nested_doc_data in facts_data.get("documents", {}).items():
                                        self.all_facts.extend(nested_doc_data.get("facts", []))
                                else:
                                    # Fallback to top-level facts
                                    self.all_facts.extend(facts_data.get("facts", []))

    def refresh_facts_list(self) -> None:
        """Refresh the facts list view."""
        facts_list = self.query_one("#facts-list", ListView)
        facts_list.clear()

        # Add fact items to the list
        for i, fact in enumerate(self.filtered_facts):
            facts_list.append(FactItem(fact, i))

        # Update count
        count_widget = self.query_one("#fact-count", Static)
        count_widget.update(f"\n[cyan]{len(self.filtered_facts)} facts[/cyan]")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with debouncing."""
        if event.input.id == "search-input":
            # Cancel previous timer if exists
            if self._search_timer is not None:
                self._search_timer.stop()

            # Store the search term
            self._pending_search = event.value

            # Set a new timer to execute search after 300ms of no typing
            self._search_timer = self.set_timer(
                0.3,  # 300ms delay
                lambda: self._execute_search(self._pending_search)
            )

    def _execute_search(self, search_term: str) -> None:
        """Execute the search filtering (called after debounce delay)."""
        # Run search in background to avoid blocking UI
        self.run_worker(
            self._search_worker(search_term),
            exclusive=False
        )

    async def _search_worker(self, search_term: str) -> None:
        """Background worker for search filtering."""
        import asyncio

        search_term = search_term.lower()

        # Show searching indicator briefly
        count_widget = self.query_one("#fact-count", Static)
        count_widget.update("\n[yellow]Searching...[/yellow]")

        # Give UI a chance to update
        await asyncio.sleep(0.01)

        # Perform filtering
        if search_term:
            self.filtered_facts = [
                fact for fact in self.all_facts
                if search_term in fact.get("claim", "").lower()
            ]
        else:
            self.filtered_facts = self.all_facts.copy()

        # Refresh the list on main thread
        self.call_from_thread(self.refresh_facts_list)
        self._search_timer = None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle fact selection."""
        if isinstance(event.item, FactItem):
            self.selected_fact = event.item.fact
            # Show fact detail
            self.show_fact_detail()

    def show_fact_detail(self) -> None:
        """Show detailed view of the selected fact."""
        if not self.selected_fact:
            return

        # Format fact details
        claim = self.selected_fact.get("claim", "No claim")
        evidence = self.selected_fact.get("evidence_quote", "No evidence")
        confidence = self.selected_fact.get("confidence", 0.0)
        fact_type = self.selected_fact.get("fact_type", "Unknown")
        source_location = self.selected_fact.get("source_location", "Unknown")

        # Create detail message
        detail = f"""
[bold]Claim:[/bold]
{claim}

[bold]Evidence:[/bold]
{evidence}

[bold]Type:[/bold] {fact_type}
[bold]Confidence:[/bold] {confidence:.2f}
[bold]Source:[/bold] {source_location}
"""
        self.app.notify(detail, severity="information", timeout=10)

    def action_go_back(self) -> None:
        """Go back to the previous screen."""
        self.app.pop_screen()

    def action_view_detail(self) -> None:
        """View detailed information about the selected fact."""
        if self.selected_fact:
            self.show_fact_detail()
        else:
            self.app.notify("No fact selected", severity="warning")

    def action_focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()

    def action_toggle_filter(self) -> None:
        """Toggle filter panel."""
        # TODO: Implement filter toggle
        self.app.notify("Filter options coming soon!", severity="information")

    def _build_commands_text(self) -> str:
        """Build the commands help text."""
        commands = [
            "[cyan]↑/↓[/cyan]    Navigate",
            "[cyan]Enter[/cyan]  View detail",
            "[cyan]/[/cyan]      Search",
            "[cyan]f[/cyan]      Filters",
            "",
            "[cyan]Esc[/cyan]    Back",
            "[cyan]q[/cyan]      Quit",
            "[cyan]?[/cyan]      Help",
        ]
        return "\n".join(commands)
