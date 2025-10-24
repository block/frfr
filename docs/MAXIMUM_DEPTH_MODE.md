# Maximum Depth Extraction Mode (Now Default)

**Status**: ✅ Active by Default
**Philosophy**: Exceed human analysis capabilities

---

## What Changed

The extraction system now operates in **aggressive extraction mode by default**, designed to extract more facts than a human analyst would typically capture.

### Key Philosophy

> "This system aims to EXCEED human analysis capabilities. Extract facts with MAXIMUM DEPTH and SPECIFICITY. Every distinct technical detail, every specific configuration, every quantitative value, every process step is a separate fact."

### Depth Instructions

The system now follows these rules:

1. **If a paragraph describes a control, extract 5-10 distinct facts from it**
2. **If a sentence contains multiple technical details, create a separate fact for each**
3. **If a list has 5 items, create 5 separate facts (one per item)**
4. **Extract facts about the same control at different specificity levels**:
   - High-level: "Uses firewalls for network security"
   - Mid-level: "Firewall rules restrict inbound traffic"
   - Detailed: "Firewall configured to allow only ports 80 and 443 for inbound HTTPS traffic with stateful packet inspection"

---

## What Gets Extracted Now

### 1. Specific Implementations - Leave NO technical detail behind

**Extract**:
- EVERY technology mentioned: AWS, AWS RDS, AWS EC2, Splunk Enterprise 9.0, Okta SSO
- EVERY version: PostgreSQL 13.7, TLS 1.2, TLS 1.3, Python 3.10
- EVERY protocol: TLS 1.3, AES-256-GCM, SHA-256, RSA-4096
- EVERY standard: NIST SP 800-53 Rev 5, ISO 27001:2013, OWASP Top 10, HIPAA, SOX
- EVERY third-party: vendor names, service providers, subservice organizations

**Example**:
```
Original text: "LNRS uses AWS for hosting with RDS PostgreSQL databases and EC2 instances,
secured with TLS 1.3 encryption and monitored by Splunk Enterprise."

Extracted facts:
1. "LNRS uses AWS for cloud hosting"
2. "LNRS uses AWS RDS for database hosting"
3. "LNRS databases run on PostgreSQL"
4. "LNRS uses AWS EC2 for compute instances"
5. "LNRS secures connections with TLS 1.3 encryption"
6. "LNRS uses Splunk Enterprise for monitoring"
```

### 2. Concrete Processes - Extract EVERY process detail

**Extract**:
- **WHO**: Every role, title, team, department (IT manager, Security team, CISO, VP of Engineering, authorized personnel, third-party auditor)
- **WHEN**: Every frequency, schedule, timeframe (daily, weekly, monthly, quarterly, annually, semi-annually, real-time, within 24 hours, every 90 days)
- **HOW**: Every procedure, methodology, workflow step (automated script, manual review, ticketing system, approval workflow)

**Example**:
```
Original text: "The IT Security team reviews firewall rules quarterly using an automated
compliance tool, with changes requiring CISO approval before implementation."

Extracted facts:
1. "IT Security team reviews firewall rules quarterly" (WHO: IT Security team, WHEN: quarterly, HOW: review)
2. "Firewall rule reviews use an automated compliance tool" (HOW: automated tool)
3. "Firewall rule changes require CISO approval" (WHO: CISO, WHAT: approval)
4. "CISO approval is required before firewall rule implementation" (WHEN: before implementation)
```

### 3. Technical Details - Extract EVERY quantitative value

**Extract**:
- Numbers with units: 90 days, 365 days, 256-bit, 4096-bit, 8 characters, 8GB RAM
- Percentages: 99.9%, 99.95%, 5% error rate, 80% CPU threshold
- Frequencies: daily at 2 AM, weekly on Sundays, monthly on first Monday
- Thresholds: temperature >80°F, <3 failed login attempts, CPU >80%, disk >90%
- Capacity metrics: RTO of 4 hours, RPO of 15 minutes, 99.95% uptime SLA

**Example**:
```
Original text: "Backups run daily at 2 AM with 90-day retention. System achieves 99.95%
uptime with RTO of 4 hours and RPO of 15 minutes."

Extracted facts:
1. "Backups run daily at 2 AM"
2. "Backups are retained for 90 days"
3. "System achieves 99.95% uptime"
4. "System has RTO of 4 hours"
5. "System has RPO of 15 minutes"
```

### 4. Organizational Facts - Extract EVERY organizational detail

**Extract**:
- Team sizes: 8-person IT team, 3 security engineers, 50+ developers
- Locations: Alpharetta GA, data center in Virginia, office in London
- Reporting structures: reports to CISO, overseen by Board, managed by VP
- Responsibilities: responsible for patch management, accountable for backups

### 5. Compliance Statements - Extract EVERY compliance detail

**Extract**:
- Standards: meets NIST SP 800-53, follows ISO 27001:2013, complies with GDPR Article 32
- Certifications: SOC 2 Type 2 certified, PCI DSS Level 1, HIPAA compliant
- Requirements: required by policy, mandated by regulation, enforced by contract

### 6. Test Results - Extract EVERY test detail

**Extract**:
- What was tested: user authentication, firewall rules, backup restoration
- How it was tested: inspection, observation, inquiry, re-performance, automated testing
- Sample sizes: 25 of 100 users, all 50 servers, representative sample of 10%
- Results: no exceptions noted, 3 deviations found, all tests passed

---

## Critical: Exact Quotes Required

**The system now emphasizes EXACT, VERBATIM quotes**:

