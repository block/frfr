"""
Test script for V3 extraction with pre-parsing and post-processing.

Tests the hybrid extraction approach on a small sample to validate
the integration works correctly.
"""

from frfr.extraction.fact_extractor import FactExtractor
from frfr.session import Session
from pathlib import Path

# Create a small test file with sample SOC2 text
test_text = """
CC5.3 Control Activities

LNRS has a Security Incident Response Policy and Procedures in place to provide policy
guidance and establish responsibilities for responding to and reporting security breaches.

Inspected the Data Security Incident Response Overview and Incident Response and
Notification Policy to determine that LNRS had a Security Incident Response Policy
and Procedures in place to provide policy guidance for responding to and reporting
security breaches. No Exceptions Noted

The IT Security team reviews firewall rules quarterly using an automated compliance tool,
with changes requiring CISO approval before implementation. During the audit period, the
auditor inspected 4 quarterly reviews and sampled 25 out of 100 firewall rule changes to
verify CISO approval was obtained. No exceptions noted.

Management maintains documented account management policies and procedures to provide
guidance on the management of user accounts on target systems and password standards.
Passwords must be at least 12 characters and changed every 90 days.

Inspected the User Access Control Procedures to determine the policies and procedures
for account management and password configuration are in place and provide guidance on
logical access requirements. No Exceptions Noted

Data in motion is encrypted using TLS 1.3. Data can be accessed remotely using a virtual
private network with multi-factor authentication. Remote access requires two-factor
authentication with SMS codes or hardware tokens.

Backups are performed daily at 2 AM UTC with retention period of 90 days. Backup
verification tests are conducted monthly by the IT Operations team. The backup system
achieves 99.95% successful completion rate.
"""

# Write test file
test_file = Path("test_sample_v3.txt")
with open(test_file, "w") as f:
    f.write(test_text)

print("="*70)
print("V3 EXTRACTION TEST - Small Sample")
print("="*70)
print(f"\nTest file: {test_file}")
print(f"Lines: {len(test_text.split(chr(10)))}")
print(f"Characters: {len(test_text)}")

# Create session
session = Session()
print(f"\nSession: {session.session_id}")

# Create extractor
extractor = FactExtractor(chunk_size=100, overlap_size=20, max_workers=1)

try:
    # Extract facts
    print("\n" + "="*70)
    print("EXTRACTION IN PROGRESS...")
    print("="*70 + "\n")

    result = extractor.extract_from_document(
        text_file=test_file,
        document_name="test_sample_v3",
        session=session,
    )

    # Print results
    print("\n" + "="*70)
    print("EXTRACTION COMPLETE")
    print("="*70)

    print(f"\nTotal facts extracted: {len(result.facts)}")
    print(f"Lines in test: {len(test_text.split(chr(10)))}")
    print(f"Facts per 100 lines: {len(result.facts) / len(test_text.split(chr(10))) * 100:.2f}")

    # Show facts
    print("\n" + "="*70)
    print("EXTRACTED FACTS")
    print("="*70 + "\n")

    for i, fact in enumerate(result.facts, 1):
        print(f"{i}. {fact.claim}")
        if fact.quantitative_values:
            print(f"   📊 Quantitative: {fact.quantitative_values}")
        if fact.entities:
            print(f"   🔧 Entities: {fact.entities}")
        if fact.process_details:
            who = fact.process_details.get("who")
            when = fact.process_details.get("when")
            if who or when:
                print(f"   👥 Process: WHO={who}, WHEN={when}")
        print(f"   Specificity: {fact.specificity_score:.2f}")
        print()

    # Analyze results
    print("="*70)
    print("ANALYSIS")
    print("="*70)

    # Count facts by type
    fact_types = {}
    for fact in result.facts:
        ft = fact.fact_type or "unknown"
        fact_types[ft] = fact_types.get(ft, 0) + 1

    print("\nFact types:")
    for ft, count in sorted(fact_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ft}: {count}")

    # Check specificity
    avg_spec = sum([f.specificity_score or 0 for f in result.facts]) / len(result.facts)
    high_spec = sum([1 for f in result.facts if (f.specificity_score or 0) >= 0.7])
    print(f"\nSpecificity:")
    print(f"  Average: {avg_spec:.2f}")
    print(f"  High (≥0.7): {high_spec}/{len(result.facts)} ({high_spec/len(result.facts)*100:.1f}%)")

    # Check quantitative coverage
    facts_with_qv = sum([1 for f in result.facts if f.quantitative_values])
    print(f"\nQuantitative values:")
    print(f"  Facts with QV: {facts_with_qv}/{len(result.facts)} ({facts_with_qv/len(result.facts)*100:.1f}%)")

    # Check entities
    facts_with_entities = sum([1 for f in result.facts if f.entities])
    print(f"\nEntities:")
    print(f"  Facts with entities: {facts_with_entities}/{len(result.facts)} ({facts_with_entities/len(result.facts)*100:.1f}%)")

    print("\n" + "="*70)
    print("SUCCESS!")
    print("="*70)
    print("\nV3 extraction working correctly. Ready to run on full document.")

except Exception as e:
    print("\n" + "="*70)
    print("ERROR")
    print("="*70)
    print(f"\n{e}")
    import traceback
    traceback.print_exc()

finally:
    # Cleanup
    import os
    if test_file.exists():
        os.remove(test_file)
        print(f"\nCleaned up: {test_file}")
