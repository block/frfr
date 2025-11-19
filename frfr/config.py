"""Configuration management for Frfr."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def get_data_dir() -> str:
    """Get the base data directory for frfr.

    Respects FRFR_DATA_DIR environment variable for custom locations.
    Defaults to ~/Documents/frfr for cross-platform, user-visible storage.
    """
    data_dir = os.environ.get("FRFR_DATA_DIR")
    if data_dir:
        return str(Path(data_dir).expanduser())
    return str(Path("~/Documents/frfr").expanduser())


@dataclass
class FrfrConfig:
    """Configuration for Frfr system."""

    # Swarm configuration
    swarm_size: int = 5
    swarm_model: str = "claude-sonnet-4"
    swarm_temperature: float = 1.0  # Will be varied with different seeds

    # Judge configuration
    judge_model: str = "claude-opus-4"
    judge_temperature: float = 0.0  # Deterministic for consistency

    # Consensus configuration
    consensus_threshold: float = 0.8  # Plurality threshold (80% or "all but one")
    similarity_threshold: float = 0.85  # Semantic similarity for clustering

    # Document processing
    chunk_size: int = 4000  # Characters per chunk
    chunk_overlap: int = 200  # Overlap between chunks

    # Temporal configuration
    temporal_namespace: str = "frfr"
    temporal_task_queue: str = "frfr-tasks"

    # Storage
    session_storage_dir: str = field(
        default_factory=lambda: os.path.join(get_data_dir(), "sessions")
    )
    inputs_dir: str = field(default_factory=lambda: os.path.join(get_data_dir(), "inputs"))

    # API configuration (assumes pre-configured environment)
    anthropic_api_key: Optional[str] = None  # Falls back to ANTHROPIC_API_KEY env var


# Default configuration instance
default_config = FrfrConfig()
