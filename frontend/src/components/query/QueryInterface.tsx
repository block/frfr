import { useState } from 'react';
import type { QueryResponse } from '../../api/types';

interface Props {
  onSubmit: (query: string) => void;
  loading: boolean;
  error: string | null;
  response: QueryResponse | null;
  onSourceClick: (index: number) => void;
}

function QueryInterface({ onSubmit, loading, error, response, onSourceClick }: Props) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmit(query.trim());
    }
  };

  return (
    <div className="card">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Ask a question about your documents</label>
          <textarea
            className="form-input"
            placeholder="e.g., What encryption methods are used for data at rest?"
            rows={3}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !query.trim()}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {error && (
        <div className="mt-4" style={{ color: 'var(--color-error)' }}>
          <p>{error}</p>
        </div>
      )}

      {response && (
        <div className="mt-4">
          <h4 className="form-label">Answer</h4>
          <div
            style={{
              padding: '1rem',
              backgroundColor: 'var(--color-bg)',
              borderRadius: '0.375rem',
              whiteSpace: 'pre-wrap',
            }}
          >
            {response.answer}
          </div>

          {response.sources.length > 0 && (
            <div className="mt-4">
              <h4 className="form-label">Sources ({response.sources.length})</h4>
              <div className="flex flex-col gap-2">
                {response.sources.map((source, i) => (
                  <div
                    key={i}
                    onClick={() => onSourceClick(i)}
                    style={{
                      padding: '0.75rem',
                      border: '1px solid var(--color-border)',
                      borderRadius: '0.375rem',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-primary)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.borderColor = 'var(--color-border)';
                    }}
                  >
                    <p className="text-sm">{source.claim}</p>
                    <div className="flex gap-2 mt-1 text-xs text-muted">
                      <span>{source.document}</span>
                      <span>&middot;</span>
                      <span>{source.location}</span>
                      <span>&middot;</span>
                      <span>{Math.round(source.confidence * 100)}% confidence</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-muted mt-4">Query completed in {response.duration}</p>
        </div>
      )}
    </div>
  );
}

export default QueryInterface;
