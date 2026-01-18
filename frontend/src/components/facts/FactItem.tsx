import type { ExtractedFact } from '../../api/types';

interface Props {
  fact: ExtractedFact;
  isSelected: boolean;
  onClick: () => void;
}

function FactItem({ fact, isSelected, onClick }: Props) {
  const getTypeBadge = (type?: string) => {
    if (!type) return null;
    const colors: Record<string, string> = {
      technical_control: '#2563eb',
      organizational: '#7c3aed',
      process: '#059669',
      metric: '#d97706',
      CUEC: '#dc2626',
      test_result: '#0891b2',
      architecture: '#4f46e5',
      compliance: '#16a34a',
    };
    return (
      <span
        style={{
          display: 'inline-block',
          padding: '0.125rem 0.5rem',
          borderRadius: '9999px',
          fontSize: '0.6875rem',
          fontWeight: 500,
          backgroundColor: `${colors[type] || '#64748b'}20`,
          color: colors[type] || '#64748b',
        }}
      >
        {type.replace('_', ' ')}
      </span>
    );
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return '#16a34a';
    if (confidence >= 0.7) return '#ca8a04';
    return '#dc2626';
  };

  return (
    <div
      onClick={onClick}
      style={{
        padding: '0.75rem',
        border: `1px solid ${isSelected ? 'var(--color-primary)' : 'var(--color-border)'}`,
        borderRadius: '0.375rem',
        cursor: 'pointer',
        backgroundColor: isSelected ? 'rgba(37, 99, 235, 0.05)' : 'transparent',
        transition: 'all 0.15s ease',
      }}
    >
      <div className="flex justify-between items-center gap-2 mb-1">
        <div className="flex gap-2 items-center">
          {getTypeBadge(fact.fact_type)}
          {fact.control_family && (
            <span className="text-xs text-muted">{fact.control_family}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span
            className="text-xs"
            style={{ color: getConfidenceColor(fact.confidence) }}
          >
            {Math.round(fact.confidence * 100)}%
          </span>
        </div>
      </div>

      <p className="text-sm" style={{ marginBottom: '0.5rem' }}>
        {fact.claim}
      </p>

      <div className="flex gap-2 flex-wrap">
        {fact.entities?.slice(0, 3).map((entity, i) => (
          <span
            key={i}
            className="text-xs"
            style={{
              padding: '0.125rem 0.375rem',
              backgroundColor: 'var(--color-bg)',
              borderRadius: '0.25rem',
            }}
          >
            {entity}
          </span>
        ))}
        {fact.quantitative_values?.slice(0, 2).map((value, i) => (
          <span
            key={`q${i}`}
            className="text-xs"
            style={{
              padding: '0.125rem 0.375rem',
              backgroundColor: '#fef3c7',
              borderRadius: '0.25rem',
            }}
          >
            {value}
          </span>
        ))}
      </div>

      <p className="text-xs text-muted" style={{ marginTop: '0.5rem' }}>
        {fact.source_doc} &middot; {fact.source_location}
      </p>
    </div>
  );
}

export default FactItem;
