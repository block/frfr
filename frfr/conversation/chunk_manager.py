"""
Chunk Manager for conversation context.

This module handles loading, mapping, and scoring of text chunks to provide
rich context for conversations. It bridges extracted facts with their source
chunks to enable smarter, context-aware responses.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class ChunkInfo:
    """Information about a text chunk."""
    chunk_id: str  # e.g., "chunk_0005"
    document: str  # Document filename
    text: str  # Full chunk text
    line_start: int  # Starting line number
    line_end: int  # Ending line number
    source_path: Path  # Path to chunk file

    def get_metadata_string(self) -> str:
        """Get formatted metadata string for display."""
        return f"Document: {self.document} | Lines: {self.line_start}-{self.line_end}"


@dataclass
class ChunkWithEvidence:
    """Chunk with highlighted evidence."""
    chunk_info: ChunkInfo
    evidence_texts: List[str]  # List of evidence quotes to highlight
    relevance_score: float  # 0.0-1.0
    fact_ids: List[int]  # Which facts reference this chunk


class ChunkManager:
    """Manages text chunks for conversation context."""

    # Default chunk settings (must match FactExtractor defaults)
    DEFAULT_CHUNK_SIZE = 50
    DEFAULT_OVERLAP_SIZE = 10

    def __init__(self, session_path: Path, chunk_size: int = None, overlap_size: int = None):
        """
        Initialize ChunkManager.

        Args:
            session_path: Path to the session directory
            chunk_size: Lines per chunk (default: 50, matches FactExtractor)
            overlap_size: Lines of overlap (default: 10, matches FactExtractor)
        """
        self.session_path = session_path
        self.chunks_dir = session_path / "chunks"
        self._chunk_cache: Dict[str, ChunkInfo] = {}

        # Use provided values or defaults
        self.chunk_size = chunk_size if chunk_size is not None else self.DEFAULT_CHUNK_SIZE
        self.overlap_size = overlap_size if overlap_size is not None else self.DEFAULT_OVERLAP_SIZE

        # Calculate chunk advance (how many lines each chunk moves forward)
        self.chunk_advance = self.chunk_size - self.overlap_size

        # Auto-detect chunk settings from actual files if not provided
        if chunk_size is None or overlap_size is None:
            detected = self._detect_chunk_settings()
            if detected:
                self.chunk_size, self.overlap_size, self.chunk_advance = detected

        if not self.chunks_dir.exists():
            # Chunks directory doesn't exist, we'll operate in degraded mode
            pass

    def _detect_chunk_settings(self) -> Optional[tuple[int, int, int]]:
        """
        Auto-detect chunk size and overlap by examining actual chunk files.

        Returns:
            Tuple of (chunk_size, overlap_size, chunk_advance) or None if detection fails
        """
        if not self.chunks_dir.exists():
            return None

        try:
            # Find first two chunk files for any document
            chunk_files = sorted(self.chunks_dir.glob("*_chunk_*.txt"))
            if len(chunk_files) < 2:
                return None

            # Read first two chunks
            chunk0_text = chunk_files[0].read_text(encoding="utf-8")
            chunk1_text = chunk_files[1].read_text(encoding="utf-8")

            chunk0_lines = len(chunk0_text.splitlines())
            chunk1_lines = len(chunk1_text.splitlines())

            # Parse chunk IDs
            chunk0_id = int(chunk_files[0].stem.split("_")[-1])
            chunk1_id = int(chunk_files[1].stem.split("_")[-1])

            if chunk1_id != chunk0_id + 1:
                # Not consecutive chunks, can't detect reliably
                return None

            # For consecutive chunks, the advance is in the pattern:
            # If chunk_0 has lines and chunk_1 starts at position X,
            # then chunk_advance = X

            # We can estimate: chunk_size ≈ chunk0_lines (first chunk should be full size)
            # To find overlap, we need to know where chunk_1 starts
            # Since we don't have explicit line numbers in files, we use the pattern:
            # chunk_advance = chunk_size - overlap_size

            # Best guess: first chunk is full size
            detected_chunk_size = chunk0_lines

            # If both chunks are same size or close, overlap is likely small
            # If second chunk is notably smaller, there might be document end
            # For now, just use defaults but log that we attempted detection
            # This is hard without metadata, so we'll stick with defaults

            return None  # Defer to defaults for now

        except Exception:
            return None

    def load_chunk(self, document: str, chunk_id: str) -> Optional[ChunkInfo]:
        """
        Load a specific chunk by document and chunk ID.

        Args:
            document: Document name (without extension)
            chunk_id: Chunk ID (e.g., "chunk_0005" or just "0005")

        Returns:
            ChunkInfo if found, None otherwise
        """
        # Normalize chunk_id
        if not chunk_id.startswith("chunk_"):
            chunk_id = f"chunk_{chunk_id}"

        cache_key = f"{document}_{chunk_id}"

        # Check cache
        if cache_key in self._chunk_cache:
            return self._chunk_cache[cache_key]

        # Try to find the chunk file
        chunk_file = self.chunks_dir / f"{document}_{chunk_id}.txt"

        if not chunk_file.exists():
            return None

        try:
            text = chunk_file.read_text(encoding="utf-8")

            # Extract line numbers from the chunk file
            # Chunks are created with self.chunk_size lines and self.overlap_size overlap
            # So each chunk advances by self.chunk_advance lines (chunk_size - overlap_size)
            # Example with defaults (50, 10):
            #   chunk_0000: lines 1-50
            #   chunk_0001: lines 41-90 (overlaps 10 lines with chunk_0000)
            #   chunk_0002: lines 81-130 (overlaps 10 lines with chunk_0001)
            chunk_num = int(chunk_id.split("_")[-1])
            line_start = chunk_num * self.chunk_advance + 1
            line_end = line_start + len(text.splitlines()) - 1

            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                document=document,
                text=text,
                line_start=line_start,
                line_end=line_end,
                source_path=chunk_file
            )

            # Cache it
            self._chunk_cache[cache_key] = chunk_info
            return chunk_info

        except Exception:
            return None

    def find_chunk_for_fact(self, fact: Dict, document: str) -> Optional[ChunkInfo]:
        """
        Find the chunk that contains a given fact.

        Args:
            fact: Fact dictionary with source_location
            document: Document name

        Returns:
            ChunkInfo if found, None otherwise
        """
        source_location = fact.get("source_location", "")

        # Parse line numbers from source_location (e.g., "Lines 42-45")
        line_match = re.search(r'[Ll]ines?\s+(\d+)(?:-(\d+))?', source_location)

        if not line_match:
            return None

        start_line = int(line_match.group(1))

        # Estimate chunk ID based on line number
        # Chunks advance by self.chunk_advance lines (chunk_size - overlap_size)
        # So line N is in chunk floor((N-1) / chunk_advance)
        chunk_num = (start_line - 1) // self.chunk_advance
        chunk_id = f"chunk_{chunk_num:04d}"

        # Try to load this chunk
        chunk = self.load_chunk(document, chunk_id)

        # If not found, try adjacent chunks (due to overlap or rounding)
        if chunk is None and chunk_num > 0:
            chunk = self.load_chunk(document, f"chunk_{(chunk_num-1):04d}")

        if chunk is None:
            chunk = self.load_chunk(document, f"chunk_{(chunk_num+1):04d}")

        return chunk

    def get_chunks_for_facts(self, facts: List[Dict]) -> List[ChunkWithEvidence]:
        """
        Get all chunks referenced by a list of facts, with evidence highlights.

        Args:
            facts: List of fact dictionaries

        Returns:
            List of ChunkWithEvidence objects, deduplicated by chunk
        """
        chunk_map: Dict[str, ChunkWithEvidence] = {}

        for idx, fact in enumerate(facts):
            document = fact.get("source_doc", "").replace(".pdf", "")
            chunk = self.find_chunk_for_fact(fact, document)

            if chunk is None:
                continue

            chunk_key = f"{chunk.document}_{chunk.chunk_id}"

            # Get evidence quotes (support both V4 and V5 formats)
            evidence_texts = []

            # V5 format (multiple quotes)
            if "evidence_quotes" in fact and fact["evidence_quotes"]:
                evidence_texts = [eq["quote"] for eq in fact["evidence_quotes"]]
            # V4 format (single quote)
            elif "evidence_quote" in fact and fact["evidence_quote"]:
                evidence_texts = [fact["evidence_quote"]]

            if chunk_key in chunk_map:
                # Add to existing chunk
                chunk_map[chunk_key].evidence_texts.extend(evidence_texts)
                chunk_map[chunk_key].fact_ids.append(idx + 1)  # 1-indexed
            else:
                # Create new entry
                chunk_map[chunk_key] = ChunkWithEvidence(
                    chunk_info=chunk,
                    evidence_texts=evidence_texts,
                    relevance_score=fact.get("confidence", 0.5),
                    fact_ids=[idx + 1]  # 1-indexed
                )

        # Sort by relevance score (descending)
        chunks = sorted(chunk_map.values(), key=lambda c: c.relevance_score, reverse=True)

        return chunks

    def filter_chunks_by_query(self, chunks: List[ChunkWithEvidence], query: str, max_chunks: int = 10) -> List[ChunkWithEvidence]:
        """
        Filter and rank chunks based on query relevance.

        Args:
            chunks: List of ChunkWithEvidence objects
            query: User query string
            max_chunks: Maximum number of chunks to return

        Returns:
            Filtered and ranked list of chunks
        """
        if not query:
            return chunks[:max_chunks]

        # Simple keyword-based relevance scoring
        query_keywords = set(query.lower().split())

        scored_chunks = []
        for chunk in chunks:
            # Score based on keyword overlap
            chunk_text_lower = chunk.chunk_info.text.lower()
            keyword_matches = sum(1 for kw in query_keywords if kw in chunk_text_lower)

            # Combine with existing confidence score
            combined_score = (chunk.relevance_score * 0.5) + (keyword_matches / max(len(query_keywords), 1) * 0.5)

            scored_chunks.append((combined_score, chunk))

        # Sort by combined score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        return [chunk for _, chunk in scored_chunks[:max_chunks]]

    def highlight_evidence_in_text(self, text: str, evidence_texts: List[str], add_markers: bool = False) -> str:
        """
        Highlight evidence quotes within chunk text using Rich markup.

        Args:
            text: Full chunk text
            evidence_texts: List of evidence quotes to highlight
            add_markers: If True, add visual markers (arrows) next to highlighted lines

        Returns:
            Text with Rich markup for highlighting
        """
        if not evidence_texts:
            return text

        # Normalize text for better matching
        def normalize(s: str) -> str:
            return re.sub(r'\s+', ' ', s).strip()

        highlighted_text = text

        for evidence in evidence_texts:
            if not evidence:
                continue

            # Try exact match first
            if evidence in highlighted_text:
                if add_markers:
                    highlighted_text = highlighted_text.replace(
                        evidence,
                        f"[bold black on yellow]{evidence}[/bold black on yellow]"
                    )
                else:
                    highlighted_text = highlighted_text.replace(
                        evidence,
                        f"[bold yellow on blue]{evidence}[/bold yellow on blue]"
                    )
                continue

            # Try normalized fuzzy match
            norm_evidence = normalize(evidence)

            # Split text into lines and try to find partial matches
            lines = highlighted_text.split('\n')
            for i, line in enumerate(lines):
                norm_line = normalize(line)

                # Check if evidence is contained in this line
                if norm_evidence in norm_line or norm_line in norm_evidence:
                    # Highlight the entire line
                    if add_markers:
                        lines[i] = f"[bold black on yellow]{line}[/bold black on yellow]"
                    else:
                        lines[i] = f"[bold yellow on blue]{line}[/bold yellow on blue]"
                    break

            highlighted_text = '\n'.join(lines)

        return highlighted_text

    def get_lines_in_range(self, text: str, target_start: int, target_end: int, context_lines: int = 5, chunk_start_line: int = 1) -> str:
        """
        Get specific lines by line number with context.

        Args:
            text: Full chunk text
            target_start: Starting line number to highlight
            target_end: Ending line number to highlight
            context_lines: Lines of context before/after
            chunk_start_line: What line number the chunk starts at

        Returns:
            Formatted text with line numbers and highlighting
        """
        lines = text.split('\n')

        # Convert absolute line numbers to chunk-relative indices
        target_start_idx = target_start - chunk_start_line
        target_end_idx = target_end - chunk_start_line

        # Validate range
        if target_start_idx < 0 or target_end_idx >= len(lines):
            return f"[yellow]⚠️ Lines {target_start}-{target_end} are outside chunk range (lines {chunk_start_line}-{chunk_start_line + len(lines) - 1})[/yellow]"

        # Calculate context range
        start_idx = max(0, target_start_idx - context_lines)
        end_idx = min(len(lines), target_end_idx + context_lines + 1)

        # Build output with line numbers
        result_lines = []
        for i in range(start_idx, end_idx):
            line = lines[i]
            line_num = chunk_start_line + i
            line_num_str = f"{line_num:4d} │ "

            # Highlight target lines
            if target_start_idx <= i <= target_end_idx:
                result_lines.append(f"[bold black on yellow]{line_num_str}{line}[/bold black on yellow]")
            else:
                result_lines.append(f"[dim]{line_num_str}{line}[/dim]")

        return '\n'.join(result_lines)

    def get_focused_context(self, text: str, evidence_texts: List[str], context_lines: int = 5, start_line_num: int = 1) -> str:
        """
        Extract focused sections around evidence with context lines and line numbers.

        Args:
            text: Full chunk text
            evidence_texts: List of evidence quotes to find
            context_lines: Number of lines to show before/after evidence
            start_line_num: Starting line number for display

        Returns:
            Focused text sections with evidence highlighted and line numbers
        """
        if not evidence_texts:
            return text

        lines = text.split('\n')
        evidence_line_indices = set()

        # Normalize text for better matching - but be more conservative
        def normalize(s: str) -> str:
            # Only normalize whitespace, preserve case and punctuation
            return re.sub(r'\s+', ' ', s).strip().lower()

        # Find all lines that contain evidence - use more precise matching
        for evidence in evidence_texts:
            if not evidence or len(evidence.strip()) < 5:  # Skip very short evidence
                continue

            # Try exact match first (case insensitive)
            evidence_lower = evidence.lower()
            evidence_words = len(evidence.split())

            for i, line in enumerate(lines):
                line_lower = line.lower()

                # For multi-word evidence, use exact substring match
                if evidence_words >= 3:
                    # Exact substring match (case insensitive)
                    if evidence_lower in line_lower:
                        evidence_line_indices.add(i)
                        continue
                elif evidence_words == 2:
                    # For 2-word phrases, require word boundaries
                    import re as regex
                    # Use word boundary matching for 2-word phrases
                    pattern = r'\b' + regex.escape(evidence_lower) + r'\b'
                    if regex.search(pattern, line_lower):
                        evidence_line_indices.add(i)
                        continue
                else:
                    # For single words, require they're a significant part of the line
                    if evidence_lower in line_lower:
                        # Only match if the word is substantial relative to line
                        line_words = len(line.split())
                        if line_words <= 8:  # Short lines, single word can match
                            evidence_line_indices.add(i)
                            continue

                # Fuzzy match only for longer evidence strings (3+ words)
                if evidence_words >= 3:
                    norm_evidence = normalize(evidence)
                    norm_line = normalize(line)

                    # Check if normalized evidence is in normalized line
                    # AND the match is substantial
                    if norm_evidence in norm_line:
                        # Calculate match quality
                        match_ratio = len(norm_evidence) / max(len(norm_line), 1)
                        if match_ratio > 0.4:  # At least 40% of the line should be evidence
                            evidence_line_indices.add(i)

        if not evidence_line_indices:
            # No evidence found - return detailed message for debugging
            evidence_preview = evidence_texts[0][:100] if evidence_texts else "None"
            return f"""[yellow]⚠️ Evidence text not found in chunk.

