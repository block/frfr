import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Session, DocumentListItem, ProcessingEvent } from '../api/types';
import DocumentsTable from '../components/documents/DocumentsTable';
import AddDocumentModal from '../components/documents/AddDocumentModal';
import ProcessingView from '../components/processing/ProcessingView';

function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [session, setSession] = useState<Session | null>(null);
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddDoc, setShowAddDoc] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [events, setEvents] = useState<ProcessingEvent[]>([]);

  useEffect(() => {
    if (sessionId) {
      loadSession();
    }
  }, [sessionId]);

  const loadSession = async () => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const [sessionData, docsData] = await Promise.all([
        api.getSession(sessionId),
        api.listDocuments(sessionId),
      ]);
      setSession(sessionData);
      setDocuments(docsData);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load session');
    } finally {
      setLoading(false);
    }
  };

  const handleStartProcessing = async () => {
    if (!sessionId) return;
    try {
      setProcessing(true);
      setEvents([]);
      await api.startProcessing(sessionId);

      // Subscribe to events
      const cleanup = api.subscribeToProcessingEvents(
        sessionId,
        (event) => {
          setEvents((prev) => [...prev, event]);
          if (event.type === 'complete') {
            setProcessing(false);
            loadSession(); // Reload to get updated stats
          }
        },
        () => {
          setProcessing(false);
        }
      );

      return () => cleanup();
    } catch (e) {
      setProcessing(false);
      alert(e instanceof Error ? e.message : 'Failed to start processing');
    }
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
    return <div className="text-muted">Loading session...</div>;
  }

  if (error || !session) {
    return (
      <div className="card">
        <p style={{ color: 'var(--color-error)' }}>{error || 'Session not found'}</p>
        <Link to="/" className="btn btn-secondary mt-4">
          Back to Sessions
        </Link>
      </div>
    );
  }

  const pendingDocs = documents.filter((d) => d.status === 'pending' || d.status === 'failed');
  const totalFacts = documents.reduce((sum, d) => sum + d.fact_count, 0);

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="card">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="card-title">{session.session_id}</h2>
            <p className="text-muted text-sm mt-1">
              {documents.length} documents &middot; {totalFacts} facts &middot;{' '}
              {getStatusBadge(session.status)}
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              to={`/sessions/${sessionId}/facts`}
              className="btn btn-secondary"
            >
              Browse Facts
            </Link>
            <Link
              to={`/sessions/${sessionId}/query`}
              className="btn btn-secondary"
            >
              Query
            </Link>
          </div>
        </div>
      </div>

      {/* Processing View */}
      {(processing || events.length > 0) && (
        <ProcessingView
          events={events}
          isProcessing={processing}
          onClear={() => setEvents([])}
        />
      )}

      {/* Documents */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Documents</h3>
          <div className="flex gap-2">
            {pendingDocs.length > 0 && !processing && (
              <button className="btn btn-primary" onClick={handleStartProcessing}>
                Process {pendingDocs.length} Document{pendingDocs.length !== 1 ? 's' : ''}
              </button>
            )}
            <button
              className="btn btn-secondary"
              onClick={() => setShowAddDoc(true)}
            >
              Add Document
            </button>
          </div>
        </div>

        {documents.length === 0 ? (
          <p className="text-muted">No documents yet. Add one to get started.</p>
        ) : (
          <DocumentsTable
            documents={documents}
            sessionId={sessionId!}
            onReprocess={async (docName) => {
              await api.reprocessDocument(sessionId!, docName);
              loadSession();
            }}
          />
        )}
      </div>

      {showAddDoc && (
        <AddDocumentModal
          sessionId={sessionId!}
          onClose={() => setShowAddDoc(false)}
          onAdded={() => {
            setShowAddDoc(false);
            loadSession();
          }}
        />
      )}
    </div>
  );
}

export default SessionPage;