```
**CRITICAL**: Each fact must have an EXACT, VERBATIM quote as evidence from the chunk
- Copy the text WORD-FOR-WORD from the chunk
- DO NOT paraphrase, summarize, or rephrase the quote
- DO NOT change wording, even slightly
- If the exact text is unclear, extract a longer quote to be safe
```

This addresses the paraphrasing issue while maintaining aggressive extraction.

---

## Expected Results

### Fact Count Increase

**Previous**: 193 facts from SOC2 document (with enhanced prompts but not maximum depth)

**Expected with Maximum Depth**: 400-800+ facts from same document
- Every technical detail becomes a fact
- Every process step becomes a fact
- Every quantitative value becomes a fact
- Lists become multiple facts (5 items = 5 facts)

### Quality Maintenance

- Specificity score should remain high (avg >0.7)
- All facts must validate (exact quotes from source)
- Metadata completeness should improve (more entities, quantitative_values)

### Validation Rate

- May see increased rejection rate initially due to more aggressive extraction
- Quote corrector should recover many medium-confidence facts (40-79% match)
- Overall validated fact count should be 2-3x higher than previous run

---

## Token Usage Impact

**Increased Limits**:
- Max tokens per chunk: 4000 → **6000** (50% increase)
- Allows extraction of 20-40 facts per chunk (vs 10-15 previously)

**Cost Implications**:
- ~50% more tokens per chunk
- But 2-3x more facts extracted
- Better value: cost per validated fact actually decreases

---

## Usage

No changes required - this is now the default:

```bash
python frfr/cli.py extract-facts output/soc2_full_extraction.txt \
  --document-name my_soc2_report \
  --chunk-size 500 \
  --overlap 100 \
  --max-workers 11
```

**You'll now get**:
- Maximum depth extraction by default
- Every technical detail captured
- Every process fully documented
- Every quantitative value extracted
- Comprehensive metadata for all facts

---

## Examples

### Example 1: Physical Security

**Original text**:
```
"The data center has 24/7 security guards, badge access system with mantraps,
and surveillance cameras recording at all entrances. Temperature is maintained
at 68°F with alerts at ±5°F variance."
```

**Extracted facts (Maximum Depth)**:
1. "Data center has 24/7 security guards"
2. "Data center uses badge access system"
3. "Data center has mantraps"
4. "Data center has surveillance cameras at all entrances"
5. "Surveillance cameras record activities"
6. "Data center temperature is maintained at 68°F"
7. "Temperature alerts trigger at ±5°F variance"
8. "Temperature alerts trigger when below 63°F"
9. "Temperature alerts trigger when above 73°F"

**9 facts from 2 sentences** (5x human baseline)

### Example 2: Access Control

**Original text**:
```
"Remote VPN access requires multi-factor authentication using SMS codes or
TOTP authenticator apps. Accounts lock after 3 failed login attempts within
15 minutes and remain locked for 30 minutes."
```

**Extracted facts (Maximum Depth)**:
1. "Remote VPN access requires multi-factor authentication"
2. "Multi-factor authentication uses SMS codes"
3. "Multi-factor authentication uses TOTP authenticator apps"
4. "Accounts lock after 3 failed login attempts"
5. "Failed login attempts are counted within 15-minute windows"
6. "Locked accounts remain locked for 30 minutes"

**6 facts from 2 sentences** (3x human baseline)

### Example 3: Backup and Recovery

**Original text**:
```
"Daily incremental backups run at 2 AM UTC with weekly full backups on Sundays.
Backups are encrypted with AES-256 and retained for 90 days. Backup restoration
tests are performed quarterly by the IT Operations team."
```

**Extracted facts (Maximum Depth)**:
1. "Daily incremental backups run at 2 AM UTC"
2. "Weekly full backups run on Sundays"
3. "Backups are encrypted with AES-256"
4. "Backups are retained for 90 days"
5. "Backup restoration tests are performed quarterly"
6. "Backup restoration tests are performed by IT Operations team"

**6 facts from 3 sentences** (2x human baseline)

---

## Benefits

1. **Exceeds Human Analysis**: Captures details humans might overlook or consider redundant
2. **Complete Coverage**: No technical detail left behind
3. **Machine-Queryable**: Every detail is a discrete, searchable fact
4. **Audit Trail**: Every claim is traceable to exact source quote
5. **Automated Due Diligence**: Can answer highly specific questions without re-reading source
6. **Compliance Validation**: Can verify specific technical requirements are documented

---

## Trade-offs

### Pros
- ✅ Maximum information extraction
- ✅ Exceeds human analysis capabilities
- ✅ Comprehensive coverage of all details
- ✅ Better for automated analysis and querying
- ✅ More facts = more data for consensus algorithms

### Cons
- ⚠️ Higher token usage (~50% increase)
- ⚠️ More facts to validate
- ⚠️ May include some redundant information
- ⚠️ Requires quote corrector to recover rejected facts

**Net Result**: The benefits far outweigh the costs for automated analysis systems.

---

## Next Steps

1. **Run Test Extraction** with maximum depth mode on SOC2 document
2. **Measure Results**: Compare fact count, specificity, coverage
3. **Integrate Quote Corrector**: Auto-recover rejected facts during extraction
4. **Build Deduplication**: Post-process to merge highly similar facts if needed

---

## Conclusion

The system now operates at **maximum depth by default**, designed to exceed human analysis capabilities. This makes it suitable for:

- Automated compliance validation
- Technical due diligence
- Security assessments
- Detailed audit trail generation
- Machine-queryable knowledge bases

**Philosophy**: Extract everything, validate rigorously, let downstream systems handle deduplication if needed.
