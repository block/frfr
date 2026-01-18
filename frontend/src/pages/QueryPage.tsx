import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { QueryResponse, QueryHistoryEntry } from '../api/types';
import QueryInterface from '../components/query/QueryInterface';
import SourceContextPanel from '../components/query/SourceContextPanel';

function QueryPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [history, setHistory] = useState<QueryHistoryEntry[]>([]);
  const [currentResponse, setCurrentResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSourceIndex, setSelectedSourceIndex] = useState<number | null>(null);

  useEffect(() => {
    if (sessionId) {
      loadHistory();
    }
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

  const handleQuery = async (query: string) => {
    if (!sessionId) return;
    try {
      setLoading(true);
      setError(null);
      setSelectedSourceIndex(null);
      const response = await api.submitQuery(sessionId, { query });
      setCurrentResponse(response);
      loadHistory(); // Refresh history
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Query failed');
    } finally {
      setLoading(false);
    }
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
