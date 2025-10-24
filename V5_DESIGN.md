# V5 Design: Multiple Evidence Quotes Per Fact

## Motivation

Current limitation: Facts can only have one `evidence_quote`, but many facts are supported by evidence from multiple locations in the document.

**Examples where multiple quotes help:**
1. **Distributed information**: "Backups are performed daily and retained for 90 days" might be mentioned across different sections
2. **Corroborating evidence**: Multiple test results confirming the same control
3. **Policy + implementation**: Policy statement in one section, implementation details in another
4. **Triangulation**: Multiple mentions increase confidence and provide richer context

## Schema Changes

### New `EvidenceQuote` Class

```python
class EvidenceQuote(BaseModel):
    """A single piece of evidence supporting a fact."""

    quote: str = Field(
        ...,
        description="Exact text from document (must match exactly)"
    )
    source_location: str = Field(
        ...,
        description="Location of this quote (e.g., 'Lines 42-45', 'Page 3, Section 2.1')"
    )
    relevance: Optional[str] = Field(
        None,
        description="Why this quote supports the claim (optional context)"
    )
```

### Updated `ExtractedFact` Schema

**Option A: Replace `evidence_quote` with `evidence_quotes`** (breaking change)
```python
evidence_quotes: List[EvidenceQuote] = Field(
    ...,
    description="Evidence supporting this fact (can have multiple quotes)"
)
```

**Option B: Keep both for backward compatibility** (recommended)
```python
evidence_quote: Optional[str] = Field(
    None,
    description="DEPRECATED: Use evidence_quotes instead"
)
evidence_quotes: Optional[List[EvidenceQuote]] = Field(
    None,
    description="Evidence supporting this fact (recommended)"
)
```

**Recommendation:** Use Option B to maintain compatibility with V4 data. Add validation logic to ensure at least one is present.

### Validation Logic

```python
@validator('evidence_quotes', always=True)
def validate_evidence(cls, v, values):
    """Ensure at least one evidence source is provided."""
    legacy_quote = values.get('evidence_quote')

    # If new format provided, use it
    if v and len(v) > 0:
        return v

    # If legacy format provided, convert to new format
    if legacy_quote:
        source_location = values.get('source_location', 'Unknown')
        return [EvidenceQuote(
            quote=legacy_quote,
            source_location=source_location,
            relevance=None
        )]

    # Neither provided - error
    raise ValueError("Must provide either evidence_quote or evidence_quotes")
```

## Prompt Changes

### Current Prompt Format (V4)
```json
{
  "claim": "Backups performed daily",
  "evidence_quote": "Backups are performed on a daily basis",
  "source_location": "Lines 42-45"
}
```

### New Prompt Format (V5)
```json
{
  "claim": "Backups performed daily and retained for 90 days",
  "evidence_quotes": [
    {
      "quote": "Backups are performed on a daily basis",
      "source_location": "Lines 42-45",
      "relevance": "Supports daily frequency"
    },
    {
      "quote": "Backup data is retained for a period of 90 days",
      "source_location": "Lines 123-125",
      "relevance": "Supports retention period"
    }
  ]
}
```

### Prompt Instructions

Add to extraction prompt:
```
EVIDENCE REQUIREMENTS:

For each fact, provide evidence_quotes (an array of evidence):
- **Single evidence**: Most facts have one supporting quote
- **Multiple evidence**: If a fact combines information from multiple locations,
  provide ALL relevant quotes

Example with single evidence:
{
  "claim": "LNRS uses AES-256 encryption",
  "evidence_quotes": [
    {
      "quote": "Data is encrypted using AES-256-GCM encryption",
      "source_location": "Lines 88-90"
    }
  ]
}

Example with multiple evidence:
{
  "claim": "Vulnerability scans performed quarterly by third-party vendor Acme Security",
  "evidence_quotes": [
    {
      "quote": "Vulnerability assessments are conducted quarterly",
      "source_location": "Lines 42-43",
      "relevance": "Frequency"
    },
    {
      "quote": "Third-party vendor Acme Security performs the vulnerability scans",
      "source_location": "Lines 128-130",
      "relevance": "Who performs"
    }
  ]
}

IMPORTANT:
- Each quote must be EXACT text from the chunk
- Provide multiple quotes when a fact synthesizes information from different locations
- Single quote is fine if all evidence is in one place
```

