# Enhanced Fact Extraction - High-Specificity System

**Status**: ✅ Implemented

## Overview

This document describes the major enhancements made to address extraction quality issues identified by judge LLM evaluation. The goal: shift from "control awareness" to "control specificity" by capturing technical details, quantitative values, and contextual information that make facts actionable.

---

## Problems Addressed

### Critical Issues from Judge Evaluation

1. **Overly Generic Claims**: Facts lacked actionable specificity
   - ❌ "LNRS engineers use several monitoring tools"
   - ✅ "LNRS uses Splunk Enterprise for log aggregation and Datadog for infrastructure monitoring with alerts sent when CPU exceeds 80%"

2. **Missing Context Connections**: Facts extracted in isolation without relationships

3. **Structural Information Lost**:
   - WHO performs control ❌ (rarely captured)
   - WHEN/HOW OFTEN ⚠️ (inconsistently captured)
   - WHAT TOOLS/SYSTEMS 🔴 (almost never captured)
   - Metrics and thresholds 🔴 (never captured)

4. **Table Structure Ignored**: SOC2 3-column format conflated different fact types

5. **CUECs Not Extracted**: Complementary User Entity Controls completely missed

6. **Test Procedures Underrepresented**: Only 15% coverage of test methodology

---

## Solution Architecture

### 1. Enhanced Fact Schema

**File**: `frfr/extraction/schemas.py:7-67`

Added rich metadata fields to `ExtractedFact`:

```python
class ExtractedFact(BaseModel):
    # Core fields (unchanged)
    claim: str
    source_doc: str
    source_location: str
    evidence_quote: str
    confidence: float

    # NEW: Enhanced metadata
    fact_type: Optional[str]  # technical_control, organizational, process, metric, CUEC, test_result
    control_family: Optional[str]  # access_control, encryption, monitoring, etc.
    specificity_score: Optional[float]  # 0.0=generic, 1.0=highly specific
    entities: Optional[List[str]]  # Named entities: AWS, TLS 1.2, NIST, Splunk
    quantitative_values: Optional[List[str]]  # 90 days, 256-bit, 99.9%
    process_details: Optional[dict]  # {who: role, when: frequency, how: procedure}
    section_context: Optional[str]  # System Description, Control Testing, CUEC
    related_control_ids: Optional[List[str]]  # CC6.1, A.1.2
```

**Benefits**:
- Enables filtering by fact type (show me all CUECs)
- Quantifies specificity (identify generic claims for review)
- Captures WHO/WHEN/HOW structure
- Links related facts via control IDs

---

### 2. Enhanced Document Summarization

**File**: `frfr/extraction/fact_extractor.py:45-130`

Expanded from 8 to 10 analysis fields:

**New Fields**:
- `section_types`: Categorized section types with extraction priorities
  ```json
  {
    "section_type": "Control Testing",
    "characteristics": "technical implementation + test evidence",
    "extraction_priority": "high"
  }
  ```
- `table_structure`: Detects and describes table formats
  ```json
  {
    "column_structure": "3-column: Control | Test Performed | Results",
    "extraction_guidance": "Extract facts from each column separately"
  }
  ```

**Enhanced Extraction Guidance**:
- Emphasizes capturing WHO/WHEN/HOW details
- Requires quantitative values extraction
- Demands technical specifications (protocols, algorithms, versions)

---

### 3. Section-Aware Extraction

**File**: `frfr/extraction/fact_extractor.py:260-450`

#### Section Detection
Automatically detects chunk context:
- System Description → organizational/architectural facts
- Control Testing → technical implementations + test evidence
- CUEC → customer responsibilities
- Privacy/Confidentiality → data handling specifics

#### Adaptive Prompting
Different extraction strategies per section type:

```python
if "control testing" in section_context.lower():
    "Focus on: control implementations, test procedures, test results, technologies used"
elif "cuec" in section_context.lower():
    "Focus on: customer responsibilities, required controls, user entity requirements"
```

#### Table Structure Recognition
When tables detected:
```
When extracting from tables:
- Extract facts from EACH column separately
- Do NOT conflate "Control Statement" with "Test Performed" with "Results"
- Each column represents a different fact type
```

---

### 4. Named Entity Recognition & Quantitative Extraction

**File**: `frfr/extraction/fact_extractor.py:374-420`

Enhanced prompts explicitly request:

**Named Entities**:
- Technology brands/products: AWS, Splunk, Okta, Palo Alto
- Software versions: PostgreSQL 13.7, TLS 1.3
- Protocols/algorithms: AES-256, SHA-256, bcrypt
- Standards/frameworks: NIST SP 800-53, ISO 27001, OWASP Top 10

**Quantitative Values**:
- Numbers with units: 90 days, 256-bit, 8 characters
- Percentages: 99.9%, 5% variance
- Frequencies: daily, weekly, monthly, quarterly
- Thresholds: > 80°F, < 3 attempts, at least 12 characters
- Metrics: RTO of 4 hours, 99.95% uptime SLA

