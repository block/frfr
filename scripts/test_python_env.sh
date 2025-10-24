#!/bin/bash
# Test Python environment and core dependencies

set -e

SUCCESS=0
FAILURE=1

echo "Testing Python Environment..."
echo "=============================="

# Test 1: Python version
echo -n "  Checking Python version... "
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
    echo "✓ Python $PYTHON_VERSION (>= 3.10)"
else
    echo "✗ Python $PYTHON_VERSION (need >= 3.10)"
    exit $FAILURE
fi

# Test 2: Core packages installed
echo -n "  Checking anthropic... "
if python -c "import anthropic" 2>/dev/null; then
    VERSION=$(python -c "import anthropic; print(anthropic.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

echo -n "  Checking temporalio... "
if python -c "import temporalio" 2>/dev/null; then
    VERSION=$(python -c "import temporalio; print(temporalio.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

echo -n "  Checking pydantic... "
if python -c "import pydantic" 2>/dev/null; then
    VERSION=$(python -c "import pydantic; print(pydantic.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 3: Pydantic functionality
echo -n "  Testing Pydantic models... "
if python -c "
from pydantic import BaseModel, Field

class TestModel(BaseModel):
    name: str = Field(..., description='test')
    value: int = Field(default=42)

m = TestModel(name='test')
assert m.name == 'test'
assert m.value == 42
" 2>/dev/null; then
    echo "✓ Models working"
else
    echo "✗ Model test failed"
    exit $FAILURE
fi

# Test 4: Environment variables
echo -n "  Checking PYTHONUNBUFFERED... "
if [ "$PYTHONUNBUFFERED" = "1" ]; then
    echo "✓ Set"
else
    echo "⚠ Not set (warning only)"
fi

echo -n "  Checking TEMPORAL_ADDRESS... "
if [ -n "$TEMPORAL_ADDRESS" ]; then
    echo "✓ Set to $TEMPORAL_ADDRESS"
else
    echo "⚠ Not set (warning only)"
fi

# Test 5: Package installation check
echo -n "  Checking frfr package... "
if python -c "import frfr" 2>/dev/null; then
    echo "✓ Installed"
else
    echo "⚠ Not installed (expected if not built yet)"
fi

echo ""
echo "Python environment tests passed!"
exit $SUCCESS
