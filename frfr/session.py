"""
Session management for temporary storage and state.
"""

import json
import os
import re
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime


def sanitize_session_name(name: str, max_length: int = 50) -> str:
    """
    Sanitize a session name for filesystem use.

    Args:
        name: The name to sanitize
        max_length: Maximum length of the resulting name

    Returns:
        A filesystem-safe name
    """
    # Convert to lowercase
    name = name.lower()

    # Replace spaces and special characters with underscores
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '_', name)

    # Remove leading/trailing underscores
    name = name.strip('_')

    # Truncate to max length
    if len(name) > max_length:
        name = name[:max_length].rstrip('_')

    # Ensure it's not empty
    if not name:
        name = "session"

    return name


def generate_session_name_with_llm(document_names: List[str]) -> str:
    """
    Generate a succinct session name based on document names using Claude.

    Args:
        document_names: List of document names (without extensions)

    Returns:
        A succinct session name (will be sanitized by caller)
    """
    try:
        from frfr.extraction.claude_client import ClaudeClient

        claude = ClaudeClient()

        # Prepare the prompt
        doc_list = "\n".join(f"- {name}" for name in document_names)

        prompt = f"""Given these document names, generate a succinct 2-5 word title that captures the essence of what these documents are about:

{doc_list}

Requirements:
- 2-5 words maximum
- Descriptive and specific
- No special characters
- Suitable as a folder name

Examples:
- "soc2_audit_report"
- "vendor_security_assessment"
- "compliance_documentation"
- "quarterly_financial_review"

Respond with ONLY the title, nothing else."""

        response = claude.prompt(prompt, max_tokens=50)

        # Clean up the response
        title = response.strip().strip('"').strip("'")

        # If response is too long or empty, fallback
        if not title or len(title) > 100:
            return "_".join(document_names[:3])

        return title

    except Exception as e:
        # Fallback to joining document names if LLM fails
        print(f"Warning: Could not generate session name with LLM: {e}")
        return "_".join(document_names[:3])


