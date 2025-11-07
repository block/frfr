# Session Management

Frfr uses intelligent, document-aware sessions to organize and track your document processing workflows.

## Overview

Sessions provide:
- **Document registry**: Track all PDFs and their processing status
- **Intelligent naming**: LLM-generated names that reflect document content
- **Automatic renaming**: Sessions update their names as documents are added
- **Full history**: Complete audit trail of all name changes
- **Multi-document support**: Process multiple PDFs in a single session

## Directory Structure

```
project/
├── inputs/                    # Symlinks to original PDFs
│   ├── vendor_questionnaire.pdf -> /original/path/vendor_questionnaire.pdf
│   ├── compliance_report.pdf -> /another/path/compliance_report.pdf
│   └── risk_assessment.pdf -> /yet/another/path/risk_assessment.pdf
├── outputs/                   # All transformations
│   ├── vendor_questionnaire_text.txt
│   ├── vendor_questionnaire_facts.json
│   ├── compliance_report_text.txt
│   ├── compliance_report_facts.json
│   ├── risk_assessment_text.txt
│   └── risk_assessment_facts.json
└── .frfr_sessions/           # Session working data
    └── sess_security_compliance_assessment_20251105_173454/
        ├── metadata.json     # Document registry & name history
        ├── summaries/        # LLM-generated document summaries
        │   ├── vendor_questionnaire.json
        │   ├── compliance_report.json
        │   └── risk_assessment.json
        ├── facts/           # Per-chunk extracted facts
        │   ├── vendor_questionnaire_chunk_0001.json
        │   ├── vendor_questionnaire_chunk_0002.json
        │   └── ...
        └── chunks/          # Original chunk text (for debugging)
            └── ...
```

## Session Naming

### Automatic Generation

When you create a session without specifying a name, frfr uses Claude LLM to generate a succinct, descriptive title:

```bash
# Single document
frfr process soc2_audit_report.pdf
# Generated: sess_soc2_audit_report_20251105_164525

# Multiple documents
frfr process vendor_security.pdf compliance_docs.pdf risk_assessment.pdf
# Generated: sess_vendor_security_compliance_20251105_164531
```

The LLM prompt asks Claude to:
- Generate a 2-5 word title
- Capture the essence of what the documents are about
- Use filesystem-safe characters
- Be descriptive and specific

### Automatic Renaming

As you add documents to a session, the name automatically updates to reflect the current document set:

```bash
# Start with first document
frfr process vendor_questionnaire.pdf
# Session: sess_vendor_questionnaire_20251105_173454

# Add second document - session renamed!
frfr process vendor_questionnaire.pdf compliance_report.pdf
# Session: sess_security_compliance_documentation_20251105_173454
# ℹ  Session name updated to reflect documents

# Add third document - renamed again!
frfr process vendor_questionnaire.pdf compliance_report.pdf risk_assessment.pdf
# Session: sess_security_compliance_assessment_20251105_173454
# ℹ  Session name updated to reflect documents
```

**Key features:**
- Timestamp is preserved from original creation
- All renames tracked in metadata
- Directory physically renamed on filesystem
- All internal paths updated automatically

### Manual Naming

You can always specify a custom session ID:

```bash
frfr process report.pdf --session-id my_custom_session
```

## Metadata Structure

Each session maintains comprehensive metadata in `metadata.json`:

```json
{
  "session_id": "sess_security_compliance_assessment_20251105_173454",
  "created_at": "2025-11-05T17:34:54.095560",
  "status": "active",
  "document_registry": {
    "vendor_questionnaire": {
      "original_pdf_path": "/Users/user/docs/vendor_questionnaire.pdf",
      "symlink_path": "inputs/vendor_questionnaire.pdf",
      "text_file": "outputs/vendor_questionnaire_text.txt",
      "facts_file": ".frfr_sessions/sess_security_compliance_assessment_20251105_173454/facts/vendor_questionnaire_facts.json",
      "status": "completed",
      "added_at": "2025-11-05T17:34:54.095560",
      "completed_at": "2025-11-05T17:42:15.123456"
    },
    "compliance_report": {
      "original_pdf_path": "/Users/user/docs/compliance_report.pdf",
      "symlink_path": "inputs/compliance_report.pdf",
      "text_file": "outputs/compliance_report_text.txt",
      "facts_file": ".frfr_sessions/sess_security_compliance_assessment_20251105_173454/facts/compliance_report_facts.json",
      "status": "completed",
      "added_at": "2025-11-05T17:34:58.920555",
      "completed_at": "2025-11-05T17:50:22.987654"
    },
    "risk_assessment": {
      "original_pdf_path": "/Users/user/docs/risk_assessment.pdf",
      "symlink_path": "inputs/risk_assessment.pdf",
      "text_file": "outputs/risk_assessment_text.txt",
      "facts_file": ".frfr_sessions/sess_security_compliance_assessment_20251105_173454/facts/risk_assessment_facts.json",
      "status": "completed",
      "added_at": "2025-11-05T17:35:04.669613",
      "completed_at": "2025-11-05T17:58:30.112233"
    }
  },
  "name_history": [
    {
      "name": "sess_vendor_questionnaire_20251105_173454",
      "timestamp": "2025-11-05T17:34:54.095560",
      "reason": "Initial creation"
    },
    {
      "name": "sess_security_compliance_documentation_20251105_173454",
      "timestamp": "2025-11-05T17:34:58.920555",
      "reason": "Renamed from sess_vendor_questionnaire_20251105_173454",
      "previous_name": "sess_vendor_questionnaire_20251105_173454"
    },
    {
      "name": "sess_security_compliance_assessment_20251105_173454",
      "timestamp": "2025-11-05T17:35:04.669613",
      "reason": "Renamed from sess_security_compliance_documentation_20251105_173454",
      "previous_name": "sess_security_compliance_documentation_20251105_173454"
    }
  ]
}
```

