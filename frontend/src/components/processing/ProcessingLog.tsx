import type { ProcessingEvent } from '../../api/types';

interface Props {
  events: ProcessingEvent[];
}

function ProcessingLog({ events }: Props) {
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
      case 'keepalive':
        return 'log-warning';
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
    <div className="log-output">
      {events.map((event, i) => (
        <div key={i} className={getLogClass(event.type)}>
          <span style={{ opacity: 0.6 }}>[{formatTime(event.timestamp)}]</span>{' '}
          <span style={{ fontWeight: 500 }}>{event.type}</span>
          {event.message && `: ${event.message}`}
          {event.document && (
            <span style={{ opacity: 0.8 }}> ({event.document})</span>
          )}
          {event.chunk_id && (
            <span style={{ opacity: 0.8 }}> [{event.chunk_id}]</span>
          )}
        </div>
      ))}
    </div>
  );
}

export default ProcessingLog;