class Session:
    """Manages a session directory for temporary artifacts."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        base_dir: str = ".frfr_sessions",
        inputs_dir: str = "inputs",
        outputs_dir: str = "outputs",
    ):
        """
        Initialize a session.

        Args:
            session_id: Optional session ID. If None, generates a new UUID.
            base_dir: Base directory for all sessions.
            inputs_dir: Directory for input document symlinks.
            outputs_dir: Directory for output transformations.
        """
        self.session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        self.base_dir = Path(base_dir)
        self.session_dir = self.base_dir / self.session_id

        # Input/output directories (at project root)
        self.inputs_dir = Path(inputs_dir)
        self.outputs_dir = Path(outputs_dir)

        # Create session directory
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Create inputs and outputs directories
        self.inputs_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)

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
            # Migrate old format if needed
            if "documents" in self.metadata and "document_registry" not in self.metadata:
                self.metadata["document_registry"] = {}
                for doc in self.metadata.get("documents", []):
                    self.metadata["document_registry"][doc] = {
                        "status": "completed",  # Assume old documents are complete
                    }
                del self.metadata["documents"]
                self._save_metadata()
            # Initialize name history if not present
            if "name_history" not in self.metadata:
                self.metadata["name_history"] = [
                    {
                        "name": self.session_id,
                        "timestamp": self.metadata.get("created_at", datetime.now().isoformat()),
                        "reason": "Initial creation"
                    }
                ]
                self._save_metadata()
        else:
            self.metadata = {
                "session_id": self.session_id,
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "document_registry": {},
                "name_history": [
                    {
                        "name": self.session_id,
                        "timestamp": datetime.now().isoformat(),
                        "reason": "Initial creation"
                    }
                ]
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

        # Update metadata - ensure document exists in registry
        registry = self.metadata.setdefault("document_registry", {})
        if document_name not in registry:
            registry[document_name] = {
                "status": "processing",
                "added_at": datetime.now().isoformat(),
            }
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
        import glob as glob_module
        all_facts = []
        # Escape special characters in document name for glob pattern
        escaped_name = glob_module.escape(document_name)
        for facts_file in sorted(self.facts_dir.glob(f"{escaped_name}_chunk_*.json")):
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
        import glob as glob_module
        chunk_ids = []
        # Escape special characters in document name for glob pattern
        escaped_name = glob_module.escape(document_name)
        for facts_file in self.facts_dir.glob(f"{escaped_name}_chunk_*.json"):
            # Extract chunk ID from filename (e.g., "doc_chunk_0005.json" -> 5)
            filename = facts_file.stem
            chunk_part = filename.split("_chunk_")[-1]
            chunk_id = int(chunk_part)
            chunk_ids.append(chunk_id)
        return sorted(chunk_ids)

    def get_stats(self) -> dict:
        """Get session statistics."""
        registry = self.metadata.get("document_registry", {})
        stats = {
            "session_id": self.session_id,
            "session_dir": str(self.session_dir),
            "documents": list(registry.keys()),
            "total_fact_files": len(list(self.facts_dir.glob("*.json"))),
            "total_chunks": len(list(self.chunks_dir.glob("*.txt"))),
        }

        # Add per-document stats
        for doc in registry.keys():
            processed = self.get_processed_chunks(doc)
            if processed:
                stats[f"{doc}_processed_chunks"] = processed
                stats[f"{doc}_last_chunk"] = max(processed)
            stats[f"{doc}_status"] = registry[doc].get("status", "unknown")

        return stats

    def cleanup(self):
        """Mark session as completed."""
        self.metadata["status"] = "completed"
        self.metadata["completed_at"] = datetime.now().isoformat()
        self._save_metadata()

    def add_document(self, pdf_path: str, document_name: Optional[str] = None, auto_rename: bool = True) -> Dict[str, Any]:
        """
        Add a document to the session and create symlink.

        Args:
            pdf_path: Absolute path to the PDF file
            document_name: Optional document name (defaults to filename without extension)
            auto_rename: Whether to automatically regenerate session name (default: True)

        Returns:
            Document info dictionary with all paths, including 'session_renamed' and 'new_session_id' keys
        """
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        # Determine document name
        if document_name is None:
            document_name = pdf_path.stem

        # Check if document already exists in registry
        registry = self.metadata.setdefault("document_registry", {})
        is_new_document = document_name not in registry

        # Create symlink in inputs directory
        symlink_path = self.inputs_dir / pdf_path.name
        if not symlink_path.exists():
            os.symlink(pdf_path, symlink_path)

        # Prepare output paths
        text_file = self.outputs_dir / f"{document_name}_text.txt"
        facts_file = self.facts_dir / f"{document_name}_facts.json"

        # Register document (or update existing)
        registry[document_name] = {
            "original_pdf_path": str(pdf_path),
            "symlink_path": str(symlink_path),
            "text_file": str(text_file),
            "facts_file": str(facts_file),
            "status": "pending",
            "added_at": registry.get(document_name, {}).get("added_at", datetime.now().isoformat()),
        }
        self._save_metadata()

        # Only regenerate session name if this is a NEW document
        result = dict(registry[document_name])
        result["session_renamed"] = False

        if auto_rename and is_new_document:
            new_session_id = self.regenerate_session_name(use_llm=True)
            if new_session_id:
                result["session_renamed"] = True
                result["new_session_id"] = new_session_id

        return result

    def get_documents(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all documents in the session.

        Returns:
            Dictionary mapping document names to their info
        """
        return self.metadata.get("document_registry", {})

    def get_document_info(self, document_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific document.

        Args:
            document_name: Name of the document

        Returns:
            Document info dictionary or None if not found
        """
        registry = self.metadata.get("document_registry", {})
        return registry.get(document_name)

    def update_document_status(
        self, document_name: str, status: str, **kwargs
    ) -> None:
        """
        Update document status.

        Args:
            document_name: Name of the document
            status: New status (pending, processing, completed, failed)
            **kwargs: Additional fields to update (e.g., error_message, completed_at)
        """
        registry = self.metadata.setdefault("document_registry", {})
        if document_name not in registry:
            raise ValueError(f"Document not found in registry: {document_name}")

        registry[document_name]["status"] = status
        for key, value in kwargs.items():
            registry[document_name][key] = value

        self._save_metadata()

    def get_document_paths(self, document_name: str) -> Optional[Dict[str, str]]:
        """
        Get all paths for a document.

        Args:
            document_name: Name of the document

        Returns:
            Dictionary with original_pdf_path, symlink_path, text_file, facts_file
        """
        doc_info = self.get_document_info(document_name)
        if doc_info is None:
            return None

        return {
            "original_pdf_path": doc_info.get("original_pdf_path"),
            "symlink_path": doc_info.get("symlink_path"),
            "text_file": doc_info.get("text_file"),
            "facts_file": doc_info.get("facts_file"),
        }

    def _rename_session_directory(self, new_session_id: str) -> None:
        """
        Rename the session directory and update all internal paths.

        Args:
            new_session_id: The new session ID
        """
        old_session_dir = self.session_dir
        new_session_dir = self.base_dir / new_session_id

        # Rename the directory
        old_session_dir.rename(new_session_dir)

        # Update instance variables
        old_session_id = self.session_id
        self.session_id = new_session_id
        self.session_dir = new_session_dir

        # Update subdirectory paths
        self.summaries_dir = self.session_dir / "summaries"
        self.facts_dir = self.session_dir / "facts"
        self.chunks_dir = self.session_dir / "chunks"
        self.metadata_file = self.session_dir / "metadata.json"

        # Update metadata
        self.metadata["session_id"] = new_session_id

        # Update all file paths in document registry
        for doc_name, doc_info in self.metadata.get("document_registry", {}).items():
            for path_key in ["text_file", "facts_file", "symlink_path"]:
                if path_key in doc_info and old_session_id in doc_info[path_key]:
                    doc_info[path_key] = doc_info[path_key].replace(old_session_id, new_session_id)

        # Add to name history
        history_entry = {
            "name": new_session_id,
            "timestamp": datetime.now().isoformat(),
            "reason": f"Renamed from {old_session_id}",
            "previous_name": old_session_id
        }
        self.metadata.setdefault("name_history", []).append(history_entry)

        self._save_metadata()

    def regenerate_session_name(self, use_llm: bool = True) -> Optional[str]:
        """
        Regenerate session name based on current documents.

        Args:
            use_llm: Whether to use LLM to generate the name

        Returns:
            The new session ID if renamed, None if no change
        """
        # Get current document names
        registry = self.metadata.get("document_registry", {})
        if not registry:
            return None

        document_names = list(registry.keys())

        # Generate new session name
        # Extract timestamp from current session_id if it has one
        current_timestamp = None
        parts = self.session_id.split("_")
        if len(parts) >= 2:
            # Check if last part looks like a timestamp
            last_part = parts[-1]
            if len(last_part) == 6 and last_part.isdigit():  # HHMMSS format
                # Check if second to last is a date
                if len(parts) >= 3:
                    date_part = parts[-2]
                    if len(date_part) == 8 and date_part.isdigit():  # YYYYMMDD format
                        current_timestamp = f"{date_part}_{last_part}"

        # Generate new base name
        if use_llm:
            title = generate_session_name_with_llm(document_names)
        else:
            title = "_".join(document_names[:3])

        sanitized = sanitize_session_name(title)

        # Use current timestamp if available, otherwise generate new one
        if current_timestamp:
            new_session_id = f"sess_{sanitized}_{current_timestamp}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_session_id = f"sess_{sanitized}_{timestamp}"

        # Only rename if the name actually changed
        if new_session_id != self.session_id:
            self._rename_session_directory(new_session_id)
            return new_session_id

        return None

    @staticmethod
    def generate_session_id(document_names: List[str], use_llm: bool = True) -> str:
        """
        Generate a session ID based on document names.

        Args:
            document_names: List of document names (without extensions)
            use_llm: Whether to use LLM to generate a succinct title

        Returns:
            A session ID with format "sess_<name>"
        """
        if not document_names:
            return f"sess_{uuid.uuid4().hex[:12]}"

        if use_llm:
            # Use LLM to generate a succinct title
            title = generate_session_name_with_llm(document_names)
        else:
            # Fallback: join first 3 document names
            title = "_".join(document_names[:3])

        # Sanitize the name for filesystem
        sanitized = sanitize_session_name(title)

        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return f"sess_{sanitized}_{timestamp}"

    def __repr__(self):
        return f"Session(id={self.session_id}, dir={self.session_dir})"
