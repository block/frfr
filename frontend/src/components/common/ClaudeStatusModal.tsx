interface Props {
  onClose: () => void;
}

function ClaudeStatusModal({ onClose }: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Claude Not Available</h3>
          <button className="modal-close" onClick={onClose}>
            &times;
          </button>
        </div>

        <div style={{ padding: '1rem 0' }}>
          <p style={{ marginBottom: '1rem' }}>
            Claude is required for document processing and queries. Please configure one of the following:
          </p>

          <div style={{ marginBottom: '1rem' }}>
            <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Option 1: API Key
            </h4>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>
              Make sure <code style={{ background: 'var(--color-surface)', padding: '0.125rem 0.25rem', borderRadius: '0.25rem' }}>ANTHROPIC_API_KEY</code> is available in your environment, or pass it when starting frfr.
            </p>
          </div>

          <div>
            <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              Option 2: Claude CLI
            </h4>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>
              Install the Claude CLI and sign in with <code style={{ background: 'var(--color-surface)', padding: '0.125rem 0.25rem', borderRadius: '0.25rem' }}>claude login</code>. Visit{' '}
              <a
                href="https://docs.anthropic.com/en/docs/claude-code"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'var(--color-primary)' }}
              >
                docs.anthropic.com
              </a>{' '}
              for setup instructions.
            </p>
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-primary" onClick={onClose}>
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}

export default ClaudeStatusModal;
