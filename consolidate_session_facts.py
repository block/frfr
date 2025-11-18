#!/usr/bin/env python3
"""
Helper script to consolidate facts from chunk files into the main facts file.
This is useful if processing completed but facts weren't consolidated properly.
"""

import sys
import json
from pathlib import Path

# Add frfr to path
sys.path.insert(0, str(Path(__file__).parent))

from frfr.session import Session


def consolidate_session_facts(session_id: str) -> None:
    """Consolidate facts for a specific session."""
    session = Session(session_id=session_id)

    print(f"Processing session: {session_id}")
    print(f"Session directory: {session.session_dir}")
    print()

    documents = session.get_documents()
    if not documents:
        print("No documents found in session.")
        return

    total_consolidated = 0
    for document_name, doc_info in documents.items():
        print(f"Document: {document_name}")

        # Load facts from chunks
        facts_list = session.load_all_facts(document_name)
        chunks = session.get_processed_chunks(document_name)

        print(f"  Found {len(chunks)} chunk files")
        print(f"  Loaded {len(facts_list)} facts")

        if len(facts_list) == 0:
            print(f"  ⚠️  No facts found in chunk files")
            continue

        # Load summary
        summary = session.load_summary(document_name)

        # Get the facts file path from metadata
        facts_file = Path(doc_info['facts_file'])
        text_file = Path(doc_info.get('text_file', ''))

        # Create consolidated facts file
        consolidated = {
            "session_id": session.session_id,
            "documents": {
                document_name: {
                    "summary": summary,
                    "facts": facts_list,
                    "fact_count": len(facts_list),
                    "source_text_file": str(text_file),
                }
            },
            "total_facts": len(facts_list),
        }

        # Write the consolidated facts file
        facts_file.parent.mkdir(parents=True, exist_ok=True)
        with open(facts_file, "w") as f:
            json.dump(consolidated, f, indent=2)

        print(f"  ✓ Consolidated facts written to: {facts_file}")
        total_consolidated += len(facts_list)
        print()

    print(f"✅ Done! Consolidated {total_consolidated} facts total.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 consolidate_session_facts.py <session_id>")
        print()
        print("Example:")
        print("  python3 consolidate_session_facts.py sess_dataset_ownership_declaration_20251118_091213")
        sys.exit(1)

    session_id = sys.argv[1]
    consolidate_session_facts(session_id)