**Process Details**:
```json
{
  "who": "IT Security team",
  "when": "quarterly",
  "how": "automated vulnerability scanner with manual review"
}
```

---

### 5. Specificity Scoring

**File**: `frfr/extraction/fact_extractor.py:399-404`

Facts now include a specificity score (0.0-1.0):

**Examples**:
- 0.2: "Temperature and humidity levels are monitored"
- 0.5: "Temperature monitored with alerts triggered on variance"
- 0.9: "Data center temperature maintained at 68°F with alerts triggered at ±5°F variance"

**Usage**: Filter out low-specificity facts (< 0.5) or prioritize high-specificity for review.

---

### 6. Multi-Pass Extraction Strategy

**File**: `frfr/extraction/fact_extractor.py:491-630`

Optional multi-pass mode for deep extraction:

#### Pass 1: General Extraction
Standard comprehensive extraction (current default)

#### Pass 2: CUEC Extraction
Focused on:
- Customer/user entity responsibilities
- Controls customers must implement
- Actions the customer must take
- Look for: "user entity", "customer responsibility", "complementary controls"

#### Pass 3: Test Procedures
Focused on:
- What tests were performed
- How tests were conducted
- Test results and outcomes
- Sample sizes and populations

#### Pass 4: Quantitative Extraction
Focused on:
- All numbers with units
- Percentages and frequencies
- Thresholds and limits
- Performance metrics

#### Pass 5: Technical Specifications
Focused on:
- Technology brands/products
- Software versions
- Protocols and algorithms
- Standards and frameworks
- Configurations

**Enable**: `--multipass` flag in CLI

---

## Usage

### Maximum Depth Extraction (Default)

The system now operates in **aggressive extraction mode by default**, designed to exceed human analysis capabilities.

```bash
python frfr/cli.py extract-facts output/soc2_full_extraction.txt \
  --document-name my_soc2_report \
  --chunk-size 500 \
  --overlap 100 \
  --max-workers 11
```

**Result**: Maximum depth extraction with:
- Every technical detail extracted as separate facts
- Every quantitative value captured
- Every process step documented with WHO/WHEN/HOW
- Every tool, technology, protocol, and standard identified
- Enhanced metadata (entities, quantitative_values, process_details, specificity_score)

**Philosophy**: "If a paragraph describes a control, extract 5-10 distinct facts from it"

### Multi-Pass Extraction (Maximum Depth)

```bash
python frfr/cli.py extract-facts output/soc2_full_extraction.txt \
  --document-name my_soc2_report \
  --chunk-size 500 \
  --overlap 100 \
  --max-workers 11 \
  --multipass
```

**Result**: Additional specialized passes extract CUECs, test procedures, quantitative data, and technical specs that might be missed in general pass.

---

## Expected Improvements

### Coverage Improvements

Based on judge evaluation baseline:

| Category                           | Before | After (Target) | Improvement |
|------------------------------------|--------|----------------|-------------|
| High-level control existence       | 80-85% | 90%+           | +10%        |
| Technical implementation specifics | 20-30% | 70-80%         | +50%        |
| Tool/technology names              | 5%     | 60-70%         | +60%        |
| Metrics/thresholds/SLAs            | <5%    | 50-60%         | +55%        |
| CUECs                              | 0%     | 80-90%         | +90%        |
| Test procedures                    | 15%    | 60-70%         | +50%        |
| Process details (who/when/how)     | 30-40% | 70-80%         | +40%        |

### Fact Count Improvements

**Before** (generic extraction): ~275 facts
**After** (enhanced + multipass): **500-800+ facts** (estimated)

### Specificity Improvements

**Before**:
- Average specificity: ~0.4 (generic)
- Few facts mention specific tools/versions

**After**:
- Average specificity: ~0.7 (specific)
- Most facts include named entities and quantitative values

---

## Quality Validation

### Specificity Score Distribution

After extraction, analyze specificity:

```python
import json

with open("output/consolidated_facts.json") as f:
    data = json.load(f)

for doc_name, doc_data in data["documents"].items():
    facts = doc_data["facts"]

    scores = [f.get("specificity_score", 0) for f in facts]
    avg_specificity = sum(scores) / len(scores)

    print(f"Document: {doc_name}")
    print(f"  Average specificity: {avg_specificity:.2f}")
    print(f"  High specificity (>0.7): {sum(1 for s in scores if s > 0.7)}")
    print(f"  Low specificity (<0.4): {sum(1 for s in scores if s < 0.4)}")
```

### Named Entity Coverage

Check extraction of technical terms:

```python
all_entities = []
for fact in facts:
    all_entities.extend(fact.get("entities", []))

unique_entities = set(all_entities)
print(f"Unique entities extracted: {len(unique_entities)}")
print(f"Examples: {list(unique_entities)[:10]}")
```

