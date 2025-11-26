"""Progress tracking for document processing operations."""

import json
import time
import fcntl
import os
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum


class ProcessingStage(str, Enum):
    """Stages of processing for a chunk."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    VALIDATING = "validating"
    VALIDATED = "validated"
    COMPLETED = "completed"
    FAILED = "failed"
    # Document-level stages (not per-chunk)
    MULTIPASS_CUEC = "multipass_cuec"
    MULTIPASS_TEST = "multipass_test"
    MULTIPASS_QUANTITATIVE = "multipass_quantitative"
    MULTIPASS_TECHNICAL = "multipass_technical"
    GLOBAL_QV_CHECK = "global_qv_check"
    FINALIZING = "finalizing"


@dataclass
class ChunkProgress:
    """Progress information for a single chunk."""
    chunk_id: int
    stage: ProcessingStage
    facts_extracted: int = 0
    facts_valid: int = 0
    facts_recovered: int = 0
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class DocumentProgress:
    """Progress information for a document."""
    document_name: str
    total_chunks: int
    chunks: Dict[int, ChunkProgress]
    started_at: str
    updated_at: str
    completed_at: Optional[str] = None
    document_stage: Optional[ProcessingStage] = None  # For document-level stages (multipass, QV check)

    def get_stage_counts(self) -> Dict[str, int]:
        """Get count of chunks in each stage."""
        counts = {stage.value: 0 for stage in ProcessingStage}
        for chunk in self.chunks.values():
            counts[chunk.stage] += 1
        return counts

    def get_progress_percentage(self) -> float:
        """Calculate overall progress percentage."""
        if self.total_chunks == 0:
            return 0.0

        # Chunk-level stages (0-85% of total progress)
        chunk_stage_weights = {
            ProcessingStage.PENDING: 0.0,
            ProcessingStage.EXTRACTING: 0.2,
            ProcessingStage.EXTRACTED: 0.4,
            ProcessingStage.VALIDATING: 0.65,
            ProcessingStage.VALIDATED: 0.85,
            ProcessingStage.COMPLETED: 0.85,
            ProcessingStage.FAILED: 0.0,
            # Document-level stages don't apply to chunks
            ProcessingStage.MULTIPASS_CUEC: 0.85,
            ProcessingStage.MULTIPASS_TEST: 0.85,
            ProcessingStage.MULTIPASS_QUANTITATIVE: 0.85,
            ProcessingStage.MULTIPASS_TECHNICAL: 0.85,
            ProcessingStage.GLOBAL_QV_CHECK: 0.85,
            ProcessingStage.FINALIZING: 0.85,
        }

        # Calculate chunk progress (0-85%)
        chunk_progress = sum(chunk_stage_weights[chunk.stage] for chunk in self.chunks.values())
        chunk_percentage = (chunk_progress / self.total_chunks) * 100 if self.total_chunks > 0 else 0

        # Add document-level progress (85-100%)
        document_progress = 0.0
        if hasattr(self, 'document_stage') and self.document_stage:
            if self.document_stage == ProcessingStage.MULTIPASS_CUEC:
                document_progress = 85.0 + (0 * 2.5)  # 85%
            elif self.document_stage == ProcessingStage.MULTIPASS_TEST:
                document_progress = 85.0 + (1 * 2.5)  # 87.5%
            elif self.document_stage == ProcessingStage.MULTIPASS_QUANTITATIVE:
                document_progress = 85.0 + (2 * 2.5)  # 90%
            elif self.document_stage == ProcessingStage.MULTIPASS_TECHNICAL:
                document_progress = 85.0 + (3 * 2.5)  # 92.5%
            elif self.document_stage == ProcessingStage.GLOBAL_QV_CHECK:
                document_progress = 95.0
            elif self.document_stage == ProcessingStage.FINALIZING:
                document_progress = 98.0
            else:
                document_progress = 0.0

        # If all chunks completed, use document-level progress
        if chunk_percentage >= 85.0:
            return document_progress if document_progress > 85.0 else chunk_percentage
        return chunk_percentage


class ProgressTracker:
    """Tracks and persists processing progress."""

    def __init__(self, session_dir: Path, document_name: str):
        """
        Initialize progress tracker.

        Args:
            session_dir: Session directory path
            document_name: Name of document being processed
        """
        self.session_dir = Path(session_dir)
        self.document_name = document_name
        self.progress_file = self.session_dir / f"progress_{document_name}.json"
        self.progress: Optional[DocumentProgress] = None

    def initialize(self, total_chunks: int) -> None:
        """
        Initialize progress tracking for a document.

        Args:
            total_chunks: Total number of chunks to process
        """
        self.progress = DocumentProgress(
            document_name=self.document_name,
            total_chunks=total_chunks,
            chunks={
                i: ChunkProgress(chunk_id=i, stage=ProcessingStage.PENDING)
                for i in range(total_chunks)
            },
            started_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._save()

    def load(self) -> Optional[DocumentProgress]:
        """
        Load progress from disk.

        Returns:
            DocumentProgress if file exists, None otherwise
        """
        if not self.progress_file.exists():
            return None

        try:
            with open(self.progress_file) as f:
                data = json.load(f)

            # Reconstruct from dict
            chunks = {
                int(chunk_id): ChunkProgress(**chunk_data)
                for chunk_id, chunk_data in data["chunks"].items()
            }

            self.progress = DocumentProgress(
                document_name=data["document_name"],
                total_chunks=data["total_chunks"],
                chunks=chunks,
                started_at=data["started_at"],
                updated_at=data["updated_at"],
                completed_at=data.get("completed_at"),
                document_stage=ProcessingStage(data["document_stage"]) if data.get("document_stage") else None,
            )

            return self.progress

        except Exception as e:
            print(f"Warning: Failed to load progress file: {e}")
            return None

    def update_chunk(
        self,
        chunk_id: int,
        stage: ProcessingStage,
        facts_extracted: Optional[int] = None,
        facts_valid: Optional[int] = None,
        facts_recovered: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Update progress for a specific chunk.

        Args:
            chunk_id: Chunk identifier
            stage: Current processing stage
            facts_extracted: Number of facts extracted (optional)
            facts_valid: Number of valid facts (optional)
            facts_recovered: Number of recovered facts (optional)
            error: Error message if failed (optional)
        """
        if not self.progress:
            raise RuntimeError("Progress not initialized. Call initialize() first.")

        if chunk_id not in self.progress.chunks:
            raise ValueError(f"Invalid chunk_id: {chunk_id}")

        chunk = self.progress.chunks[chunk_id]
        chunk.stage = stage

        if facts_extracted is not None:
            chunk.facts_extracted = facts_extracted
        if facts_valid is not None:
            chunk.facts_valid = facts_valid
        if facts_recovered is not None:
            chunk.facts_recovered = facts_recovered
        if error is not None:
            chunk.error = error

        # Update timestamps
        if chunk.started_at is None:
            chunk.started_at = datetime.now().isoformat()

        if stage in [ProcessingStage.COMPLETED, ProcessingStage.FAILED]:
            chunk.completed_at = datetime.now().isoformat()

        self.progress.updated_at = datetime.now().isoformat()
        self._save()

    def mark_completed(self) -> None:
        """Mark the entire document as completed."""
        if not self.progress:
            raise RuntimeError("Progress not initialized.")

        self.progress.completed_at = datetime.now().isoformat()
        self.progress.updated_at = datetime.now().isoformat()
        self._save()

    def update_document_stage(self, stage: ProcessingStage) -> None:
        """
        Update the document-level processing stage (multipass, QV check, etc.).

        Args:
            stage: Document-level processing stage
        """
        if not self.progress:
            raise RuntimeError("Progress not initialized. Call initialize() first.")

        self.progress.document_stage = stage
        self.progress.updated_at = datetime.now().isoformat()
        self._save()

    def _save(self) -> None:
        """Save progress to disk with file locking to prevent race conditions."""
        if not self.progress:
            return

        # Ensure session directory exists (with retry for race conditions)
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.session_dir.mkdir(parents=True, exist_ok=True)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    import logging
                    logging.warning(f"Failed to create session directory after {max_retries} attempts: {e}")
                    return
                time.sleep(0.1)  # Brief wait before retry

        # Convert to dict
        data = {
            "document_name": self.progress.document_name,
            "total_chunks": self.progress.total_chunks,
            "chunks": {
                str(chunk_id): asdict(chunk)
                for chunk_id, chunk in self.progress.chunks.items()
            },
            "started_at": self.progress.started_at,
            "updated_at": self.progress.updated_at,
            "completed_at": self.progress.completed_at,
            "document_stage": self.progress.document_stage.value if self.progress.document_stage else None,
        }

        # Use a lock file to prevent concurrent writes from parallel workers
        lock_file_path = self.progress_file.with_suffix(".lock")
        temp_file = self.progress_file.with_suffix(".tmp")
        lock_file = None

        try:
            # Acquire exclusive lock with timeout to prevent deadlocks
            lock_file = open(lock_file_path, "w")

            # Try to acquire lock with timeout
            max_lock_wait = 10  # seconds
            lock_acquired = False
            start_time = time.time()

            while not lock_acquired and (time.time() - start_time) < max_lock_wait:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                except BlockingIOError:
                    # Lock held by another process, wait briefly and retry
                    time.sleep(0.1)

            if not lock_acquired:
                import logging
                logging.warning(f"Could not acquire lock for progress file after {max_lock_wait}s, skipping save")
                return

            try:
                # Write to temp file then atomically replace
                # Ensure parent directory still exists (might have been deleted by another process)
                temp_file.parent.mkdir(parents=True, exist_ok=True)

                with open(temp_file, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk

                # Atomic replace - temp file should exist now
                if temp_file.exists():
                    temp_file.replace(self.progress_file)
                else:
                    import logging
                    logging.warning(f"Temp file disappeared before replace: {temp_file}")

            finally:
                # Release lock
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except:
                    pass

        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except:
                    pass
            # Don't raise - log but continue processing
            import logging
            logging.warning(f"Failed to save progress file: {e}")
        finally:
            # Close and clean up lock file
            if lock_file:
                try:
                    lock_file.close()
                except:
                    pass

            if lock_file_path.exists():
                try:
                    lock_file_path.unlink()
                except:
                    pass

    def cleanup(self) -> None:
        """Remove progress file after completion."""
        if self.progress_file.exists():
            self.progress_file.unlink()


def get_document_progress(session_dir: Path, document_name: str) -> Optional[DocumentProgress]:
    """
    Get progress for a document.

    Args:
        session_dir: Session directory
        document_name: Document name

    Returns:
        DocumentProgress if available, None otherwise
    """
    tracker = ProgressTracker(session_dir, document_name)
    return tracker.load()


def get_all_progress(session_dir: Path) -> Dict[str, DocumentProgress]:
    """
    Get progress for all documents in a session.

    Args:
        session_dir: Session directory

    Returns:
        Dict mapping document names to their progress
    """
    session_path = Path(session_dir)
    progress_files = session_path.glob("progress_*.json")

    result = {}
    for progress_file in progress_files:
        # Extract document name from filename: progress_{doc_name}.json
        doc_name = progress_file.stem.replace("progress_", "")
        tracker = ProgressTracker(session_path, doc_name)
        progress = tracker.load()
        if progress:
            result[doc_name] = progress

    return result


def get_incomplete_chunks(session_dir: Path, document_name: str) -> List[int]:
    """
    Get list of chunk IDs that are not completed.

    Args:
        session_dir: Session directory
        document_name: Document name

    Returns:
        List of chunk IDs that need processing (not in completed state)
    """
    progress = get_document_progress(session_dir, document_name)
    if not progress:
        return []

    incomplete = []
    for chunk_id, chunk in progress.chunks.items():
        if chunk.stage != ProcessingStage.COMPLETED:
            incomplete.append(chunk_id)

    return sorted(incomplete)


def get_progress_summary(session_dir: Path, document_name: str) -> Optional[dict]:
    """
    Get summary of progress for a document.

    Args:
        session_dir: Session directory
        document_name: Document name

    Returns:
        Dict with progress summary: {"total": int, "completed": int, "incomplete": int, "failed": int}
        Returns None if no progress file exists
    """
    progress = get_document_progress(session_dir, document_name)
    if not progress:
        return None

    stage_counts = progress.get_stage_counts()
    completed = stage_counts.get(ProcessingStage.COMPLETED.value, 0)
    failed = stage_counts.get(ProcessingStage.FAILED.value, 0)
    total = progress.total_chunks
    incomplete = total - completed

    return {
        "total": total,
        "completed": completed,
        "incomplete": incomplete,
        "failed": failed,
    }
