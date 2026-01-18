import { useState, useMemo } from 'react';
import type { QueryResponse, BatchProgress } from '../../api/types';

interface Props {
  onSubmit: (query: string) => void;
  loading: boolean;
  error: string | null;
  response: QueryResponse | null;
  onSourceClick: (index: number) => void;
  batchProgress: BatchProgress | null;
  totalFacts: number | null;
}

// Parse answer text and make citation references clickable
function renderAnswerWithCitations(
  answer: string,
  sourceCount: number,
  onSourceClick: (index: number) => void
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Match [1], [2], [1, 2], [1, 2, 3], etc.
  const citationRegex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

  let lastIndex = 0;
  let match;
  let keyIndex = 0;

  while ((match = citationRegex.exec(answer)) !== null) {
    // Add text before this citation
    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }

    // Parse the numbers inside the brackets
    const numbersStr = match[1];
    const numbers = numbersStr.split(/\s*,\s*/).map(n => parseInt(n, 10));

    // Create clickable citation links
    const citationLinks = numbers.map((num, i) => {
      const sourceIndex = num - 1; // Convert 1-indexed to 0-indexed
      const isValid = sourceIndex >= 0 && sourceIndex < sourceCount;

      return (
        <span key={`${keyIndex}-${i}`}>
          {i > 0 && ', '}
          {isValid ? (
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                onSourceClick(sourceIndex);
              }}
              style={{
                color: 'var(--color-primary)',
                textDecoration: 'none',
                fontWeight: 500,
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.textDecoration = 'underline';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.textDecoration = 'none';
              }}
            >
              {num}
            </a>
          ) : (
            <span>{num}</span>
          )}
        </span>
      );
    });

    parts.push(
      <span key={`citation-${keyIndex}`} style={{ color: 'var(--color-primary)' }}>
        [{citationLinks}]
      </span>
    );

    keyIndex++;
    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after last citation
  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex));
  }

  return parts;
}

function QueryInterface({ onSubmit, loading, error, response, onSourceClick, batchProgress, totalFacts }: Props) {
  const [query, setQuery] = useState('');

  const renderedAnswer = useMemo(() => {
    if (!response) return null;
    return renderAnswerWithCitations(response.answer, response.sources.length, onSourceClick);
  }, [response, onSourceClick]);

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

      {/* Batch Progress Visualization */}
      {loading && batchProgress && (
        <div className="mt-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium">
              {batchProgress.phase === 'selecting'
                ? 'Step 1: Analyzing facts in parallel...'
                : 'Step 2: Generating answer from relevant facts...'}
            </span>
            <span className="text-xs text-muted">
              {totalFacts ? `${totalFacts} total facts` : ''}
            </span>
          </div>

          {/* Progress bar */}
          <div
            style={{
              height: '8px',
              backgroundColor: 'var(--color-border)',
              borderRadius: '4px',
              overflow: 'hidden',
              marginBottom: '0.75rem',
            }}
          >
            <div
              style={{
                height: '100%',
                width: batchProgress.phase === 'answering'
                  ? '100%'
                  : `${(batchProgress.completed / batchProgress.total_batches) * 100}%`,
                backgroundColor: batchProgress.phase === 'answering'
                  ? 'var(--color-success)'
                  : 'var(--color-primary)',
                transition: 'width 0.3s ease',
              }}
            />
          </div>

          {batchProgress.phase === 'selecting' ? (
            <>
              {/* Batch status grid */}
              <div className="flex gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div
                    style={{
                      width: '12px',
                      height: '12px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--color-primary)',
                      animation: batchProgress.running > 0 ? 'pulse 1.5s infinite' : 'none',
                    }}
                  />
                  <span>{batchProgress.running} running</span>
                </div>
                <div className="flex items-center gap-2">
                  <div
                    style={{
                      width: '12px',
                      height: '12px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--color-success)',
                    }}
                  />
                  <span>{batchProgress.completed}/{batchProgress.total_batches} complete</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-muted">{batchProgress.facts_found} relevant facts found</span>
                </div>
              </div>

              {/* Batch indicators */}
              <div className="flex gap-1 mt-3 flex-wrap">
                {Array.from({ length: batchProgress.total_batches }).map((_, i) => {
                  const isComplete = i < batchProgress.completed;
                  const isRunning = !isComplete && i < batchProgress.completed + batchProgress.running;
                  return (
                    <div
                      key={i}
                      title={`Batch ${i + 1}`}
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '4px',
                        backgroundColor: isComplete
                          ? 'var(--color-success)'
                          : isRunning
                          ? 'var(--color-primary)'
                          : 'var(--color-border)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '10px',
                        color: isComplete || isRunning ? 'white' : 'var(--color-muted)',
                        animation: isRunning ? 'pulse 1.5s infinite' : 'none',
                      }}
                    >
                      {i + 1}
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            /* Answering phase display */
            <div className="flex items-center gap-3 text-sm">
              <div
                style={{
                  width: '16px',
                  height: '16px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-primary)',
                  animation: 'pulse 1.5s infinite',
                }}
              />
              <span>
                Passing {batchProgress.facts_found} relevant facts to Claude for final answer...
              </span>
            </div>
          )}

          <style>{`
            @keyframes pulse {
              0%, 100% { opacity: 1; }
              50% { opacity: 0.5; }
            }
          `}</style>
        </div>
      )}

      {/* Simple loading state when no batch progress yet */}
      {loading && !batchProgress && (
        <div className="mt-4 text-sm text-muted">
          Loading facts...
        </div>
      )}

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
            {renderedAnswer}
          </div>

          <p className="text-xs text-muted mt-4">
            {response.sources.length} source{response.sources.length !== 1 ? 's' : ''} cited &middot; Query completed in {response.duration}
          </p>
        </div>
      )}
    </div>
  );
}

export default QueryInterface;
