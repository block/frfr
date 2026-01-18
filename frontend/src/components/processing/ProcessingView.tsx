import type { ProcessingEvent } from '../../api/types';

interface Props {
  events: ProcessingEvent[];
  isProcessing: boolean;
  onClear: () => void;
}

function ProcessingView({ events, isProcessing, onClear }: Props) {
  // Calculate progress from events
  const latestProgress = events
    .filter((e) => e.progress !== undefined)
    .slice(-1)[0]?.progress ?? 0;

  // Count facts extracted
  const factsExtracted = events
    .filter((e) => e.type === 'fact_extracted')
    .reduce((sum, e) => sum + ((e.data as { count?: number })?.count || 0), 0);

  const getLogClass = (type: string) => {
    switch (type) {
      case 'error':
        return 'log-error';
      case 'complete':
      case 'document_complete':
        return 'log-success';
      case 'chunk_start':
      case 'document_start':
        return 'log-info';
      default:
        return '';
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          {isProcessing ? 'Processing...' : 'Processing Complete'}
        </h3>
        {!isProcessing && events.length > 0 && (
          <button className="btn btn-secondary btn-sm" onClick={onClear}>
            Clear
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm mb-1">
          <span>Progress</span>
          <span>{Math.round(latestProgress * 100)}%</span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-bar-fill"
            style={{ width: `${latestProgress * 100}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 mb-4">
        <div>
          <p className="text-xs text-muted">Status</p>
          <p className="text-sm font-medium">
            {isProcessing ? (
              <span style={{ color: 'var(--color-warning)' }}>Processing</span>
            ) : (
              <span style={{ color: 'var(--color-success)' }}>Complete</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted">Facts Extracted</p>
          <p className="text-sm font-medium">{factsExtracted}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Events</p>
          <p className="text-sm font-medium">{events.length}</p>
        </div>
      </div>

      {/* Log output */}
      <div className="log-output">
        {events.length === 0 ? (
          <p className="text-muted">Waiting for events...</p>
        ) : (
          events.map((event, i) => (
            <div key={i} className={getLogClass(event.type)}>
              <span style={{ opacity: 0.6 }}>[{formatTime(event.timestamp)}]</span>{' '}
              {event.message || event.type}
              {event.document && (
                <span style={{ opacity: 0.8 }}> ({event.document})</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default ProcessingView;
