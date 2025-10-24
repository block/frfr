# Parallel Processing & Fact Recovery Features

**Status**: ✅ Implemented

## Overview

Two major enhancements have been added to improve extraction speed and fact recovery:

1. **Parallel Chunk Processing** - Process multiple chunks simultaneously
2. **Medium-Confidence Fact Recovery** - LLM-assisted recovery of facts with partial validation

---

## 1. Parallel Chunk Processing

### What It Does

Processes multiple document chunks in parallel using a thread pool, significantly reducing total extraction time.

### Key Features

- **Configurable Workers**: Control max parallel processes (default: 5)
- **Thread Pool**: Uses `ThreadPoolExecutor` for safe concurrent execution
- **Progress Tracking**: Real-time progress bar showing completed chunks
- **Ordered Results**: Facts are combined in chunk order regardless of completion order

### Usage

```bash
python frfr/cli.py extract-facts <text_file> \
  --document-name <doc_name> \
  --max-workers 5  # Default: 5, adjust based on system resources
```

**Examples**:

```bash
# Use default (5 parallel workers)
python frfr/cli.py extract-facts output/soc2_full_extraction.txt \
  --document-name my_doc

# Increase to 10 workers for faster processing (requires more resources)
python frfr/cli.py extract-facts output/soc2_full_extraction.txt \
  --document-name my_doc \
  --max-workers 10

# Reduce to 2 workers for resource-constrained environments
python frfr/cli.py extract-facts output/soc2_full_extraction.txt \
  --document-name my_doc \
  --max-workers 2
```

### Performance

**Sequential Processing** (max-workers=1):
- 9 chunks × ~2 min/chunk = ~18 minutes

**Parallel Processing** (max-workers=5):
- 9 chunks ÷ 5 workers ≈ 2 batches
- ~2 min × 2 batches = **~4-5 minutes** (3-4x speedup)

### Implementation

**File**: `frfr/extraction/fact_extractor.py`

```python
# Thread pool executor processes chunks concurrently
with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
    future_to_chunk = {}
    for chunk_info in chunks_to_process:
        future = executor.submit(
            self._process_single_chunk,
            chunk_info, document_name, summary, session, validator, len(all_facts)
        )
        future_to_chunk[future] = chunk_info[0]

    # Collect results as they complete
    for future in as_completed(future_to_chunk):
        chunk_id, validated_facts, stats = future.result()
        chunk_results[chunk_id] = (validated_facts, stats)
```

---

## 2. Medium-Confidence Fact Recovery

### What It Does

When a fact has a 40-79% validation match (medium confidence), the system attempts to recover it by:
1. Using LLM to search for the correct evidence quote
2. Verifying the recovered quote exists in the source
3. Updating the fact with corrected evidence

This **saves facts that would otherwise be rejected**, improving overall extraction yield.

### Key Features

- **Smart Threshold**: Only attempts recovery for 40-79% matches
- **LLM Search**: Uses Claude to find exact supporting quotes
- **Verification**: Validates recovered quotes against source text
- **Fact Update**: Automatically updates evidence_quote and source_location
- **Tracking**: Marks recovered facts and includes in stats

### How It Works

#### 1. Normal Validation Flow

```
Extract Fact → Validate Quote → Quote Found (>80% match) → ✓ Accept
                               → Quote Not Found (<40% match) → ✗ Reject
```

#### 2. Enhanced Flow with Recovery

```
Extract Fact → Validate Quote → Quote Found (>80% match) → ✓ Accept
                               → Medium Match (40-79%) → Attempt Recovery
                                   → Recovery Succeeds → ✓ Accept (with updated quote)
                                   → Recovery Fails → ✗ Reject
                               → Quote Not Found (<40% match) → ✗ Reject
```

### Example Recovery

**Original Fact** (60% match):
```json
{
  "claim": "Remote user VPN connections utilize multi-factor authentication",
  "evidence_quote": "VPN connections require MFA for access",
  "source_location": "Lines 100-102"
}
```

**Recovery Process**:
1. LLM searches lines 80-122 (expanded context)
2. Finds exact quote: "Remote users connecting via VPN must authenticate using multi-factor authentication methods"
3. Verifies quote exists at lines 98-100

**Recovered Fact**:
```json
{
  "claim": "Remote user VPN connections utilize multi-factor authentication",
  "evidence_quote": "Remote users connecting via VPN must authenticate using multi-factor authentication methods",
  "source_location": "Lines 80-122"
}
```

### Configuration

Recovery is **enabled by default** when Claude client is available. No additional configuration needed.

To disable recovery (not recommended):
```python
# In fact_extractor.py, pass claude_client=None
validator = FactValidator(text_file, claude_client=None)
```

