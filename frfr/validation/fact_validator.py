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
    corrected_quotes: Optional[List[str]] = None  # Multiple quotes if multi-quote recovery
    corrected_location: Optional[str] = None  # Updated location if recovered
    is_near_match: bool = False  # True if fact is approximately correct (~75-90% match)
    match_percentage: Optional[float] = None  # Actual match percentage for near matches
    recovery_method: Optional[str] = None  # Method used: "single_quote", "fuzzy_match", "multi_quote"


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

    def normalize_text(self, text: str, handle_ocr_artifacts: bool = True) -> str:
        """
        Normalize text for comparison.

        Aggressively removes extra whitespace, newlines, and normalizes quotes.
        This handles unexpected whitespace within quotes.

        Args:
            text: The text to normalize
            handle_ocr_artifacts: If True, applies OCR artifact corrections
        """
        # Replace all types of whitespace (spaces, tabs, newlines, etc.) with single space
        import re
        text = re.sub(r'\s+', ' ', text)

        # Normalize various quote types
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("'", "'").replace("'", "'")

        # Normalize dashes and hyphens
        text = text.replace("–", "-").replace("—", "-").replace("‐", "-")

        # Handle common OCR artifacts
        if handle_ocr_artifacts:
            # Common OCR substitutions (applied carefully to avoid false positives)
            # These are applied word-by-word to maintain context
            pass  # Will be handled in word-level matching

        # Remove common OCR artifacts and extra punctuation spacing
        text = re.sub(r'\s*([,;:.!?])\s*', r'\1 ', text)
        text = re.sub(r'\s+([)\]}])', r'\1', text)
        text = re.sub(r'([(\[{])\s+', r'\1', text)

        return text.strip()

    def levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Edit distance between the strings
        """
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def fuzzy_word_match(self, word1: str, word2: str, threshold: float = 0.85) -> bool:
        """
        Check if two words match with fuzzy matching (handles OCR artifacts).

        Args:
            word1: First word
            word2: Second word
            threshold: Similarity threshold (0.0 to 1.0)

        Returns:
            True if words are similar enough
        """
        # Exact match (case-insensitive)
        if word1.lower() == word2.lower():
            return True

        # Skip fuzzy matching for very short words (too many false positives)
        if len(word1) < 3 or len(word2) < 3:
            return False

        # Handle common OCR substitutions
        ocr_variants = {
            'l': ['I', '1', '|'],
            'I': ['l', '1', '|'],
            'O': ['0', 'o'],
            '0': ['O', 'o'],
            'rn': ['m'],
            'm': ['rn'],
            'vv': ['w'],
            'w': ['vv'],
            'cl': ['d'],
            'd': ['cl'],
        }

        # Try OCR substitutions
        w1_lower = word1.lower()
        w2_lower = word2.lower()

        for orig, variants in ocr_variants.items():
            if orig in w1_lower:
                for variant in variants:
                    if w1_lower.replace(orig, variant) == w2_lower:
                        return True
            if orig in w2_lower:
                for variant in variants:
                    if w2_lower.replace(orig, variant) == w1_lower:
                        return True

        # Calculate Levenshtein distance
        max_len = max(len(word1), len(word2))
        distance = self.levenshtein_distance(word1.lower(), word2.lower())
        similarity = 1.0 - (distance / max_len)

        return similarity >= threshold

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
        self, quote: str, text: str, use_fuzzy: bool = False, context_lines: int = 5
    ) -> Tuple[bool, str, float]:
        """
        Search for quote in text with fuzzy matching.

        Args:
            quote: The evidence quote to find
            text: The text to search in
            use_fuzzy: If True, use fuzzy word matching (more lenient)
            context_lines: Number of lines to expand search if not found

        Returns:
            Tuple of (found, match_description, match_ratio)
            - found: True if quote is valid (>= 90% match)
            - match_description: Human-readable description
            - match_ratio: Percentage match (0.0 to 1.0)
        """
        normalized_quote = self.normalize_text(quote)
        normalized_text = self.normalize_text(text)

        # Try exact match first
        if normalized_quote in normalized_text:
            return True, "exact match", 1.0

        # Try partial match with word-by-word sequential matching
        quote_words = normalized_quote.split()
        text_words = normalized_text.split()

        # Check if most quote words appear in order
        quote_idx = 0
        matched_words = 0

        if use_fuzzy:
            # Use fuzzy matching for words (handles OCR artifacts)
            for text_word in text_words:
                if quote_idx < len(quote_words):
                    if self.fuzzy_word_match(text_word, quote_words[quote_idx], threshold=0.85):
                        matched_words += 1
                        quote_idx += 1
        else:
            # Use exact word matching (original behavior)
            for text_word in text_words:
                if quote_idx < len(quote_words) and text_word.lower() == quote_words[quote_idx].lower():
                    matched_words += 1
                    quote_idx += 1

        match_ratio = matched_words / len(quote_words) if quote_words else 0

        # Classification:
        # >= 90%: Valid (exact or near-exact)
        # 75-89%: Near match (approximately correct, flagged for review)
        # 40-74%: Medium confidence (attempt recovery)
        # < 40%: Not found (reject)

        match_type = "fuzzy match" if use_fuzzy and matched_words > 0 else "match"

        if match_ratio >= 0.90:
            return True, f"near-exact {match_type} ({match_ratio:.0%})", match_ratio
        elif match_ratio >= 0.75:
            # This is a near match - not quite valid but close
            return False, f"near {match_type} ({match_ratio:.0%})", match_ratio
        elif match_ratio >= 0.40:
            return False, f"medium confidence {match_type} ({match_ratio:.0%})", match_ratio
        else:
            return False, f"not found (only {match_ratio:.0%} {match_type})", match_ratio

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

            if result.get("found") and result.get("confidence", 0) >= 0.6:  # Lowered from 0.8 to 0.6
                recovered_quote = result["quote"]

                # Verify the recovered quote actually exists in context
                found, match_type, match_ratio = self.find_quote_in_text(recovered_quote, search_context)

                if found:
                    logger.info(f"✓ Successfully recovered fact with {result['confidence']:.0%} confidence (match: {match_ratio:.0%})")
                    return recovered_quote, f"Lines {start_line}-{end_line}"
                else:
                    logger.warning(f"LLM found quote but it doesn't exist in context: {recovered_quote[:60]}...")

            logger.info(f"Recovery failed: confidence={result.get('confidence', 0):.0%}, found={result.get('found')}, reason={result.get('reasoning', 'unknown')[:60]}")
            return None

        except Exception as e:
            logger.warning(f"Fact recovery failed: {e}")
            return None

    def attempt_multi_quote_recovery(
        self, claim: str, original_quote: str, search_context: str, start_line: int, end_line: int
    ) -> Optional[List[Tuple[str, str]]]:
        """
        Attempt to recover a fact by finding multiple supporting quotes.

        Some claims synthesize information from multiple locations. This function
        uses LLM to identify if the claim needs multiple quotes and extracts them.

        Args:
            claim: The factual claim
            original_quote: The original (invalid) quote
            search_context: The text context to search in
            start_line: Starting line of search context
            end_line: Ending line of search context

        Returns:
            List of tuples (quote, location) or None if recovery failed
        """
        if not self.claude_client:
            logger.debug("No Claude client available for multi-quote recovery")
            return None

        logger.info(f"Attempting multi-quote recovery for claim: {claim[:60]}...")

        prompt = f"""You are helping recover a fact that combines information from multiple locations.