Searched for: "{evidence_preview}"
Chunk contains {len(lines)} lines

This could mean:
- The evidence was paraphrased during extraction
- The fact references a different chunk
- The line numbers in source_location are incorrect

Try viewing a different fact or run a new query.[/yellow]"""

        # Build focused sections with context and line numbers
        focused_sections = []
        sorted_indices = sorted(evidence_line_indices)

        # Merge nearby evidence lines into single sections
        sections_ranges = []
        current_section = None

        for idx in sorted_indices:
            section_start = max(0, idx - context_lines)
            section_end = min(len(lines), idx + context_lines + 1)

            if current_section is None:
                current_section = [section_start, section_end, {idx}]
            elif section_start <= current_section[1]:
                # Overlapping sections, merge them
                current_section[1] = max(current_section[1], section_end)
                current_section[2].add(idx)
            else:
                # Non-overlapping, save current and start new
                sections_ranges.append(current_section)
                current_section = [section_start, section_end, {idx}]

        if current_section:
            sections_ranges.append(current_section)

        # Build sections with line numbers
        for start_idx, end_idx, evidence_indices in sections_ranges:
            section_lines = []

            for i in range(start_idx, end_idx):
                line = lines[i]
                line_num = start_line_num + i
                line_num_str = f"{line_num:4d} │ "  # Right-aligned, 4 chars wide

                if i in evidence_indices:
                    # This is the evidence line - highlight prominently with background only
                    section_lines.append(f"[bold black on yellow]{line_num_str}{line}[/bold black on yellow]")
                else:
                    # Context line - dimmed
                    section_lines.append(f"[dim]{line_num_str}{line}[/dim]")

            focused_sections.append('\n'.join(section_lines))

        # Add ellipsis between non-contiguous sections
        result = []
        for i, section in enumerate(focused_sections):
            result.append(section)
            if i < len(focused_sections) - 1:
                result.append("[dim]     │ ...[/dim]")

        return '\n'.join(result)

    def build_chunk_context(self, facts: List[Dict], query: str, token_budget: int = 10000) -> Tuple[str, List[ChunkWithEvidence]]:
        """
        Build chunk context string for prompt, respecting token budget.

        Args:
            facts: List of fact dictionaries
            query: User query
            token_budget: Maximum tokens for chunk context

        Returns:
            Tuple of (formatted context string, list of chunks used)
        """
        # Get all relevant chunks
        all_chunks = self.get_chunks_for_facts(facts)

        # Filter by query relevance
        relevant_chunks = self.filter_chunks_by_query(all_chunks, query, max_chunks=20)

        if not relevant_chunks:
            return "", []

        # Build context string, respecting token budget
        context_parts = ["### Full Context from Source Documents\n"]
        context_parts.append("The following are relevant excerpts from the source documents, providing full context for the facts:\n")

        used_chunks = []
        estimated_tokens = len(" ".join(context_parts)) // 4

        for chunk_with_evidence in relevant_chunks:
            chunk = chunk_with_evidence.chunk_info

            # Format chunk entry
            chunk_text = f"\n**{chunk.get_metadata_string()}** (Referenced by Facts: {', '.join(map(str, chunk_with_evidence.fact_ids))})\n"
            chunk_text += "```\n"
            chunk_text += chunk.text
            chunk_text += "\n```\n"

            # Estimate tokens (rough: 1 token ≈ 4 characters)
            chunk_tokens = len(chunk_text) // 4

            if estimated_tokens + chunk_tokens > token_budget:
                break

            context_parts.append(chunk_text)
            used_chunks.append(chunk_with_evidence)
            estimated_tokens += chunk_tokens

        return "\n".join(context_parts), used_chunks
