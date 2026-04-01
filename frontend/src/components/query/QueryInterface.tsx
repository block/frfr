import { useState, useRef, useEffect } from 'react';

interface Props {
  onSubmit: (query: string) => void;
  loading: boolean;
}

function QueryInterface({ onSubmit, loading }: Props) {
  const [query, setQuery] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }
  }, [query]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && !loading) {
      onSubmit(query.trim());
      setQuery('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        display: 'flex',
        gap: '0.5rem',
        alignItems: 'flex-end',
        padding: '0.75rem 1rem',
        borderTop: '1px solid var(--color-border)',
        backgroundColor: 'var(--color-card-bg, white)',
      }}
    >
      <textarea
        ref={textareaRef}
        className="form-input"
        placeholder="Ask a question about your documents..."
        rows={1}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
        style={{
          flex: 1,
          resize: 'none',
          minHeight: '2.5rem',
          maxHeight: '150px',
          margin: 0,
        }}
      />
      <button
        type="submit"
        className="btn btn-primary"
        disabled={loading || !query.trim()}
        style={{ flexShrink: 0, height: '2.5rem' }}
      >
        {loading ? 'Searching...' : 'Send'}
      </button>
    </form>
  );
}

export default QueryInterface;
