import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { QueryResponse, QueryHistoryEntry, BatchProgress, SourceEvidence } from '../api/types';
import QueryInterface from '../components/query/QueryInterface';
import ChatMessage, { renderAnswerWithCitations } from '../components/query/ChatMessage';
import SourceContextPanel from '../components/query/SourceContextPanel';

function QueryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);
  const [currentQuery, setCurrentQuery] = useState<string | null>(null);
  const [currentResponse, setCurrentResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSourceIndex, setSelectedSourceIndex] = useState<number | null>(null);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [totalFacts, setTotalFacts] = useState<number | null>(null);
  const [streamingAnswer, setStreamingAnswer] = useState<string>('');
  const [streamingSources, setStreamingSources] = useState<SourceEvidence[]>([]);
  const abortRef = useRef<(() => void) | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  useEffect(() => {
    if (sessionId) {
      loadHistory();
    }
    return () => {
      abortRef.current?.();
    };
  }, [sessionId]);

  // Track whether user is near the bottom of the scroll area
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      isNearBottomRef.current = scrollHeight - scrollTop - clientHeight < 150;
    };
    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);

  // Auto-scroll only if user is already at the bottom
  useEffect(() => {
    if (isNearBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [history, currentQuery, currentResponse, streamingAnswer, batchProgress]);

  const loadHistory = async () => {
    if (!sessionId) return;
    try {
      const data = await api.getQueryHistory(sessionId);
      setHistory(data);
    } catch (e) {
      console.error('Failed to load history:', e);
    }
  };

  const handleQuery = (query: string) => {
    if (!sessionId) return;

    abortRef.current?.();

    setLoading(true);
    setError(null);
    setSelectedSourceIndex(null);
    setCurrentResponse(null);
    setCurrentQuery(query);
    setBatchProgress(null);
    setTotalFacts(null);
    setStreamingAnswer('');
    setStreamingSources([]);

    abortRef.current = api.submitQueryStream(sessionId, { query }, {
      onStatus: (status) => {
        if (status.totalFacts) {
          setTotalFacts(status.totalFacts);
        }
      },
      onProgress: (progress) => {
        setBatchProgress(progress);
      },
      onSources: (sources) => {
        setStreamingSources(sources);
      },
      onAnswerChunk: (chunk) => {
        setStreamingAnswer((prev) => prev + chunk);
      },
      onResult: (result) => {
        setCurrentResponse(result);
        setCurrentQuery(null);
        setStreamingAnswer('');
        setStreamingSources([]);
        setLoading(false);
        setBatchProgress(null);
        loadHistory();
      },
      onError: (err) => {
        setError(err.message);
        setLoading(false);
        setBatchProgress(null);
        setStreamingAnswer('');
      },
    });
  };

  // Get the fact_index of the currently selected source for highlighting
  const activeFactIndex = (() => {
    if (selectedSourceIndex === null) return null;
    const sources = currentResponse?.sources ?? streamingSources;
    return sources?.[selectedSourceIndex]?.fact_index ?? null;
  })();

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 120px)' }}>
      {/* Header */}
      <div className="mb-2">
        <Link to={`/sessions/${sessionId}`} className="text-sm text-muted">
          &larr; Back to Session
        </Link>
        <h2 className="card-title mt-1">Query Documents</h2>
      </div>

      <div className="flex gap-4" style={{ flex: 1, minHeight: 0 }}>
        {/* Chat column */}
        <div className="flex flex-col" style={{ flex: 1, minHeight: 0 }}>
          {/* Scrollable message area */}
          <div
            ref={scrollContainerRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '1rem 0.5rem',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: history.length === 0 && !currentQuery && !currentResponse ? 'center' : 'flex-start',
            }}
          >
            {/* Empty state */}
            {history.length === 0 && !currentQuery && !currentResponse && (
              <div className="text-muted" style={{ textAlign: 'center', padding: '2rem' }}>
                <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Ask a question about your documents</p>
                <p className="text-xs">Your conversation will appear here</p>
              </div>
            )}

            {/* History messages (chronological order) */}
            {history.map((entry, i) => (
              <ChatMessage
                key={`history-${i}`}
                query={entry.query}
                answer={entry.answer}
              />
            ))}

            {/* Current response (completed) */}
            {currentResponse && (
              <ChatMessage
                query={currentResponse.query}
                answer={currentResponse.answer}
                sources={currentResponse.sources}
                onSourceClick={setSelectedSourceIndex}
                activeFactIndex={activeFactIndex}
              />
            )}

            {/* In-progress query */}
            {currentQuery && loading && (
              <div className="flex flex-col" style={{ gap: '1rem', marginBottom: '0.75rem' }}>
                {/* User query bubble */}
                <div className="flex" style={{ justifyContent: 'flex-end' }}>
                  <div
                    style={{
                      maxWidth: '80%',
                      padding: '0.75rem 1rem',
                      borderRadius: '1rem 1rem 0.25rem 1rem',
                      backgroundColor: 'var(--color-primary)',
                      color: 'white',
                      whiteSpace: 'pre-wrap',
                      lineHeight: '1.5',
                    }}
                  >
                    {currentQuery}
                  </div>
                </div>

                {/* Streaming answer - rendered as its own bubble */}
                {streamingAnswer ? (
                  <div className="flex" style={{ justifyContent: 'flex-start' }}>
                    <div
                      style={{
                        maxWidth: '80%',
                        padding: '0.75rem 1rem',
                        borderRadius: '1rem 1rem 1rem 0.25rem',
                        backgroundColor: 'var(--color-surface, var(--color-bg))',
                        border: '1px solid var(--color-border)',
                        whiteSpace: 'pre-wrap',
                        lineHeight: '1.6',
                      }}
                    >
                      {streamingSources && streamingSources.length > 0
                        ? renderAnswerWithCitations(streamingAnswer, streamingSources, setSelectedSourceIndex, null)
                        : streamingAnswer}
                      <span style={{ animation: 'pulse 1s infinite', opacity: 0.6 }}>&#9608;</span>
                    </div>
                  </div>
                ) : (
                  <div className="flex" style={{ justifyContent: 'flex-start' }}>
                    <div
                      style={{
                        maxWidth: '80%',
                        padding: '0.75rem 1rem',
                        borderRadius: '1rem 1rem 1rem 0.25rem',
                        backgroundColor: 'var(--color-surface, var(--color-bg))',
                        border: '1px solid var(--color-border)',
                        lineHeight: '1.6',
                      }}
                    >
                      {batchProgress ? (
                        <ProgressIndicator
                          batchProgress={batchProgress}
                          totalFacts={totalFacts}
                        />
                      ) : (
                        <span className="text-sm text-muted">Thinking...</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Error */}
            {error && (
              <div style={{ color: 'var(--color-error)', padding: '0.5rem', marginBottom: '1rem' }}>
                <p>{error}</p>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input bar pinned at bottom */}
          <QueryInterface onSubmit={handleQuery} loading={loading} />
        </div>

        {/* Source context panel - sticky */}
        {selectedSourceIndex !== null && (() => {
          const sources = currentResponse?.sources ?? streamingSources;
          const source = sources?.[selectedSourceIndex];
          return source ? (
            <div style={{
              width: '40%',
              position: 'sticky',
              top: 0,
              alignSelf: 'flex-start',
              maxHeight: '100%',
              overflowY: 'auto'
            }}>
              <SourceContextPanel
                source={source}
                onClose={() => setSelectedSourceIndex(null)}
              />
            </div>
          ) : null;
        })()}
      </div>
    </div>
  );
}

// Progress indicator for batch processing
function ProgressIndicator({ batchProgress, totalFacts }: { batchProgress: BatchProgress; totalFacts: number | null }) {
  return (
    <div>
      <div className="text-sm" style={{ marginBottom: '0.5rem' }}>
        {batchProgress.phase === 'selecting'
          ? 'Analyzing facts in parallel...'
          : 'Generating answer...'}
        {totalFacts && (
          <span className="text-xs text-muted" style={{ marginLeft: '0.5rem' }}>
            {totalFacts} total facts
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div
        style={{
          height: '6px',
          backgroundColor: 'var(--color-border)',
          borderRadius: '3px',
          overflow: 'hidden',
          marginBottom: '0.5rem',
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

      {batchProgress.phase === 'selecting' && (
        <div className="text-xs text-muted">
          {batchProgress.completed}/{batchProgress.total_batches} batches complete
          {batchProgress.facts_found > 0 && ` \u00b7 ${batchProgress.facts_found} relevant facts found`}
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

export default QueryPage;
