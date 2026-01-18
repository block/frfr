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

    if (!source.highlights || source.highlights.length < 2) {
      return (
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: '0.8125rem' }}>
          {source.chunk_text}
        </pre>
      );
    }

    const [start, end] = source.highlights;
    const text = source.chunk_text;

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
