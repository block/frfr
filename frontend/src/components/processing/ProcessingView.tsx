import { useMemo } from 'react';
import type { ProcessingEvent } from '../../api/types';

interface Props {
  events: ProcessingEvent[];
  isProcessing: boolean;
  onClear: () => void;
}

interface ChunkProgress {
  totalChunks: number;
  completedChunks: Set<string>;
  runningChunks: Set<string>;
  factsExtracted: number;
  currentDocument: string | null;
}

function ProcessingView({ events, isProcessing, onClear }: Props) {
  // Parse events to extract chunk progress for the current document
  const chunkProgress = useMemo<ChunkProgress>(() => {
    let totalChunks = 0;
    let completedChunks = new Set<string>();
    let runningChunks = new Set<string>();
    let factsExtracted = 0;
    let currentDocument: string | null = null;

    for (const event of events) {
      // When a new document starts, reset progress tracking
      if (event.type === 'document_start' && event.document) {
        currentDocument = event.document;
        totalChunks = 0;
        completedChunks = new Set<string>();
        runningChunks = new Set<string>();
        factsExtracted = 0;
      }

      // Parse "Split document into X chunks" message
      if (event.message) {
        const splitMatch = event.message.match(/Split document into (\d+) chunks/);
        if (splitMatch) {
          totalChunks = parseInt(splitMatch[1], 10);
        }
      }

      // Track chunk_complete events (use data.facts_extracted to avoid double counting)
      if (event.type === 'chunk_complete' && event.chunk_id) {
        completedChunks.add(event.chunk_id);
        runningChunks.delete(event.chunk_id);
        if (event.data && typeof event.data === 'object' && 'facts_extracted' in event.data) {
          factsExtracted += (event.data as { facts_extracted: number }).facts_extracted;
        }
      }

      // Track document completion
      if (event.type === 'document_complete' && event.document === currentDocument) {
        // Mark as complete - don't reset yet, keep showing until next doc starts
      }
    }

    return { totalChunks, completedChunks, runningChunks, factsExtracted, currentDocument };
  }, [events]);

  // Calculate progress from events
  const latestProgress = events
    .filter((e) => e.progress !== undefined)
    .slice(-1)[0]?.progress ?? 0;

  // Calculate actual progress based on chunks if we have that info
  const calculatedProgress = chunkProgress.totalChunks > 0
    ? chunkProgress.completedChunks.size / chunkProgress.totalChunks
    : latestProgress;

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
          {isProcessing ? (
            <>
              Processing
              {chunkProgress.currentDocument && (
                <span style={{ fontWeight: 'normal', marginLeft: '8px' }}>
                  — {chunkProgress.currentDocument}
                </span>
              )}
            </>
          ) : (
            'Processing Complete'
          )}
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
          <span>{Math.round(calculatedProgress * 100)}%</span>
        </div>
        <div
          style={{
            height: '8px',
            backgroundColor: 'var(--color-border)',
            borderRadius: '4px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${calculatedProgress * 100}%`,
              backgroundColor: calculatedProgress >= 1
                ? 'var(--color-success)'
                : 'var(--color-primary)',
              transition: 'width 0.3s ease',
            }}
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
          <p className="text-sm font-medium">{chunkProgress.factsExtracted}</p>
        </div>
        <div>
          <p className="text-xs text-muted">Chunks</p>
          <p className="text-sm font-medium">
            {chunkProgress.totalChunks > 0
              ? `${chunkProgress.completedChunks.size}/${chunkProgress.totalChunks}`
              : '—'}
          </p>
        </div>
      </div>

      {/* Chunk progress grid */}
      {chunkProgress.totalChunks > 0 && (
        <div className="mb-4">
          <div className="flex gap-4 text-sm mb-2">
            <div className="flex items-center gap-2">
              <div
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-primary)',
                  animation: isProcessing ? 'pulse 1.5s infinite' : 'none',
                }}
              />
              <span>
                {chunkProgress.totalChunks - chunkProgress.completedChunks.size} pending
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-success)',
                }}
              />
              <span>{chunkProgress.completedChunks.size} complete</span>
            </div>
          </div>

          {/* Chunk indicators grid */}
          <div className="flex gap-1 flex-wrap">
            {Array.from({ length: chunkProgress.totalChunks }).map((_, i) => {
              const chunkId = `chunk_${String(i).padStart(4, '0')}`;
              const isComplete = chunkProgress.completedChunks.has(chunkId);
              const isRunning = chunkProgress.runningChunks.has(chunkId);
              return (
                <div
                  key={i}
                  title={`Chunk ${i}`}
                  style={{
                    width: '24px',
                    height: '24px',
                    borderRadius: '4px',
                    backgroundColor: isComplete
                      ? 'var(--color-success)'
                      : isRunning
                      ? 'var(--color-primary)'
                      : 'var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '10px',
                    color: isComplete || isRunning ? 'white' : 'var(--color-muted)',
                    animation: isRunning ? 'pulse 1.5s infinite' : 'none',
                  }}
                >
                  {i}
                </div>
              );
            })}
          </div>

          <style>{`
            @keyframes pulse {
              0%, 100% { opacity: 1; }
              50% { opacity: 0.5; }
            }
          `}</style>
        </div>
      )}

      {/* Log output */}
      <div className="log-output">
        {events.length === 0 ? (
          <p className="text-muted">
            {isProcessing ? 'Reconnected to processing stream, waiting for events...' : 'Waiting for events...'}
          </p>
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
