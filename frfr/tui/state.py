"""Global state management for the TUI application."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from frfr.session import Session


@dataclass
class SessionInfo:
    """Information about a session for display in the browser."""

    session_id: str
    session_dir: Path
    name: str
    created_at: datetime
    status: str
    document_count: int
    total_facts: int
    documents: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_session(cls, session: Session) -> "SessionInfo":
        """Create SessionInfo from a Session object."""
        stats = session.get_stats()
        documents = session.get_documents()

        # Get current name from name_history (last entry) or fallback to session_id
        name_history = session.metadata.get("name_history", [])
        current_name = name_history[-1]["name"] if name_history else session.session_id

        # Store documents with their keys for proper referencing
        doc_list = []
        for doc_key, doc_info in documents.items():
            doc_entry = dict(doc_info)
            doc_entry["_doc_key"] = doc_key  # Store the registry key
            doc_list.append(doc_entry)

        return cls(
            session_id=session.session_id,
            session_dir=session.session_dir,
            name=current_name,
            created_at=datetime.fromisoformat(stats.get("created_at", datetime.now().isoformat())),
            status=stats.get("status", "unknown"),
            document_count=stats.get("document_count", 0),
            total_facts=stats.get("total_facts", 0),
            documents=doc_list,
        )

    @classmethod
    def from_metadata_file(cls, session_dir: Path) -> Optional["SessionInfo"]:
        """Create SessionInfo by loading metadata from disk."""
        metadata_file = session_dir / "metadata.json"
        if not metadata_file.exists():
            return None

        try:
            import json
            with open(metadata_file) as f:
                metadata = json.load(f)

            documents = metadata.get("document_registry", {})
            # Store documents with their keys for proper referencing
            doc_list = []
            for doc_key, doc_info in documents.items():
                doc_entry = dict(doc_info)
                doc_entry["_doc_key"] = doc_key  # Store the registry key
                doc_list.append(doc_entry)

            # Count total facts across all documents
            total_facts = 0
            for doc_info in doc_list:
                # Facts file path is relative to project root, not session dir
                facts_file_path = doc_info.get("facts_file", "")
                if facts_file_path:
                    facts_file = Path(facts_file_path)
                    if facts_file.exists():
                        with open(facts_file) as ff:
                            facts_data = json.load(ff)
                            # Handle nested structure
                            if "documents" in facts_data:
                                for nested_doc_data in facts_data.get("documents", {}).values():
                                    total_facts += len(nested_doc_data.get("facts", []))
                            else:
                                total_facts += len(facts_data.get("facts", []))

            # Get current name from name_history (last entry) or fallback to session_id
            name_history = metadata.get("name_history", [])
            current_name = name_history[-1]["name"] if name_history else metadata.get("session_id", session_dir.name)

            return cls(
                session_id=session_dir.name,  # Use directory name as source of truth
                session_dir=session_dir,
                name=current_name,
                created_at=datetime.fromisoformat(
                    metadata.get("created_at", datetime.now().isoformat())
                ),
                status=metadata.get("status", "unknown"),
                document_count=len(documents),
                total_facts=total_facts,
                documents=doc_list,
            )
        except Exception as e:
            import traceback
            print(f"ERROR loading session metadata from {session_dir}:")
            print(f"  {type(e).__name__}: {e}")
            traceback.print_exc()
            return None


@dataclass
class AppState:
    """Global application state for the TUI."""

    # Sessions
    sessions: List[SessionInfo] = field(default_factory=list)
    current_session: Optional[Session] = None
    current_session_info: Optional[SessionInfo] = None

    # Storage
    session_storage_dir: Path = field(default_factory=lambda: Path(".frfr_sessions"))

    # Query history
    query_history: List[str] = field(default_factory=list)

    # UI state
    selected_document: Optional[str] = None

    def load_sessions(self) -> None:
        """Load all available sessions from the storage directory."""
        self.sessions = []

        if not self.session_storage_dir.exists():
            return

        for session_dir in sorted(self.session_storage_dir.iterdir(), reverse=True):
            if session_dir.is_dir() and session_dir.name.startswith("sess_"):
                session_info = SessionInfo.from_metadata_file(session_dir)
                if session_info:
                    self.sessions.append(session_info)

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a specific session by ID."""
        session_dir = self.session_storage_dir / session_id
        if not session_dir.exists():
            return None

        # Create Session object pointing to the existing session
        session = Session(session_id=session_id)
        self.current_session = session

        # Update current session info
        self.current_session_info = SessionInfo.from_session(session)

        return session

    def refresh_current_session(self) -> None:
        """Refresh the current session info from disk."""
        if self.current_session:
            self.current_session_info = SessionInfo.from_session(self.current_session)

    def add_query_to_history(self, query: str) -> None:
        """Add a query to the history."""
        if query and (not self.query_history or self.query_history[-1] != query):
            self.query_history.append(query)
            # Keep only last 100 queries
            if len(self.query_history) > 100:
                self.query_history = self.query_history[-100:]
