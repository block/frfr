import { useState } from 'react';
import { api } from '../../api/client';

interface Props {
  sessionId: string;
  onClose: () => void;
  onAdded: () => void;
}

function AddSlackChannelModal({ sessionId, onClose, onAdded }: Props) {
  const [channelId, setChannelId] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const id = parseChannelInput(channelId.trim());
    if (!id) {
      setError('Please enter a valid Slack channel ID or URL');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await api.addSlackChannel(sessionId, {
        channel_id: id,
        since: since || undefined,
        until: until || undefined,
      });

      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add Slack channel');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Import from Slack</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Channel ID or URL</label>
            <input
              type="text"
              className="form-input"
              placeholder="C0123ABCDEF or https://slack.com/archives/C0123ABCDEF"
              value={channelId}
              onChange={(e) => setChannelId(e.target.value)}
              disabled={loading}
              autoFocus
            />
            <p className="text-sm text-muted" style={{ marginTop: '0.25rem' }}>
              Find the channel ID in Slack's channel details
            </p>
          </div>

          <div className="flex gap-2">
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">From date (auto: all or last 90 days)</label>
              <input
                type="date"
                className="form-input"
                value={since}
                onChange={(e) => setSince(e.target.value)}
                disabled={loading}
              />
            </div>
            <div className="form-group" style={{ flex: 1 }}>
              <label className="form-label">To date (optional)</label>
              <input
                type="date"
                className="form-input"
                value={until}
                onChange={(e) => setUntil(e.target.value)}
                disabled={loading}
              />
            </div>
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
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !channelId.trim()}
            >
              {loading ? 'Adding...' : 'Import Channel'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// parseChannelInput extracts a channel ID from a raw ID or Slack URL
function parseChannelInput(input: string): string | null {
  // Direct channel ID (starts with C, D, or G)
  if (/^[CDG][A-Z0-9]{8,}$/.test(input)) {
    return input;
  }
  // Slack archive URL: https://slack.com/archives/C0123ABCDEF or similar
  const match = input.match(/\/archives\/([CDG][A-Z0-9]+)/);
  if (match) {
    return match[1];
  }
  // If it looks like just an ID without the right prefix, still accept it
  if (/^[A-Z0-9]{9,}$/.test(input)) {
    return input;
  }
  return null;
}

export default AddSlackChannelModal;