### Implementation

**File**: `frfr/validation/fact_validator.py`

```python
def attempt_fact_recovery(
    self, claim: str, original_quote: str, search_context: str,
    start_line: int, end_line: int
) -> Optional[Tuple[str, str]]:
    """Use LLM to find correct quote for medium-confidence facts."""

    prompt = f"""Find the exact quote supporting this claim:
    Claim: {claim}
    Original Quote: {original_quote}
    Context: {search_context}
    """

    response = self.claude_client.prompt(prompt)
    result = json.loads(response)

    if result["found"] and result["confidence"] >= 0.8:
        recovered_quote = result["quote"]
        # Verify quote exists in context
        if self.find_quote_in_text(recovered_quote, search_context):
            return recovered_quote, f"Lines {start_line}-{end_line}"

    return None
```

### Statistics

Recovery stats are included in extraction output:

```bash
Chunk 5 complete: 50 extracted, 35 validated (7 recovered), 15 rejected
```

- **35 validated**: Total facts passing validation
- **7 recovered**: Facts that were medium-confidence and recovered
- **15 rejected**: Facts that failed validation and recovery

---

## Combined Benefits

### Before (Sequential + No Recovery)
- **Time**: ~18 minutes for 9 chunks
- **Facts**: 91 validated (many medium-confidence facts rejected)

### After (Parallel + Recovery)
- **Time**: ~4-5 minutes for 9 chunks
- **Facts**: 91+ validated (recovered medium-confidence facts included)
- **Speedup**: 3-4x faster
- **Quality**: Higher fact yield with verified evidence

---

## Files Modified

### Core Implementation
- `frfr/extraction/fact_extractor.py`
  - Added `max_workers` parameter
  - Implemented parallel chunk processing with ThreadPoolExecutor
  - Integrated fact recovery in validation flow

- `frfr/validation/fact_validator.py`
  - Added `claude_client` parameter for recovery
  - Implemented `attempt_fact_recovery()` method
  - Enhanced `ValidationResult` with recovery tracking
  - Updated `validate_fact()` to attempt recovery for medium-confidence facts

### CLI
- `frfr/cli.py`
  - Added `--max-workers` parameter (default: 5)
  - Enhanced progress reporting with real-time bar
  - Pass extractor max_workers setting

---

## Best Practices

### Parallel Processing

1. **Start with default (5 workers)** - Good balance of speed and resources
2. **Increase for powerful machines** - Up to 10 workers if you have:
   - 16+ GB RAM
   - Fast SSD
   - High API rate limits

3. **Decrease for constraints** - Use 2-3 workers if:
   - Limited RAM (< 8GB)
   - API rate limits
   - Shared system resources

### Fact Recovery

1. **Monitor recovery rate** - Check logs for recovery success rate
2. **Review recovered facts** - Spot-check recovered facts for accuracy
3. **Trust the system** - Recovery includes verification, false positives are rare

---

## Future Enhancements

### Parallel Processing
- Dynamic worker adjustment based on system load
- Batch size optimization
- Memory usage monitoring

### Fact Recovery
- Multi-level recovery (try increasingly relaxed thresholds)
- Semantic similarity-based quote matching
- User-configurable recovery confidence threshold
- Recovery retry with different context windows

---

## Troubleshooting

### Parallel Processing Issues

**Problem**: Out of memory errors
- **Solution**: Reduce `--max-workers` to 2-3

**Problem**: API rate limit errors
- **Solution**: Reduce `--max-workers` or add delays

**Problem**: Chunk results out of order
- **Solution**: This is expected! Results are combined in correct order automatically

### Fact Recovery Issues

**Problem**: Too many facts being recovered (potential false positives)
- **Solution**: Recovery includes verification, but you can review logs for patterns

**Problem**: Recovery is too slow
- **Solution**: Recovery only runs for medium-confidence facts (40-79% match), should be minimal overhead

**Problem**: No recovery happening
- **Solution**: Check that Claude client is initialized (enabled by default)

---

## Testing

To test the new features:

```bash
# Test parallel processing with progress bar
python frfr/cli.py extract-facts output/test_doc.txt \
  --document-name test \
  --max-workers 3

# Check for recovery in logs
grep "Recovered fact" <log_output>

# Verify speedup
time python frfr/cli.py extract-facts ... --max-workers 1  # Sequential
time python frfr/cli.py extract-facts ... --max-workers 5  # Parallel
```

---

## Related Files

- `STATUS.md` - Project status and progress
- `RESUME_FEATURE.md` - Resume capability documentation
- `DESIGN.md` - System architecture
