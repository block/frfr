#!/bin/bash
# V5 Extraction Monitor - Real-time tracking of V5 features

echo "========================================================================"
echo "V5 EXTRACTION MONITOR"
echo "========================================================================"
echo ""

# Check if log file exists
if [ ! -f "v5_extraction.log" ]; then
    echo "Waiting for extraction to start..."
    exit 0
fi

# Get session directory
SESSION_DIR=$(grep "Directory:" v5_extraction.log | head -1 | awk '{print $3}')

# Progress tracking
LATEST_CHUNK=$(grep -oE "chunk [0-9]+" v5_extraction.log 2>/dev/null | sed 's/chunk //' | sort -n | tail -1)
TOTAL_CHUNKS=165

if [ -n "$LATEST_CHUNK" ]; then
    PROGRESS=$((LATEST_CHUNK * 100 / TOTAL_CHUNKS))
    echo "📊 Progress: Chunk $LATEST_CHUNK / ~$TOTAL_CHUNKS ($PROGRESS%)"
else
    echo "📊 Progress: Starting..."
fi

echo ""
echo "🔍 V5 Feature Usage:"
echo "-------------------------------------------------------------------"

# Check for facts with multiple evidence quotes in session
if [ -d "$SESSION_DIR/facts" ]; then
    TOTAL_FACTS=$(python3 -c "
import json
from pathlib import Path
count = 0
for f in Path('$SESSION_DIR/facts').glob('*.json'):
    with open(f) as file:
        count += len(json.load(file))
print(count)
" 2>/dev/null)

    MULTI_QUOTE_FACTS=$(python3 -c "
import json
from pathlib import Path
count = 0
for f in Path('$SESSION_DIR/facts').glob('*.json'):
    with open(f) as file:
        facts = json.load(file)
        for fact in facts:
            eq = fact.get('evidence_quotes', [])
            if len(eq) > 1:
                count += 1
print(count)
" 2>/dev/null)

    SINGLE_QUOTE_FACTS=$((TOTAL_FACTS - MULTI_QUOTE_FACTS))

    echo "  Total facts extracted: $TOTAL_FACTS"
    echo "  Single evidence quote: $SINGLE_QUOTE_FACTS"
    echo "  Multiple evidence quotes: $MULTI_QUOTE_FACTS"

    if [ $TOTAL_FACTS -gt 0 ]; then
        MULTI_PERCENTAGE=$(python3 -c "print(f'{$MULTI_QUOTE_FACTS / $TOTAL_FACTS * 100:.1f}')" 2>/dev/null)
        echo "  Multiple quote usage: $MULTI_PERCENTAGE%"
    fi
else
    echo "  Waiting for first facts to be extracted..."
fi

echo ""
echo "⏱️  Estimated completion: ~2-3 hours"
echo ""
echo "To check detailed progress: tail -f v5_extraction.log"
echo "To view this monitor again: bash v5_extraction_monitor.sh"
echo "========================================================================"