**Claim**: {claim}

**Original Quote (not found)**: {original_quote}

**Context** (Lines {start_line}-{end_line}):
{search_context}

Your task:
1. Determine if this claim requires MULTIPLE quotes to support it (e.g., it combines info from different places)
2. If yes, extract 2-3 EXACT quotes (word-for-word) from the context that TOGETHER support the claim
3. Each quote should support a specific part of the claim
4. Identify the approximate line numbers for each quote

Respond with ONLY a JSON object:
{{
  "needs_multiple_quotes": true/false,
  "quotes": [
    {{"quote": "exact quote 1", "supports": "what part of claim"}},
    {{"quote": "exact quote 2", "supports": "what part of claim"}}
  ],
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

If the claim does NOT need multiple quotes or cannot be supported by this context, set needs_multiple_quotes to false.
"""

        try:
            response = self.claude_client.prompt(prompt, max_tokens=1500)

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

            if result.get("needs_multiple_quotes") and result.get("confidence", 0) >= 0.6:
                quotes_data = result.get("quotes", [])

                if not quotes_data or len(quotes_data) < 2:
                    logger.warning("Multi-quote recovery: LLM returned less than 2 quotes")
                    return None

                # Validate each quote actually exists in context
                recovered_quotes = []
                for quote_data in quotes_data[:3]:  # Limit to 3 quotes max
                    quote_text = quote_data.get("quote", "")
                    if not quote_text:
                        continue

                    # Verify quote exists in context (>= 90% match)
                    found, match_type, match_ratio = self.find_quote_in_text(quote_text, search_context)

                    if found:
                        recovered_quotes.append((quote_text, f"Lines {start_line}-{end_line}"))
                        logger.debug(f"  ✓ Found quote: {quote_text[:40]}... ({match_ratio:.0%})")
                    else:
                        logger.warning(f"  ✗ Quote not found in context: {quote_text[:40]}... ({match_ratio:.0%})")

                # Success if we found at least 2 valid quotes
                if len(recovered_quotes) >= 2:
                    logger.info(f"✓ Successfully recovered {len(recovered_quotes)} quotes for multi-quote fact")
                    return recovered_quotes
                else:
                    logger.warning(f"Multi-quote recovery failed: only found {len(recovered_quotes)}/2+ valid quotes")
                    return None

            logger.info(f"Multi-quote recovery not applicable: needs_multiple={result.get('needs_multiple_quotes')}, confidence={result.get('confidence', 0):.0%}")
            return None

        except Exception as e:
            logger.warning(f"Multi-quote recovery failed: {e}")
            return None

    def progressive_fact_recovery(
        self, claim: str, original_quote: str, search_context: str, start_line: int, end_line: int,
        original_match_ratio: float
    ) -> Optional[Dict]:
        """
        Attempt progressive fact recovery using multiple strategies.

        Tries recovery in this order:
        1. Single-quote recovery (LLM finds correct quote)
        2. Fuzzy matching (if near match 75-89%, retry with OCR-tolerant matching)
        3. Multi-quote recovery (for claims combining multiple pieces of info)

        Args:
            claim: The factual claim
            original_quote: The original (invalid) quote
            search_context: The text context to search in
            start_line: Starting line of search context
            end_line: Ending line of search context
            original_match_ratio: The match ratio from initial validation

        Returns:
            Dict with recovery result or None if all strategies failed
            {
                "method": "single_quote" | "fuzzy_match" | "multi_quote",
                "quote": str,  # For single quote
                "quotes": List[str],  # For multi-quote
                "location": str
            }
        """
        logger.info(f"Starting progressive recovery (original match: {original_match_ratio:.0%})")

        # Strategy 1: Single-quote recovery (existing behavior)
        logger.debug("  Strategy 1: Single-quote LLM recovery...")
        single_result = self.attempt_fact_recovery(claim, original_quote, search_context, start_line, end_line)
        if single_result:
            corrected_quote, corrected_location = single_result
            logger.info(f"  ✓ Single-quote recovery succeeded")
            return {
                "method": "single_quote",
                "quote": corrected_quote,
                "location": corrected_location
            }

        # Strategy 2: Fuzzy matching (for near matches with OCR artifacts)
        # Only try this for near matches (75-89%)
        if 0.75 <= original_match_ratio < 0.90:
            logger.debug("  Strategy 2: Fuzzy matching with OCR tolerance...")
            found_fuzzy, match_type_fuzzy, match_ratio_fuzzy = self.find_quote_in_text(
                original_quote, search_context, use_fuzzy=True
            )
            if found_fuzzy:  # >= 90% with fuzzy matching
                logger.info(f"  ✓ Fuzzy matching succeeded ({match_ratio_fuzzy:.0%})")
                return {
                    "method": "fuzzy_match",
                    "quote": original_quote,
                    "location": f"Lines {start_line}-{end_line}"
                }

        # Strategy 3: Multi-quote recovery (for claims combining multiple sources)
        logger.debug("  Strategy 3: Multi-quote recovery...")
        multi_result = self.attempt_multi_quote_recovery(claim, original_quote, search_context, start_line, end_line)
        if multi_result:
            quotes = [q[0] for q in multi_result]
            location = multi_result[0][1]  # Use first quote's location
            logger.info(f"  ✓ Multi-quote recovery succeeded ({len(quotes)} quotes)")
            return {
                "method": "multi_quote",
                "quotes": quotes,
                "location": location
            }

        logger.warning(f"  ✗ All recovery strategies failed")
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
            match_ratios = []
            best_match_ratio = 0
            has_near_match = False

            for quote in quotes_to_validate:
                found, match_type, match_ratio = self.find_quote_in_text(quote, chunk_text)
                match_ratios.append(match_ratio)
                best_match_ratio = max(best_match_ratio, match_ratio)

                if not found:
                    all_valid = False
                    failed_quotes.append((quote[:40], match_type))
                    # Check if this is a near match (75-89%)
                    if 0.75 <= match_ratio < 0.90:
                        has_near_match = True

            if all_valid:
                # All quotes validated successfully (>= 90% match)
                quote_snippet = quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0]
                if len(quotes_to_validate) > 1:
                    quote_snippet += f" (+{len(quotes_to_validate)-1} more)"

                return ValidationResult(
                    fact_index=fact_index,
                    claim=claim[:80],
                    is_valid=True,
                    actual_line_range=location,
                    quote_snippet=quote_snippet,
                    match_percentage=best_match_ratio,
                )
            elif has_near_match or (0.4 <= best_match_ratio < 0.90):
                # Near match (75-89%) or medium confidence (40-74%) - attempt progressive recovery
                match_category = "near match" if best_match_ratio >= 0.75 else "medium confidence"
                logger.info(f"{match_category} fact in chunk ({best_match_ratio:.0%}), attempting progressive recovery...")

                # Find best quote for recovery
                best_quote_idx = match_ratios.index(max(match_ratios)) if match_ratios else 0
                best_quote_for_recovery = quotes_to_validate[best_quote_idx]

                # Attempt progressive recovery using the chunk text as context
                recovery_result = self.progressive_fact_recovery(
                    claim, best_quote_for_recovery, chunk_text, 0, len(chunk_text.split('\n')),
                    best_match_ratio
                )

                if recovery_result:
                    recovery_method = recovery_result["method"]
                    logger.info(f"✓ Recovered {match_category} fact from chunk using {recovery_method}: {claim[:60]}...")

                    # Handle single-quote or fuzzy match recovery
                    if recovery_method in ["single_quote", "fuzzy_match"]:
                        corrected_quote = recovery_result["quote"]
                        corrected_location = recovery_result["location"]
                        return ValidationResult(
                            fact_index=fact_index,
                            claim=claim[:80],
                            is_valid=True,
                            actual_line_range=corrected_location,
                            quote_snippet=corrected_quote[:60] + "..." if len(corrected_quote) > 60 else corrected_quote,
                            was_recovered=True,
                            corrected_quote=corrected_quote,
                            corrected_location=corrected_location,
                            is_near_match=(best_match_ratio >= 0.75),
                            match_percentage=best_match_ratio,
                            recovery_method=recovery_method,
                        )
                    # Handle multi-quote recovery
                    elif recovery_method == "multi_quote":
                        corrected_quotes = recovery_result["quotes"]
                        corrected_location = recovery_result["location"]
                        quote_snippet = corrected_quotes[0][:60] + "..." if len(corrected_quotes[0]) > 60 else corrected_quotes[0]
                        quote_snippet += f" (+{len(corrected_quotes)-1} more)"
                        return ValidationResult(
                            fact_index=fact_index,
                            claim=claim[:80],
                            is_valid=True,
                            actual_line_range=corrected_location,
                            quote_snippet=quote_snippet,
                            was_recovered=True,
                            corrected_quotes=corrected_quotes,
                            corrected_location=corrected_location,
                            is_near_match=(best_match_ratio >= 0.75),
                            match_percentage=best_match_ratio,
                            recovery_method=recovery_method,
                        )
                else:
                    # All recovery strategies failed
                    error_msg = f"{match_category} ({best_match_ratio:.0%}) - all recovery strategies failed"
                    return ValidationResult(
                        fact_index=fact_index,
                        claim=claim[:80],
                        is_valid=False,
                        error_message=error_msg,
                        actual_line_range=location,
                        quote_snippet=quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0],
                        is_near_match=(best_match_ratio >= 0.75),
                        match_percentage=best_match_ratio,
                    )
            else:
                # Match ratio too low (< 40%) - reject without recovery
                error_msg = f"{len(failed_quotes)}/{len(quotes_to_validate)} quotes not found in chunk (best: {best_match_ratio:.0%})"
                return ValidationResult(
                    fact_index=fact_index,
                    claim=claim[:80],
                    is_valid=False,
                    error_message=error_msg,
                    actual_line_range=location,
                    quote_snippet=quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0],
                    match_percentage=best_match_ratio,
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
        match_ratios = []
        best_match_ratio = 0
        has_near_match = False

        for quote in quotes_to_validate:
            found, match_type, match_ratio = self.find_quote_in_text(quote, line_text)
            match_types.append(match_type)
            match_ratios.append(match_ratio)
            best_match_ratio = max(best_match_ratio, match_ratio)

            if not found:
                all_found = False
                failed_quotes.append(quote)
                # Check if this is a near match (75-89%)
                if 0.75 <= match_ratio < 0.90:
                    has_near_match = True

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
                match_percentage=best_match_ratio,
            )

        # If not found, try expanding the search range for failed quotes
        expanded_start = max(1, start_line - 5)
        expanded_end = min(len(self.lines), end_line + 5)
        expanded_text = self.get_line_text(expanded_start, expanded_end)

        all_found_expanded = True
        expanded_match_types = []
        expanded_match_ratios = []
        best_expanded_ratio = 0
        has_near_match_expanded = False

        for quote in quotes_to_validate:
            found_expanded, match_type_expanded, match_ratio_expanded = self.find_quote_in_text(quote, expanded_text)
            expanded_match_types.append(match_type_expanded)
            expanded_match_ratios.append(match_ratio_expanded)
            best_expanded_ratio = max(best_expanded_ratio, match_ratio_expanded)

            if not found_expanded:
                all_found_expanded = False
                # Check if this is a near match (75-89%)
                if 0.75 <= match_ratio_expanded < 0.90:
                    has_near_match_expanded = True

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
                match_percentage=best_expanded_ratio,
            )

        # Not found even with expanded search - attempt recovery if quote was close
        # Near match: 75-89% match - ATTEMPT RECOVERY (these are approximately correct)
        # Medium confidence: 40-74% match - ATTEMPT RECOVERY
        # Valid: >= 90% match
        # Too low: < 40% match - reject

        # Find the quote with the best match ratio for recovery
        best_quote_idx = expanded_match_ratios.index(max(expanded_match_ratios)) if expanded_match_ratios else 0
        best_quote_for_recovery = quotes_to_validate[best_quote_idx]

        # Attempt recovery for near matches (75-89%) and medium confidence (40-74%)
        if 0.4 <= best_expanded_ratio < 0.90:  # Recovery range: 40-89%
            match_category = "near match" if best_expanded_ratio >= 0.75 else "medium confidence"
            logger.info(f"{match_category} fact ({best_expanded_ratio:.0%}), attempting progressive recovery...")

            # Try progressive recovery with even wider context
            recovery_start = max(1, start_line - 20)
            recovery_end = min(len(self.lines), end_line + 20)
            recovery_context = self.get_line_text(recovery_start, recovery_end)

            recovery_result = self.progressive_fact_recovery(
                claim, best_quote_for_recovery, recovery_context, recovery_start, recovery_end,
                best_expanded_ratio
            )

            if recovery_result:
                recovery_method = recovery_result["method"]
                logger.info(f"✓ Recovered {match_category} fact using {recovery_method}: {claim[:60]}...")

                # Handle single-quote or fuzzy match recovery
                if recovery_method in ["single_quote", "fuzzy_match"]:
                    corrected_quote = recovery_result["quote"]
                    corrected_location = recovery_result["location"]
                    return ValidationResult(
                        fact_index=fact_index,
                        claim=claim[:80],
                        is_valid=True,
                        actual_line_range=corrected_location,
                        quote_snippet=corrected_quote[:60] + "..." if len(corrected_quote) > 60 else corrected_quote,
                        was_recovered=True,
                        corrected_quote=corrected_quote,
                        corrected_location=corrected_location,
                        is_near_match=(best_expanded_ratio >= 0.75),
                        match_percentage=best_expanded_ratio,
                        recovery_method=recovery_method,
                    )
                # Handle multi-quote recovery
                elif recovery_method == "multi_quote":
                    corrected_quotes = recovery_result["quotes"]
                    corrected_location = recovery_result["location"]
                    quote_snippet = corrected_quotes[0][:60] + "..." if len(corrected_quotes[0]) > 60 else corrected_quotes[0]
                    quote_snippet += f" (+{len(corrected_quotes)-1} more)"
                    return ValidationResult(
                        fact_index=fact_index,
                        claim=claim[:80],
                        is_valid=True,
                        actual_line_range=corrected_location,
                        quote_snippet=quote_snippet,
                        was_recovered=True,
                        corrected_quotes=corrected_quotes,
                        corrected_location=corrected_location,
                        is_near_match=(best_expanded_ratio >= 0.75),
                        match_percentage=best_expanded_ratio,
                        recovery_method=recovery_method,
                    )
            else:
                # All recovery strategies failed - flag as near match that needs manual review
                if best_expanded_ratio >= 0.75:
                    quote_snippet = quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0]
                    if len(quotes_to_validate) > 1:
                        quote_snippet += f" (+{len(quotes_to_validate)-1} more)"

                    logger.warning(f"Near match ({best_expanded_ratio:.0%}) - all recovery strategies failed, cannot make citable")
                    return ValidationResult(
                        fact_index=fact_index,
                        claim=claim[:80],
                        is_valid=False,  # Not valid - needs correct quote
                        error_message=f"Near match ({best_expanded_ratio:.0%}) - all recovery strategies failed",
                        actual_line_range=f"Lines {expanded_start}-{expanded_end}",
                        quote_snippet=quote_snippet,
                        is_near_match=True,
                        match_percentage=best_expanded_ratio,
                    )

        # Not found and recovery failed/not attempted
        # V5: Report how many quotes failed
        error_msg = f"{len(failed_quotes)}/{len(quotes_to_validate)} quotes not found in specified lines or nearby"
        if expanded_match_types:
            error_msg += f" (best match: {best_expanded_ratio:.0%})"

        return ValidationResult(
            fact_index=fact_index,
            claim=claim[:80],
            is_valid=False,
            error_message=error_msg,
            actual_line_range=f"Lines {start_line}-{end_line}",
            quote_snippet=quotes_to_validate[0][:60] + "..." if len(quotes_to_validate[0]) > 60 else quotes_to_validate[0],
            match_percentage=best_expanded_ratio,
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
        import glob as glob_module
        all_facts = []
        # Escape special characters in document name for glob pattern
        escaped_name = glob_module.escape(document_name)
        fact_files = sorted(facts_dir.glob(f"{escaped_name}_chunk_*.json"))

        for fact_file in fact_files:
            with open(fact_file, "r") as f:
                chunk_facts = json.load(f)
                all_facts.extend(chunk_facts)

        logger.info(f"Loaded {len(all_facts)} facts from {len(fact_files)} chunks")

        # Validate all facts
        results = self.validate_facts(all_facts)

        # Calculate stats
        valid_count = sum(1 for r in results if r.is_valid)
        recovered_count = sum(1 for r in results if r.is_valid and r.was_recovered)
        recovered_near_match_count = sum(1 for r in results if r.is_valid and r.was_recovered and r.is_near_match)
        near_match_failed_count = sum(1 for r in results if not r.is_valid and r.is_near_match)
        invalid_count = len(results) - valid_count

        stats = {
            "total_facts": len(results),
            "valid_facts": valid_count,
            "recovered_facts": recovered_count,
            "recovered_near_matches": recovered_near_match_count,
            "near_match_failed": near_match_failed_count,
            "invalid_facts": invalid_count,
            "validation_rate": valid_count / len(results) if results else 0,
            "recovery_rate": recovered_count / len(results) if results else 0,
            "near_match_recovery_rate": recovered_near_match_count / (recovered_near_match_count + near_match_failed_count) if (recovered_near_match_count + near_match_failed_count) > 0 else 0,
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
    recovered_count = sum(1 for r in results if r.is_valid and r.was_recovered)
    recovered_near_match_count = sum(1 for r in results if r.is_valid and r.was_recovered and r.is_near_match)
    near_match_failed_count = sum(1 for r in results if not r.is_valid and r.is_near_match)
    invalid_count = len(results) - valid_count

    stats = {
        "total_facts": len(results),
        "valid_facts": valid_count,
        "recovered_facts": recovered_count,
        "recovered_near_matches": recovered_near_match_count,
        "near_match_failed": near_match_failed_count,
        "invalid_facts": invalid_count,
        "validation_rate": valid_count / len(results) if results else 0,
        "recovery_rate": recovered_count / len(results) if results else 0,
        "near_match_recovery_rate": recovered_near_match_count / (recovered_near_match_count + near_match_failed_count) if (recovered_near_match_count + near_match_failed_count) > 0 else 0,
    }

    return results, stats