## Validation Changes

### Current Validation (V4)
```python
def validate_fact(fact, chunk_text):
    quote = fact['evidence_quote']
    if quote not in chunk_text:
        return False
    return True
```

### New Validation (V5)
```python
def validate_fact(fact, chunk_text):
    evidence_quotes = fact.get('evidence_quotes', [])

    # Must have at least one quote
    if not evidence_quotes:
        return False

    # Validate each quote
    for evidence in evidence_quotes:
        quote = evidence['quote']
        if quote not in chunk_text:
            # Try fuzzy matching with 80% threshold
            match_score = fuzzy_match(quote, chunk_text)
            if match_score < 0.8:
                return False

    return True
```

## Migration Strategy

### Phase 1: Schema Update (Non-breaking)
1. Add `EvidenceQuote` class
2. Add `evidence_quotes` field (Optional)
3. Keep `evidence_quote` field (Optional)
4. Add validator to ensure at least one is present
5. Add converter utility to upgrade old format to new

### Phase 2: Prompt Update
1. Update extraction prompts to show `evidence_quotes` format
2. Keep accepting both formats (LLM may still use old format)
3. Post-processing converts old format to new

### Phase 3: Validation Update
1. Update validator to handle both formats
2. Try validating each quote individually
3. Add fuzzy matching for quotes that don't match exactly

### Phase 4: Full Adoption (Optional)
1. Run converter on all existing V4 data
2. Update all code to use new format
3. Deprecate `evidence_quote` field entirely

## Benefits

1. **Richer evidence**: Capture all supporting quotes, not just one
2. **Higher confidence**: Multiple quotes = stronger evidence
3. **Better traceability**: Know exactly where each piece of information came from
4. **Synthesis support**: Facts that combine information have proper citations
5. **Quality metric**: Number of evidence quotes can indicate fact quality

## Implementation Files

1. **Schema**: `frfr/extraction/schemas.py`
   - Add `EvidenceQuote` class
   - Update `ExtractedFact` class
   - Add validation logic

2. **Prompts**: `frfr/extraction/fact_extractor.py`
   - Update extraction prompt (lines ~630-650)
   - Add examples of multiple evidence quotes

3. **Validation**: `frfr/validation/fact_validator.py`
   - Update to validate each quote
   - Add handling for both formats

4. **Migration**: `frfr/migration/v4_to_v5.py` (new file)
   - Converter from V4 format to V5 format
   - CLI tool to upgrade existing files

## Testing Plan

1. **Unit tests**: Test schema validation with:
   - Single quote (old format)
   - Single quote (new format)
   - Multiple quotes
   - Missing quotes (should fail)

2. **Integration tests**: Extract facts from sample document:
   - Verify LLM can provide multiple quotes
   - Verify validation works with multiple quotes
   - Verify old format still works

3. **Migration tests**: Convert V4 data to V5:
   - Load V4.7_FIXED_facts.json
   - Convert to V5 format
   - Verify all facts have evidence_quotes array

## Rollout

1. ✅ Design (this document)
2. ✅ Implement schema changes (frfr/extraction/schemas.py)
3. ✅ Implement prompt changes (frfr/extraction/fact_extractor.py)
4. ✅ Implement validation changes (frfr/validation/fact_validator.py)
5. ✅ Test with sample extraction (test_v5_validation.py, V5 extraction test)
6. ⏳ Run full V5 extraction (optional - infrastructure ready)
7. ⏳ Compare V5 vs V4 results (optional - when full extraction runs)
8. ⏳ Document improvements (optional - after production use)