## Document Registry

Each document in the session tracks:

- **original_pdf_path**: Absolute path to the original PDF
- **symlink_path**: Symlink in `inputs/` directory
- **text_file**: Extracted text in `outputs/`
- **facts_file**: Extracted facts in `outputs/`
- **status**: Current processing state
  - `pending`: Added but not yet processed
  - `processing`: Currently being processed
  - `completed`: Successfully processed
  - `failed`: Processing failed (includes error_message)
- **added_at**: When document was added to session
- **completed_at**: When processing finished

## Multi-Document Workflows

### Process Multiple Documents Together

```bash
# All at once
frfr process doc1.pdf doc2.pdf doc3.pdf

# This will:
# 1. Generate session name from all documents
# 2. Create symlinks in inputs/
# 3. Process each document sequentially
# 4. Track status of each document
# 5. Support cross-document queries in interactive mode
```

### Build Up a Session Over Time

```bash
# Start with first document
frfr process doc1.pdf --session-id my_analysis

# Add more documents later
frfr process doc2.pdf --session-id my_analysis
# Session name updates automatically!

frfr process doc3.pdf --session-id my_analysis
# Session name updates again!
```

### Check Session Status

```bash
# View session information
frfr session-info sess_security_compliance_assessment_20251105_173454

# Output shows:
# - Session ID and directory
# - All documents and their status
# - Processing statistics
# - Name history
```

## Symlinks vs Copies

Frfr uses **symlinks** rather than copying PDFs because:

1. **Preserves originals**: PDFs stay in their original locations
2. **Saves disk space**: No duplicate copies
3. **Version control**: Original files can be tracked by git/other VCS
4. **Flexibility**: Move sessions without moving PDFs

If you need to archive a session with its PDFs, resolve the symlinks:

```bash
# Create archive with actual PDFs
cd inputs/
for link in *.pdf; do
    cp -L "$link" "../archive/$link"
done
```

## Resume and Recovery

Sessions support resume capability:

```bash
# If processing is interrupted, resume from last chunk
frfr extract-facts outputs/document_text.txt \
  --session-id sess_security_compliance_assessment_20251105_173454 \
  --start-chunk 85
```

The session tracks:
- Which chunks have been processed
- Last successful chunk
- Processing statistics

## Best Practices

### Naming

- Let frfr generate names automatically for best results
- Use `--session-id` only when you need specific naming
- Names are descriptive but stay under 50 characters

### Organization

- Keep related documents in the same session
- Use separate sessions for different projects/analyses
- Check `frfr session-info` to review session contents

### Cleanup

- Sessions are kept in `.frfr_sessions/` which is gitignored
- Archive completed sessions if needed
- `outputs/` contains your processed data (facts, text)
- Original PDFs are never modified

### Multi-Document Analysis

- Process related documents together for better context
- Session names will evolve to reflect the document set
- Cross-document queries work in interactive mode
- Each document maintains independent processing status

## API Usage

For programmatic access to session features:

```python
from frfr.session import Session

# Create session with automatic naming
doc_names = ["vendor_security", "compliance_report"]
session_id = Session.generate_session_id(doc_names, use_llm=True)
session = Session(session_id=session_id)

# Add documents
doc_info = session.add_document("/path/to/vendor_security.pdf")
if doc_info["session_renamed"]:
    print(f"Session renamed to: {doc_info['new_session_id']}")

# Get all documents
documents = session.get_documents()
for doc_name, info in documents.items():
    print(f"{doc_name}: {info['status']}")

# Update status
session.update_document_status("vendor_security", "completed")

# Check name history
history = session.metadata.get("name_history", [])
for entry in history:
    print(f"{entry['name']}: {entry['reason']}")
```

## Troubleshooting

### Session Already Exists

If you try to create a session with a name that exists:

```bash
# Use existing session
frfr process doc.pdf --session-id existing_session

# Or let frfr generate a new unique name
frfr process doc.pdf  # Timestamp ensures uniqueness
```

### Symlink Errors

If symlinks fail (e.g., across filesystems):

```bash
# Copy PDFs to project directory first
cp /path/to/doc.pdf documents/
frfr process documents/doc.pdf
```

### Finding Old Sessions

```bash
# List all sessions
ls -1 .frfr_sessions/

# Find sessions by date
ls -lt .frfr_sessions/

# Search by name pattern
ls .frfr_sessions/ | grep security
```

## Future Enhancements

Planned improvements to session management:

- Session tags/labels for organization
- Session search and filtering
- Session merging capabilities
- Export/import session data
- Session templates for common workflows
