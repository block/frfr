import type { FactContextResponse } from '../../api/types';

interface Props {
  context: FactContextResponse;
  onClose: () => void;
}

function FactDetail({ context, onClose }: Props) {
  const { fact, chunk_text, highlights } = context;

  // Highlight evidence in chunk text
  const renderHighlightedText = () => {
    if (!chunk_text) return <p className="text-muted">No source text available.</p>;

    if (!highlights || highlights.length === 0) {
      return <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>{chunk_text}</pre>;
    }

    // Sort highlights by start position
    const sortedHighlights = [...highlights].sort((a, b) => a.start - b.start);

    const parts: React.ReactNode[] = [];
    let lastEnd = 0;

    sortedHighlights.forEach((highlight, i) => {
      // Add text before highlight
      if (highlight.start > lastEnd) {
        parts.push(chunk_text.slice(lastEnd, highlight.start));
      }
      // Add highlighted text
      parts.push(
        <mark
          key={i}
          style={{
            backgroundColor: '#fef08a',
            padding: '0.125rem',
            borderRadius: '0.125rem',
          }}
        >
          {chunk_text.slice(highlight.start, highlight.end)}
        </mark>
      );
      lastEnd = highlight.end;
    });

    // Add remaining text
    if (lastEnd < chunk_text.length) {
      parts.push(chunk_text.slice(lastEnd));
    }

    return <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>{parts}</pre>;
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="card-title">Fact Details</h3>
        <button className="modal-close" onClick={onClose}>
          &times;
        </button>
      </div>

      {/* Claim */}
      <div className="mb-4">
        <label className="form-label">Claim</label>
        <p>{fact.claim}</p>
      </div>

      {/* Metadata */}
      <div className="flex gap-4 mb-4">
        <div>
          <label className="form-label">Type</label>
          <p className="text-sm">{fact.fact_type || 'N/A'}</p>
        </div>
        <div>
          <label className="form-label">Confidence</label>
          <p className="text-sm">{Math.round(fact.confidence * 100)}%</p>
        </div>
        <div>
          <label className="form-label">Specificity</label>
          <p className="text-sm">
            {fact.specificity_score ? Math.round(fact.specificity_score * 100) + '%' : 'N/A'}
          </p>
        </div>
      </div>

      {/* Evidence quotes */}
      {(fact.evidence_quotes || fact.evidence_quote) && (
        <div className="mb-4">
          <label className="form-label">Evidence</label>
          {fact.evidence_quotes?.map((eq, i) => (
            <div
              key={i}
              style={{
                padding: '0.5rem',
                backgroundColor: '#fefce8',
                borderRadius: '0.25rem',
                marginBottom: '0.5rem',
              }}
            >
              <p className="text-sm" style={{ fontStyle: 'italic' }}>
                "{eq.quote}"
              </p>
              {eq.source_location && (
                <p className="text-xs text-muted mt-1">{eq.source_location}</p>
              )}
            </div>
          ))}
          {!fact.evidence_quotes && fact.evidence_quote && (
            <p
              className="text-sm"
              style={{
                padding: '0.5rem',
                backgroundColor: '#fefce8',
                borderRadius: '0.25rem',
                fontStyle: 'italic',
              }}
            >
              "{fact.evidence_quote}"
            </p>
          )}
        </div>
      )}

      {/* Entities and values */}
      {(fact.entities?.length || fact.quantitative_values?.length) && (
        <div className="mb-4">
          <label className="form-label">Extracted Data</label>
          <div className="flex gap-2 flex-wrap">
            {fact.entities?.map((entity, i) => (
              <span key={i} className="badge badge-info">
                {entity}
              </span>
            ))}
            {fact.quantitative_values?.map((value, i) => (
              <span key={`q${i}`} className="badge badge-warning">
                {value}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source context */}
      <div>
        <label className="form-label">Source Context</label>
        <p className="text-xs text-muted mb-2">
          {fact.source_doc} &middot; {fact.source_location}
        </p>
        <div
          style={{
            maxHeight: '300px',
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

export default FactDetail;
