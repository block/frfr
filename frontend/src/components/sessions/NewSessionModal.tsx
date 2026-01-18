import { useState } from 'react';
import { api } from '../../api/client';
import type { Session } from '../../api/types';

interface Props {
  onClose: () => void;
  onCreated: (session: Session) => void;
}

function NewSessionModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState('');
  const [documentPaths, setDocumentPaths] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);

      const paths = documentPaths
        .split('\n')
        .map((p) => p.trim())
        .filter((p) => p);

      const session = await api.createSession({
        name: name || undefined,
        document_paths: paths.length > 0 ? paths : undefined,
      });

      onCreated(session);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create session');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">New Session</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Session Name (optional)</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g., Q4 Audit Review"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Document Paths (optional)</label>
            <textarea
              className="form-input"
              placeholder="/path/to/document.pdf&#10;/path/to/another.pdf"
              rows={4}
              value={documentPaths}
              onChange={(e) => setDocumentPaths(e.target.value)}
              style={{ resize: 'vertical' }}
            />
            <p className="text-xs text-muted mt-1">
              Enter one file path per line. You can also add documents later.
            </p>
          </div>

          {error && (
            <p className="text-sm mb-4" style={{ color: 'var(--color-error)' }}>
              {error}
            </p>
          )}

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Session'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default NewSessionModal;
