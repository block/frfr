import type { ExtractedFact } from '../../api/types';
import FactItem from './FactItem';

interface Props {
  facts: ExtractedFact[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
}

function FactsBrowser({ facts, selectedIndex, onSelect }: Props) {
  if (facts.length === 0) {
    return <p className="text-muted">No facts found matching your criteria.</p>;
  }

  return (
    <div className="flex flex-col gap-2">
      {facts.map((fact, index) => (
        <FactItem
          key={index}
          fact={fact}
          isSelected={selectedIndex === index}
          onClick={() => onSelect(index)}
        />
      ))}
    </div>
  );
}

export default FactsBrowser;
