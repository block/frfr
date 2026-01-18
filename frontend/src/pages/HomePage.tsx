import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { SessionListItem } from '../api/types';
import NewSessionModal from '../components/sessions/NewSessionModal';

function HomePage() {
  const [sessions, setSessions] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      setLoading(true);
      const data = await api.listSessions();
      setSessions(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (sessionId: string) => {
    if (!confirm('Are you sure you want to delete this session?')) {
      return;
    }
    try {
      await api.deleteSession(sessionId);
      setSessions(sessions.filter((s) => s.session_id !== sessionId));
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to delete session');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusBadge = (status: string) => {
    const classes: Record<string, string> = {
      active: 'badge badge-info',
      processing: 'badge badge-warning',
      completed: 'badge badge-success',
    };
    return <span className={classes[status] || 'badge'}>{status}</span>;
  };

  if (loading) {
    return <div className="text-muted">Loading sessions...</div>;
  }

  if (error) {
    return (
      <div className="card">
        <p className="text-error">{error}</p>
        <button className="btn btn-secondary mt-4" onClick={loadSessions}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Sessions</h2>
          <button className="btn btn-primary" onClick={() => setShowNewModal(true)}>
            New Session
          </button>
        </div>

        {sessions.length === 0 ? (
          <p className="text-muted">
            No sessions yet. Create one to get started.
          </p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Documents</th>
                <th>Facts</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr key={session.session_id}>
                  <td>
                    <Link to={`/sessions/${session.session_id}`}>
                      {session.name}
                    </Link>
                  </td>
                  <td>{session.document_count}</td>
                  <td>{session.fact_count}</td>
                  <td>{getStatusBadge(session.status)}</td>
                  <td className="text-muted text-sm">
                    {formatDate(session.created_at)}
                  </td>
                  <td>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleDelete(session.session_id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showNewModal && (
        <NewSessionModal
          onClose={() => setShowNewModal(false)}
          onCreated={(session) => {
            setSessions([
              {
                session_id: session.session_id,
                name: session.session_id,
                created_at: session.created_at,
                status: session.status,
                document_count: Object.keys(session.document_registry).length,
                fact_count: 0,
              },
              ...sessions,
            ]);
            setShowNewModal(false);
          }}
        />
      )}
    </>
  );
}

export default HomePage;
