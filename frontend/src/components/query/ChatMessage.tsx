import { useMemo } from 'react';
import type { SourceEvidence } from '../../api/types';

interface Props {
  query: string;
  answer?: string;
  sources?: SourceEvidence[];
  onSourceClick?: (index: number) => void;
  activeFactIndex?: number | null;
  isStreaming?: boolean;
}

// Parse answer text and make citation references clickable
// Citations use canonical fact_index numbers (e.g., [42], [156])
export function renderAnswerWithCitations(
  answer: string,
  sources: SourceEvidence[],
  onSourceClick: (index: number) => void,
  activeFactIndex: number | null
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const citationRegex = /\[(\d+(?:\s*,\s*\d+)*)\]/g;

  const factIndexToSourceIndex = new Map<number, number>();
  sources.forEach((source, idx) => {
    factIndexToSourceIndex.set(source.fact_index, idx);
  });

  let lastIndex = 0;
  let match;
  let keyIndex = 0;

  while ((match = citationRegex.exec(answer)) !== null) {
    if (match.index > lastIndex) {
      parts.push(answer.slice(lastIndex, match.index));
    }

    const numbersStr = match[1];
    const factIndices = numbersStr.split(/\s*,\s*/).map(n => parseInt(n, 10));

    const citationLinks = factIndices.map((factIndex, i) => {
      const sourceIndex = factIndexToSourceIndex.get(factIndex);
      const isValid = sourceIndex !== undefined;
      const isActive = factIndex === activeFactIndex;

      return (
        <span key={`${keyIndex}-${i}`}>
          {i > 0 && <span style={{ color: 'var(--color-primary)' }}>, </span>}
          {isValid ? (
            <a
              href="#"
              onClick={(e) => {
                e.preventDefault();
                onSourceClick(sourceIndex);
              }}
              style={{
                color: isActive ? 'white' : 'var(--color-primary)',
                backgroundColor: isActive ? 'var(--color-primary)' : 'transparent',
                textDecoration: 'none',
                fontWeight: 500,
                padding: isActive ? '0.125rem 0.25rem' : '0',
                borderRadius: '0.25rem',
              }}
              onMouseOver={(e) => {
                if (!isActive) e.currentTarget.style.textDecoration = 'underline';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.textDecoration = 'none';
              }}
            >
              {factIndex}
            </a>
          ) : (
            <span style={{ color: 'var(--color-primary)' }}>{factIndex}</span>
          )}
        </span>
      );
    });

    parts.push(
      <span key={`citation-${keyIndex}`} style={{ color: 'var(--color-primary)' }}>
        [{citationLinks}]
      </span>
    );

    keyIndex++;
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < answer.length) {
    parts.push(answer.slice(lastIndex));
  }

  return parts;
}

function ChatMessage({ query, answer, sources, onSourceClick, activeFactIndex, isStreaming }: Props) {
  const renderedAnswer = useMemo(() => {
    if (!answer || !sources || !onSourceClick) return null;
    return renderAnswerWithCitations(answer, sources, onSourceClick, activeFactIndex ?? null);
  }, [answer, sources, onSourceClick, activeFactIndex]);

  return (
    <div className="flex flex-col" style={{ gap: '1rem', marginBottom: '0.75rem' }}>
      {/* User query bubble */}
      <div className="flex" style={{ justifyContent: 'flex-end' }}>
        <div
          style={{
            maxWidth: '80%',
            padding: '0.75rem 1rem',
            borderRadius: '1rem 1rem 0.25rem 1rem',
            backgroundColor: 'var(--color-primary)',
            color: 'white',
            whiteSpace: 'pre-wrap',
            lineHeight: '1.5',
          }}
        >
          {query}
        </div>
      </div>

      {/* Assistant answer bubble */}
      {answer && (
        <div className="flex" style={{ justifyContent: 'flex-start' }}>
          <div
            style={{
              maxWidth: '80%',
              padding: '0.75rem 1rem',
              borderRadius: '1rem 1rem 1rem 0.25rem',
              backgroundColor: 'var(--color-surface, var(--color-bg))',
              border: '1px solid var(--color-border)',
              whiteSpace: 'pre-wrap',
              lineHeight: '1.6',
            }}
          >
            {renderedAnswer ?? answer}
            {isStreaming && (
              <span style={{ animation: 'pulse 1s infinite', opacity: 0.6 }}>&#9608;</span>
            )}
          </div>
        </div>
      )}

    </div>
  );
}

export default ChatMessage;