### Process Details Coverage

Check WHO/WHEN/HOW extraction:

```python
facts_with_process = [f for f in facts if f.get("process_details")]
print(f"Facts with process details: {len(facts_with_process)}/{len(facts)}")

for fact in facts_with_process[:5]:
    print(f"  {fact['claim'][:60]}...")
    print(f"    WHO: {fact['process_details'].get('who')}")
    print(f"    WHEN: {fact['process_details'].get('when')}")
    print(f"    HOW: {fact['process_details'].get('how')}")
```

---

## Troubleshooting

### Low Specificity Scores

**Problem**: Most facts have specificity < 0.5

**Solutions**:
1. Check if document actually contains specific details
2. Review extraction_guidance in summary - may need manual tuning
3. Try --multipass for deeper extraction
4. Increase max_tokens in extraction prompt (currently 4000)

### Missing Named Entities

**Problem**: `entities` field mostly empty

**Solutions**:
1. Check if document uses brand names or generic terms
2. Review chunk text - entities may be in different sections
3. Use --multipass with technical_specs pass
4. Add custom entity patterns to prompt

### CUECs Not Extracted (Even with Multipass)

**Problem**: No facts with fact_type="CUEC"

**Solutions**:
1. Confirm document has CUEC section (search for "user entity")
2. Check section_types in summary - CUEC section detected?
3. Manually review CUEC section line ranges
4. May need to extract CUEC section separately with targeted prompt

### Process Details Incomplete

**Problem**: process_details missing "who", "when", or "how"

**Solutions**:
1. Some facts don't have all three - that's expected
2. Check if source text provides these details
3. May be implicit (e.g., "automatically" → no "who")
4. Review evidence_quote to see what's available

---

## Performance Considerations

### Multi-Pass Overhead

- Each specialized pass adds ~30% extraction time
- 4 specialized passes = ~2-3x total time
- Recommended for final production runs, not development

### Token Usage

- Enhanced prompts use more tokens (~6k vs 4k per chunk)
- Responses with metadata use more tokens (~2k vs 1k)
- Budget: ~8k tokens per chunk (up from ~5k)

### Parallel Workers

- More metadata = more memory per worker
- Reduce max_workers if OOM errors occur
- Recommended: 8-11 workers on 16GB RAM, 5 workers on 8GB RAM

---

## Examples

### Generic Fact (Old System)

```json
{
  "claim": "LNRS uses monitoring tools",
  "confidence": 0.7,
  "evidence_quote": "LNRS engineers use several monitoring tools..."
}
```

### Specific Fact (Enhanced System)

```json
{
  "claim": "LNRS uses Splunk Enterprise for log aggregation with real-time alerting when error rates exceed 5%",
  "confidence": 0.95,
  "evidence_quote": "LNRS has implemented Splunk Enterprise 9.0 for centralized log aggregation across all production systems. Real-time alerts are configured to trigger when error rates exceed 5% threshold...",
  "fact_type": "technical_control",
  "control_family": "monitoring",
  "specificity_score": 0.92,
  "entities": ["Splunk Enterprise", "Splunk Enterprise 9.0"],
  "quantitative_values": ["5%", "real-time"],
  "process_details": {
    "who": "IT Operations team",
    "when": "real-time",
    "how": "automated alerting with threshold-based triggers"
  },
  "section_context": "Control Testing",
  "related_control_ids": ["CC7.2"]
}
```

---

## Related Documentation

- `STATUS.md` - Project status
- `STRUCTURAL_EXTRACTION.md` - Structure-aware extraction approach
- `PARALLEL_AND_RECOVERY.md` - Parallel processing and fact recovery
- `DESIGN.md` - System architecture

---

## Future Enhancements

1. **Machine Learning Entity Extraction**: Use NER models for entity detection
2. **Relationship Graphs**: Build knowledge graph of related facts
3. **Automated Specificity Improvement**: Post-process to enrich generic facts
4. **Template Library**: Pre-defined extraction patterns for common doc types
5. **Confidence Calibration**: Adjust confidence based on specificity score
6. **Semantic Deduplication**: Merge semantically similar facts
7. **Fact Validation Rules**: Domain-specific validation (e.g., valid ports, protocols)

---

## Conclusion

The enhanced extraction system shifts from "awareness" to "specificity" by:

1. ✅ Capturing named entities (tools, protocols, standards)
2. ✅ Extracting quantitative values (metrics, thresholds, frequencies)
3. ✅ Recording process details (WHO/WHEN/HOW)
4. ✅ Scoring specificity to identify generic claims
5. ✅ Using section context for adaptive extraction
6. ✅ Recognizing table structures
7. ✅ Supporting multi-pass extraction for deep coverage
8. ✅ Extracting CUECs and test procedures

**Result**: Actionable, detailed facts suitable for technical due diligence, compliance validation, and security assessment.
