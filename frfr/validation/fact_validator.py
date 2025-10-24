"""
Validate extracted facts against source text.

Ensures that evidence quotes actually exist in the specified line ranges.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a single fact."""
    fact_index: int
    claim: str
    is_valid: bool
    error_message: str = ""
    actual_line_range: str = ""
    quote_snippet: str = ""
    was_recovered: bool = False  # True if fact was recovered from medium confidence
    corrected_quote: Optional[str] = None  # Updated quote if recovered
    corrected_location: Optional[str] = None  # Updated location if recovered


class FactValidator:
    """Validates extracted facts against source documents."""

    def __init__(self, text_file: Path, claude_client=None):
        """
        Initialize validator with source text.

        Args:
            text_file: Path to the source text file
            claude_client: Optional ClaudeClient for fact recovery
        """
        self.text_file = Path(text_file)
        with open(self.text_file, "r") as f:
            self.lines = f.readlines()

        self.claude_client = claude_client

        logger.info(f"Loaded {len(self.lines)} lines from {self.text_file}")

    def parse_line_range(self, location: str) -> Tuple[int, int]:
        """
        Parse line range from source_location string.

        Args:
            location: String like "Lines 10-20" or "Line 15"

        Returns:
            Tuple of (start_line, end_line) (1-indexed)
        """
        # Handle "Lines X-Y" or "Line X"
        location = location.replace("Lines", "").replace("Line", "").strip()

        if "-" in location:
            start, end = location.split("-")
            return int(start.strip()), int(end.strip())
        else:
            line_num = int(location.strip())
            return line_num, line_num

    def normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.

        Removes extra whitespace, newlines, and normalizes quotes.
        """
        # Replace multiple whitespace/newlines with single space
        text = " ".join(text.split())

        # Normalize various quote types
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")

        # Remove common OCR artifacts
        text = text.replace(" –", "–").replace("– ", "–")

        return text.strip()

    def get_line_text(self, start_line: int, end_line: int) -> str:
        """
        Get text from specified line range.

        Args:
            start_line: Starting line (1-indexed)
            end_line: Ending line (1-indexed)

        Returns:
            Combined text from line range
        """
        # Convert to 0-indexed
        start_idx = start_line - 1
        end_idx = end_line

        # Clamp to valid range
        start_idx = max(0, start_idx)
        end_idx = min(len(self.lines), end_idx)

        # Get lines and join
        text = "".join(self.lines[start_idx:end_idx])
        return text

    def find_quote_in_text(
        self, quote: str, text: str, context_lines: int = 5
    ) -> Tuple[bool, str]:
        """
        Search for quote in text with fuzzy matching.

        Args:
            quote: The evidence quote to find
            text: The text to search in
            context_lines: Number of lines to expand search if not found

        Returns:
            Tuple of (found, actual_location)
        """
        normalized_quote = self.normalize_text(quote)
        normalized_text = self.normalize_text(text)

        # Try exact match first
        if normalized_quote in normalized_text:
            return True, "exact match"

        # Try partial match (at least 70% of quote present)
        # V4.1 FIX: Relaxed from 80% to 70% to reduce false rejections
        quote_words = normalized_quote.split()
        text_words = normalized_text.split()

        # Check if most quote words appear in order
        quote_idx = 0
        matched_words = 0

        for text_word in text_words:
            if quote_idx < len(quote_words) and text_word.lower() == quote_words[quote_idx].lower():
                matched_words += 1
                quote_idx += 1

        match_ratio = matched_words / len(quote_words) if quote_words else 0

        if match_ratio >= 0.7:  # Relaxed from 0.8 to 0.7
            return True, f"partial match ({match_ratio:.0%})"

        return False, f"not found (only {match_ratio:.0%} match)"

    def attempt_fact_recovery(
        self, claim: str, original_quote: str, search_context: str, start_line: int, end_line: int
    ) -> Optional[Tuple[str, str]]:
        """
        Attempt to recover a medium-confidence fact by finding the correct quote.

        Uses LLM to search the context and find the exact quote that supports the claim.

        Args:
            claim: The factual claim
            original_quote: The original (invalid) quote
            search_context: The text context to search in
            start_line: Starting line of search context
            end_line: Ending line of search context

        Returns:
            Tuple of (corrected_quote, corrected_location) or None if recovery failed
        """
        if not self.claude_client:
            logger.debug("No Claude client available for fact recovery")
            return None

        logger.info(f"Attempting recovery for claim: {claim[:60]}...")

        prompt = f"""You are helping recover a fact that was extracted but the evidence quote couldn't be validated.

