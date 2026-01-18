import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { ExtractedFact, FactContextResponse } from '../api/types';
import FactsBrowser from '../components/facts/FactsBrowser';
import FactDetail from '../components/facts/FactDetail';

function FactsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [facts, setFacts] = useState<ExtractedFact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedFact, setSelectedFact] = useState<number | null>(null);
  const [factContext, setFactContext] = useState<FactContextResponse | null>(null);

  const pageSize = 50;

  useEffect(() => {
    if (sessionId) {
      loadFacts();
    }
  }, [sessionId, page, search, typeFilter]);

  const loadFacts = async () => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const response = await api.listFacts(sessionId, {
        search: search || undefined,
        type: typeFilter || undefined,
        page,
        page_size: pageSize,
      });
      setFacts(response.facts);
      setTotal(response.total);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load facts');
    } finally {
      setLoading(false);
    }
  };

  const loadFactContext = async (index: number) => {
    if (!sessionId) return;
    try {
      const context = await api.getFactContext(sessionId, index);
      setFactContext(context);
      setSelectedFact(index);
    } catch (e) {
      console.error('Failed to load fact context:', e);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <Link to={`/sessions/${sessionId}`} className="text-sm text-muted">
            &larr; Back to Session
          </Link>
          <h2 className="card-title mt-1">Facts Browser</h2>
          <p className="text-muted text-sm">{total} facts total</p>
        </div>
      </div>

      <div className="flex gap-4">
        {/* Facts list */}
        <div className="card" style={{ flex: 1 }}>
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              className="form-input"
              placeholder="Search facts..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              style={{ flex: 1 }}
            />
            <select
              className="form-input"
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setPage(1);
              }}
              style={{ width: 'auto' }}
            >
              <option value="">All types</option>
              <option value="technical_control">Technical Control</option>
              <option value="organizational">Organizational</option>
              <option value="process">Process</option>
              <option value="metric">Metric</option>
              <option value="CUEC">CUEC</option>
              <option value="test_result">Test Result</option>
              <option value="architecture">Architecture</option>
              <option value="compliance">Compliance</option>
            </select>
          </div>

          {error ? (
            <p style={{ color: 'var(--color-error)' }}>{error}</p>
          ) : loading ? (
            <p className="text-muted">Loading facts...</p>
          ) : (
            <>
              <FactsBrowser
                facts={facts}
                selectedIndex={selectedFact}
                onSelect={(index) => loadFactContext((page - 1) * pageSize + index)}
              />

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-between items-center mt-4">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous
                  </button>
                  <span className="text-sm text-muted">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage(page + 1)}
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        {/* Fact detail */}
        {factContext && (
          <div className="card" style={{ flex: 1, maxWidth: '50%' }}>
            <FactDetail
              context={factContext}
              onClose={() => {
                setSelectedFact(null);
                setFactContext(null);
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default FactsPage;
