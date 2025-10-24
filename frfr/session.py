"""
Session management for temporary storage and state.
"""

import json
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime


class Session:
    """Manages a session directory for temporary artifacts."""

    def __init__(self, session_id: Optional[str] = None, base_dir: str = ".frfr_sessions"):
        """
        Initialize a session.

        Args:
            session_id: Optional session ID. If None, generates a new UUID.
            base_dir: Base directory for all sessions.
        """
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self.base_dir = Path(base_dir)
        self.session_dir = self.base_dir / self.session_id

        # Create session directory
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        self.summaries_dir = self.session_dir / "summaries"
        self.facts_dir = self.session_dir / "facts"
        self.chunks_dir = self.session_dir / "chunks"

        self.summaries_dir.mkdir(exist_ok=True)
        self.facts_dir.mkdir(exist_ok=True)
        self.chunks_dir.mkdir(exist_ok=True)

        # Metadata
        self.metadata_file = self.session_dir / "metadata.json"
        self._init_metadata()

    def _init_metadata(self):
        """Initialize or load session metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, "r") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "documents": [],
                "status": "active",
            }
            self._save_metadata()

    def _save_metadata(self):
        """Save session metadata."""
        with open(self.metadata_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

    def save_summary(self, document_name: str, summary: dict):
        """
        Save document summary.

        Args:
            document_name: Name of the document
            summary: Summary dictionary
        """
        summary_file = self.summaries_dir / f"{document_name}.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        # Update metadata
        if document_name not in self.metadata.get("documents", []):
            self.metadata.setdefault("documents", []).append(document_name)
            self._save_metadata()

    def load_summary(self, document_name: str) -> Optional[dict]:
        """
        Load document summary.

        Args:
            document_name: Name of the document

        Returns:
            Summary dictionary or None if not found
        """
        summary_file = self.summaries_dir / f"{document_name}.json"
        if summary_file.exists():
            with open(summary_file, "r") as f:
                return json.load(f)
        return None

    def save_chunk_facts(self, document_name: str, chunk_id: int, facts: list):
        """
        Save facts extracted from a chunk.

        Args:
            document_name: Name of the document
            chunk_id: Chunk number
            facts: List of extracted facts
        """
        facts_file = self.facts_dir / f"{document_name}_chunk_{chunk_id:04d}.json"
        with open(facts_file, "w") as f:
            json.dump(facts, f, indent=2)

    def load_all_facts(self, document_name: str) -> list:
        """
        Load all facts for a document across all chunks.

        Args:
            document_name: Name of the document

        Returns:
            List of all extracted facts
        """
        all_facts = []
        for facts_file in sorted(self.facts_dir.glob(f"{document_name}_chunk_*.json")):
            with open(facts_file, "r") as f:
                facts = json.load(f)
                all_facts.extend(facts)
        return all_facts

    def save_chunk_text(self, document_name: str, chunk_id: int, text: str):
        """
        Save chunk text for debugging/inspection.

        Args:
            document_name: Name of the document
            chunk_id: Chunk number
            text: Chunk text
        """
        chunk_file = self.chunks_dir / f"{document_name}_chunk_{chunk_id:04d}.txt"
        with open(chunk_file, "w") as f:
            f.write(text)

    def get_processed_chunks(self, document_name: str) -> list[int]:
        """
        Get list of chunk IDs that have already been processed.

        Args:
            document_name: Name of the document

        Returns:
            Sorted list of chunk IDs
        """
        chunk_ids = []
        for facts_file in self.facts_dir.glob(f"{document_name}_chunk_*.json"):
            # Extract chunk ID from filename (e.g., "doc_chunk_0005.json" -> 5)
            filename = facts_file.stem
            chunk_part = filename.split("_chunk_")[-1]
            chunk_id = int(chunk_part)
            chunk_ids.append(chunk_id)
        return sorted(chunk_ids)

    def get_stats(self) -> dict:
        """Get session statistics."""
        stats = {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "documents": self.metadata.get("documents", []),
            "total_fact_files": len(list(self.facts_dir.glob("*.json"))),
            "total_chunks": len(list(self.chunks_dir.glob("*.txt"))),
        }

        # Add per-document stats
        for doc in self.metadata.get("documents", []):
            processed = self.get_processed_chunks(doc)
            if processed:
                stats[f"{doc}_processed_chunks"] = processed
                stats[f"{doc}_last_chunk"] = max(processed)

        return stats

    def cleanup(self):
        """Mark session as completed."""
        self.metadata["status"] = "completed"
        self.metadata["completed_at"] = datetime.now().isoformat()
        self._save_metadata()

    def __repr__(self):
        return f"Session(id={self.session_id}, dir={self.session_dir})"
