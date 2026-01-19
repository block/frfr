import { useState } from 'react';
import { api } from '../../api/client';
import type { Session } from '../../api/types';

interface Props {
  onClose: () => void;
  onCreated: (session: Session) => void;
}

function NewSessionModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState('');
  const [paths, setPaths] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePickFiles = async () => {
    try {
      setPicking(true);
      setError(null);
      const files = await api.pickFiles();
      if (files.length > 0) {
        setPaths(files);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to open file picker');
    } finally {
      setPicking(false);
    }
  };

  const removePath = (index: number) => {
    setPaths(paths.filter((_, i) => i !== index));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      setError(null);

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
            <label className="form-label">Documents (optional)</label>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handlePickFiles}
              disabled={picking || loading}
              style={{ width: '100%' }}
            >
              {picking ? 'Opening...' : 'Choose Files...'}
            </button>
            <p className="text-xs text-muted mt-1">
              You can also add documents after creating the session.
            </p>
          </div>

          {paths.length > 0 && (
            <div className="form-group">
              <label className="form-label">Selected Files ({paths.length})</label>
              <div
                style={{
                  maxHeight: '150px',
                  overflow: 'auto',
                  border: '1px solid var(--color-border)',
                  borderRadius: '0.375rem',
                  padding: '0.5rem',
                }}
              >
                {paths.map((path, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '0.25rem 0',
                      borderBottom: i < paths.length - 1 ? '1px solid var(--color-border)' : undefined,
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.875rem',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        flex: 1,
                      }}
                      title={path}
                    >
                      {path.split('/').pop()}
                    </span>
                    <button
                      type="button"
                      onClick={() => removePath(i)}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--color-muted)',
                        cursor: 'pointer',
                        padding: '0 0.25rem',
                        fontSize: '1rem',
                      }}
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

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