**Claim**: {claim}

**Original Quote (not found)**: {original_quote}

**Context** (Lines {start_line}-{end_line}):
{search_context}

Your task:
1. Search the context for text that DIRECTLY supports the claim
2. Extract the EXACT quote (word-for-word) from the context
3. Identify the approximate line numbers where the quote appears

Respond with ONLY a JSON object:
{{
  "found": true/false,
  "quote": "exact quote from context if found",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

If the claim is NOT supported by this context, set found to false.
"""

        try:
            response = self.claude_client.prompt(prompt, max_tokens=1000)

            # Parse JSON response
            import json
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()

            result = json.loads(response)

            if result.get("found") and result.get("confidence", 0) >= 0.8:
                recovered_quote = result["quote"]

                # Verify the recovered quote actually exists in context
                found, match_type = self.find_quote_in_text(recovered_quote, search_context)

                if found:
                    logger.info(f"Successfully recovered fact with {result['confidence']:.0%} confidence")
                    return recovered_quote, f"Lines {start_line}-{end_line}"

            logger.debug(f"Recovery failed: {result.get('reasoning', 'unknown reason')}")
            return None

        except Exception as e:
            logger.warning(f"Fact recovery failed: {e}")
            return None

    def validate_fact(self, fact: Dict, fact_index: int, chunk_text: Optional[str] = None) -> ValidationResult:
        """
        Validate a single fact.

        Args:
            fact: Fact dictionary with claim, evidence_quote (V4) or evidence_quotes (V5), source_location
            fact_index: Index of this fact for reporting
            chunk_text: Optional chunk text to validate against (instead of full document)

        Returns:
            ValidationResult
        """
        claim = fact.get("claim", "")
        location = fact.get("source_location", "")

        # V5: Support both single evidence_quote (V4) and evidence_quotes array (V5)
        quotes_to_validate = []

        # Check for V5 format first (evidence_quotes array)
        evidence_quotes = fact.get("evidence_quotes", [])
        if evidence_quotes and isinstance(evidence_quotes, list) and len(evidence_quotes) > 0:
            # V5 format: multiple quotes
            quotes_to_validate = [eq.get("quote", "") if isinstance(eq, dict) else eq for eq in evidence_quotes]
        else:
            # V4 format: single quote
            single_quote = fact.get("evidence_quote", "")
            if single_quote:
                quotes_to_validate = [single_quote]

        # If no quotes found, validation fails
        if not quotes_to_validate:
            return ValidationResult(
                fact_index=fact_index,
                claim=claim[:80],
                is_valid=False,
                error_message="No evidence quotes found (neither evidence_quote nor evidence_quotes)",
                actual_line_range=location,
                quote_snippet="",
            )

        # V5: Validate ALL quotes (all must pass for fact to be valid)
        # V4.5: If chunk_text is provided, validate against chunk instead of full document
        if chunk_text:
            # Search for each quote in chunk text directly
            failed_quotes = []
            all_valid = True

            for quote in quotes_to_validate:
                found, match_type = self.find_quote_in_text(quote, chunk_text)
                if not found:
                    all_valid = False
                    failed_quotes.append((quote[:40], match_type))

            if all_valid:
                # All quotes validated successfully
                quote_snippet = quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0]
                if len(quotes_to_validate) > 1:
                    quote_snippet += f" (+{len(quotes_to_validate)-1} more)"

                return ValidationResult(
                    fact_index=fact_index,
                    claim=claim[:80],
                    is_valid=True,
                    actual_line_range=location,
                    quote_snippet=quote_snippet,
                )
            else:
                # Some quotes not found in chunk - fail validation
                error_msg = f"{len(failed_quotes)}/{len(quotes_to_validate)} quotes not found in chunk"
                return ValidationResult(
                    fact_index=fact_index,
                    claim=claim[:80],
                    is_valid=False,
                    error_message=error_msg,
                    actual_line_range=location,
                    quote_snippet=quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0],
                )

        # Original validation logic (against full document)
        # Parse line range
        try:
            start_line, end_line = self.parse_line_range(location)
        except Exception as e:
            return ValidationResult(
                fact_index=fact_index,
                claim=claim[:80],
                is_valid=False,
                error_message=f"Invalid location format: {location}",
            )

        # Get text from specified lines
        line_text = self.get_line_text(start_line, end_line)

        # V5: Validate ALL quotes against line text
        all_found = True
        failed_quotes = []
        match_types = []

        for quote in quotes_to_validate:
            found, match_type = self.find_quote_in_text(quote, line_text)
            match_types.append(match_type)
            if not found:
                all_found = False
                failed_quotes.append(quote)

        # If all quotes found, success
        if all_found:
            quote_snippet = quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0]
            if len(quotes_to_validate) > 1:
                quote_snippet += f" (+{len(quotes_to_validate)-1} more)"

            return ValidationResult(
                fact_index=fact_index,
                claim=claim[:80],
                is_valid=True,
                actual_line_range=f"Lines {start_line}-{end_line}",
                quote_snippet=quote_snippet,
            )

        # If not found, try expanding the search range for failed quotes
        expanded_start = max(1, start_line - 5)
        expanded_end = min(len(self.lines), end_line + 5)
        expanded_text = self.get_line_text(expanded_start, expanded_end)

        all_found_expanded = True
        expanded_match_types = []

        for quote in quotes_to_validate:
            found_expanded, match_type_expanded = self.find_quote_in_text(quote, expanded_text)
            expanded_match_types.append(match_type_expanded)
            if not found_expanded:
                all_found_expanded = False

        if all_found_expanded:
            quote_snippet = quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0]
            if len(quotes_to_validate) > 1:
                quote_snippet += f" (+{len(quotes_to_validate)-1} more)"

            return ValidationResult(
                fact_index=fact_index,
                claim=claim[:80],
                is_valid=True,
                actual_line_range=f"Lines {expanded_start}-{expanded_end} (expanded search)",
                quote_snippet=quote_snippet,
            )

        # Not found even with expanded search - attempt recovery if quote was close
        # V4.1 FIX: Define "medium confidence" as 40-69% match (adjusted from 40-79%)
        # since we now accept 70%+ as valid
        # V5: For multiple quotes, check if ANY quote had medium confidence
        # Parse match ratio from strings like "not found (only 17% match)" or "partial match (80%)"
        best_match_ratio = 0
        best_quote_for_recovery = quotes_to_validate[0]

        for i, match_type_expanded in enumerate(expanded_match_types):
            if "%" in match_type_expanded:
                try:
                    # Extract percentage number from string
                    import re
                    match = re.search(r'(\d+)%', match_type_expanded)
                    if match:
                        match_ratio = float(match.group(1)) / 100
                        if match_ratio > best_match_ratio:
                            best_match_ratio = match_ratio
                            best_quote_for_recovery = quotes_to_validate[i]
                except (ValueError, AttributeError):
                    pass

        if 0.4 <= best_match_ratio < 0.7:  # Adjusted from 0.8 to 0.7
            logger.info(f"Medium confidence fact ({best_match_ratio:.0%}), attempting recovery...")

            # Try recovery with even wider context
            recovery_start = max(1, start_line - 20)
            recovery_end = min(len(self.lines), end_line + 20)
            recovery_context = self.get_line_text(recovery_start, recovery_end)

            recovery_result = self.attempt_fact_recovery(
                claim, best_quote_for_recovery, recovery_context, recovery_start, recovery_end
            )

            if recovery_result:
                corrected_quote, corrected_location = recovery_result
                logger.info(f"✓ Recovered fact: {claim[:60]}...")
                return ValidationResult(
                    fact_index=fact_index,
                    claim=claim[:80],
                    is_valid=True,
                    actual_line_range=corrected_location,
                    quote_snippet=corrected_quote[:60] + "..." if len(corrected_quote) > 60 else corrected_quote,
                    was_recovered=True,
                    corrected_quote=corrected_quote,
                    corrected_location=corrected_location,
                )

        # Not found and recovery failed/not attempted
        # V5: Report how many quotes failed
        error_msg = f"{len(failed_quotes)}/{len(quotes_to_validate)} quotes not found in specified lines or nearby"
        if expanded_match_types:
            error_msg += f" (best match: {expanded_match_types[0]})"

        return ValidationResult(
            fact_index=fact_index,
            claim=claim[:80],
            is_valid=False,
            error_message=error_msg,
            actual_line_range=f"Lines {start_line}-{end_line}",
            quote_snippet=quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0],
        )

    def validate_facts(self, facts: List[Dict]) -> List[ValidationResult]:
        """
        Validate all facts.

        Args:
            facts: List of fact dictionaries

        Returns:
            List of ValidationResults
        """
        results = []

        for i, fact in enumerate(facts):
            result = self.validate_fact(fact, i)
            results.append(result)

            if not result.is_valid:
                logger.warning(f"Fact {i} invalid: {result.error_message}")

        return results

    def validate_session(
        self, session_dir: Path, document_name: str
    ) -> Tuple[List[ValidationResult], Dict]:
        """
        Validate all facts from a session.

        Args:
            session_dir: Path to session directory
            document_name: Name of the document

        Returns:
            Tuple of (validation_results, summary_stats)
        """
        facts_dir = session_dir / "facts"

        # Load all fact files
        all_facts = []
        fact_files = sorted(facts_dir.glob(f"{document_name}_chunk_*.json"))

        for fact_file in fact_files:
            with open(fact_file, "r") as f:
                chunk_facts = json.load(f)
                all_facts.extend(chunk_facts)

        logger.info(f"Loaded {len(all_facts)} facts from {len(fact_files)} chunks")

        # Validate all facts
        results = self.validate_facts(all_facts)

        # Calculate stats
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count

        stats = {
            "total_facts": len(results),
            "valid_facts": valid_count,
            "invalid_facts": invalid_count,
            "validation_rate": valid_count / len(results) if results else 0,
        }

        return results, stats


def validate_consolidated_facts(
    consolidated_file: Path, text_file: Path
) -> Tuple[List[ValidationResult], Dict]:
    """
    Validate facts from a consolidated facts JSON file.

    Args:
        consolidated_file: Path to consolidated_facts.json
        text_file: Path to source text file

    Returns:
        Tuple of (validation_results, summary_stats)
    """
    with open(consolidated_file, "r") as f:
        data = json.load(f)

    # Get all facts from all documents
    all_facts = []
    for doc_name, doc_data in data.get("documents", {}).items():
        facts = doc_data.get("facts", [])
        all_facts.extend(facts)

    # Create validator and validate
    validator = FactValidator(text_file)
    results = validator.validate_facts(all_facts)

    # Calculate stats
    valid_count = sum(1 for r in results if r.is_valid)
    invalid_count = len(results) - valid_count

    stats = {
        "total_facts": len(results),
        "valid_facts": valid_count,
        "invalid_facts": invalid_count,
        "validation_rate": valid_count / len(results) if results else 0,
    }

    return results, stats
