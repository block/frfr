import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { QueryResponse, QueryHistoryEntry, BatchProgress } from '../api/types';
import QueryInterface from '../components/query/QueryInterface';
import SourceContextPanel from '../components/query/SourceContextPanel';

function QueryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);
  const [currentResponse, setCurrentResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSourceIndex, setSelectedSourceIndex] = useState<number | null>(null);
  const [batchProgress, setBatchProgress] = useState<BatchProgress | null>(null);
  const [totalFacts, setTotalFacts] = useState<number | null>(null);
  const abortRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (sessionId) {
      loadHistory();
    }
    // Cleanup on unmount
    return () => {
      abortRef.current?.();
    };
  }, [sessionId]);

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

    // Abort any existing query
    abortRef.current?.();

    setLoading(true);
    setError(null);
    setSelectedSourceIndex(null);
    setCurrentResponse(null);
    setBatchProgress(null);
    setTotalFacts(null);

    abortRef.current = api.submitQueryStream(sessionId, { query }, {
      onStatus: (status) => {
        if (status.totalFacts) {
          setTotalFacts(status.totalFacts);
        }
      },
      onProgress: (progress) => {
        setBatchProgress(progress);
      },
      onResult: (result) => {
        setCurrentResponse(result);
        setLoading(false);
        setBatchProgress(null);
        loadHistory();
      },
      onError: (err) => {
        setError(err.message);
        setLoading(false);
        setBatchProgress(null);
      },
    });
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div>
        <Link to={`/sessions/${sessionId}`} className="text-sm text-muted">
          &larr; Back to Session
        </Link>
        <h2 className="card-title mt-1">Query Documents</h2>
      </div>

      <div className="flex gap-4">
        {/* Query interface */}
        <div style={{ flex: 1 }}>
          <QueryInterface
            onSubmit={handleQuery}
            loading={loading}
            error={error}
            response={currentResponse}
            onSourceClick={setSelectedSourceIndex}
            batchProgress={batchProgress}
            totalFacts={totalFacts}
          />

          {/* History */}
          {history.length > 0 && (
            <div className="card mt-4">
              <h3 className="card-title mb-4">Query History</h3>
              <div className="flex flex-col gap-2">
                {history.slice().reverse().map((entry, i) => (
                  <div
                    key={i}
                    className="text-sm"
                    style={{
                      padding: '0.5rem',
                      borderBottom: '1px solid var(--color-border)',
                    }}
                  >
                    <p style={{ fontWeight: 500 }}>{entry.query}</p>
                    <p className="text-muted text-xs mt-1">
                      {new Date(entry.timestamp).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Source context panel */}
        {currentResponse && selectedSourceIndex !== null && (
          <div style={{ width: '40%' }}>
            <SourceContextPanel
              source={currentResponse.sources[selectedSourceIndex]}
              onClose={() => setSelectedSourceIndex(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default QueryPage;
