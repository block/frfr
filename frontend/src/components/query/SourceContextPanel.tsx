import type { SourceEvidence } from '../../api/types';

interface Props {
  source: SourceEvidence;
  onClose: () => void;
}

function SourceContextPanel({ source, onClose }: Props) {
  // Highlight evidence in chunk text
  const renderHighlightedText = () => {
    if (!source.chunk_text) {
      return <p className="text-muted">No source text available.</p>;
    }

    const text = source.chunk_text;

    // Find the quote in the chunk text ourselves (more reliable than backend offsets)
    // This avoids byte/character/surrogate encoding mismatches between Go and JS
    let start = -1;
    let end = -1;

    if (source.quote) {
      // Try exact match first
      start = text.indexOf(source.quote);
      if (start >= 0) {
        end = start + source.quote.length;
      } else {
        // Try normalized whitespace match
        const normalizedQuote = source.quote.replace(/\s+/g, ' ').trim();
        const normalizedText = text.replace(/\s+/g, ' ');
        const normalizedIdx = normalizedText.indexOf(normalizedQuote);

        if (normalizedIdx >= 0) {
          // Map back to original text position
          // Count original characters up to the normalized position
          let origIdx = 0;
          let normIdx = 0;
          while (normIdx < normalizedIdx && origIdx < text.length) {
            if (/\s/.test(text[origIdx])) {
              // Skip whitespace in original, but only count one space in normalized
              while (origIdx < text.length && /\s/.test(text[origIdx])) {
                origIdx++;
              }
              normIdx++;
            } else {
              origIdx++;
              normIdx++;
            }
          }
          start = origIdx;

          // Find end by matching the normalized quote length
          let quoteOrigLen = 0;
          normIdx = 0;
          while (normIdx < normalizedQuote.length && (start + quoteOrigLen) < text.length) {
            if (/\s/.test(text[start + quoteOrigLen])) {
              while ((start + quoteOrigLen) < text.length && /\s/.test(text[start + quoteOrigLen])) {
                quoteOrigLen++;
              }
              normIdx++;
            } else {
              quoteOrigLen++;
              normIdx++;
            }
          }
          end = start + quoteOrigLen;
        }
      }
    }

    // Fall back to backend hints if we couldn't find it
    if (start < 0 && source.highlights && source.highlights.length >= 2) {
      [start, end] = source.highlights;
    }

    if (start < 0 || end < 0 || start >= text.length) {
      return (
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>
          {text}
        </pre>
      );
    }

    return (
      <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>
        {text.slice(0, start)}
        <mark
          style={{
            backgroundColor: '#fef08a',
            padding: '0.125rem',
            borderRadius: '0.125rem',
          }}
        >
          {text.slice(start, end)}
        </mark>
        {text.slice(end)}
      </pre>
    );
  };

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h3 className="card-title">Source Context</h3>
        <button className="modal-close" onClick={onClose}>
          &times;
        </button>
      </div>

      {/* Claim */}
      <div className="mb-4">
        <label className="form-label">Claim</label>
        <p>{source.claim}</p>
      </div>

      {/* Quote */}
      {source.quote && (
        <div className="mb-4">
          <label className="form-label">Evidence Quote</label>
          <p
            style={{
              padding: '0.75rem',
              backgroundColor: '#fefce8',
              borderRadius: '0.375rem',
              fontStyle: 'italic',
            }}
          >
            "{source.quote}"
          </p>
        </div>
      )}

      {/* Metadata */}
      <div className="flex gap-4 mb-4">
        <div>
          <label className="form-label">Document</label>
          <p className="text-sm">{source.document}</p>
        </div>
        <div>
          <label className="form-label">Location</label>
          <p className="text-sm">{source.location}</p>
        </div>
        <div>
          <label className="form-label">Confidence</label>
          <p className="text-sm">{Math.round(source.confidence * 100)}%</p>
        </div>
      </div>

      {/* Full context */}
      <div>
        <label className="form-label">Full Source Context</label>
        <div
          style={{
            maxHeight: '400px',
            overflow: 'auto',
            backgroundColor: 'var(--color-bg)',
            padding: '0.75rem',
            borderRadius: '0.375rem',
            border: '1px solid var(--color-border)',
          }}
        >
          {renderHighlightedText()}
        </div>
      </div>
    </div>
  );
}

export default SourceContextPanel;
