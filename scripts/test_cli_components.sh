#!/bin/bash
# Test CLI framework components

set -e

SUCCESS=0
FAILURE=1

echo "Testing CLI Components..."
echo "=============================="

# Test 1: click
echo -n "  Checking click... "
if python -c "import click" 2>/dev/null; then
    VERSION=$(python -c "import click; print(click.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 2: click functionality
echo -n "  Testing click commands... "
if python << 'EOF' 2>/dev/null
import click

@click.command()
@click.option('--name', default='World')
def hello(name):
    return f"Hello {name}"

# Test command creation
assert callable(hello)
print("✓ Commands working", end="")
EOF
then
    echo ""
else
    echo "✗ Click command test failed"
    exit $FAILURE
fi

# Test 3: rich
echo -n "  Checking rich... "
if python -c "import rich" 2>/dev/null; then
    VERSION=$(python -c "import rich; print(rich.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 4: rich console
echo -n "  Testing rich console... "
if python << 'EOF' 2>/dev/null
from rich.console import Console
from io import StringIO

# Test console output
output = StringIO()
console = Console(file=output, force_terminal=False)
console.print("Test message")

result = output.getvalue()
assert "Test message" in result
print("✓ Console working", end="")
EOF
then
    echo ""
else
    echo "✗ Rich console test failed"
    exit $FAILURE
fi

# Test 5: rich tables
echo -n "  Testing rich tables... "
if python << 'EOF' 2>/dev/null
from rich.table import Table
from rich.console import Console
from io import StringIO

table = Table(title="Test Table")
table.add_column("Name")
table.add_column("Value")
table.add_row("Test", "123")

output = StringIO()
console = Console(file=output, force_terminal=False)
console.print(table)

result = output.getvalue()
assert "Test" in result
print("✓ Tables working", end="")
EOF
then
    echo ""
else
    echo "✗ Rich table test failed"
    exit $FAILURE
fi

# Test 6: rich progress bars
echo -n "  Testing rich progress... "
if python << 'EOF' 2>/dev/null
from rich.progress import Progress

with Progress() as progress:
    task = progress.add_task("Test", total=100)
    progress.update(task, advance=50)
    assert True  # If we get here, it works

print("✓ Progress bars working", end="")
EOF
then
    echo ""
else
    echo "✗ Rich progress test failed"
    exit $FAILURE
fi

# Test 7: prompt-toolkit
echo -n "  Checking prompt-toolkit... "
if python -c "import prompt_toolkit" 2>/dev/null; then
    VERSION=$(python -c "import prompt_toolkit; print(prompt_toolkit.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 8: prompt-toolkit session (non-interactive)
echo -n "  Testing prompt-toolkit components... "
if python << 'EOF' 2>/dev/null
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter

# Test creating a session (don't actually prompt)
history = InMemoryHistory()
completer = WordCompleter(['test', 'hello', 'world'])
session = PromptSession(history=history, completer=completer)

assert session is not None
print("✓ Prompt components working", end="")
EOF
then
    echo ""
else
    echo "✗ Prompt-toolkit test failed"
    exit $FAILURE
fi

# Test 9: python-dotenv
echo -n "  Checking python-dotenv... "
if python -c "import dotenv" 2>/dev/null; then
    VERSION=$(python -c "import dotenv; print(dotenv.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 10: python-dotenv functionality
echo -n "  Testing dotenv loading... "
if python << 'EOF' 2>/dev/null
import tempfile
import os
from dotenv import load_dotenv

# Create temp .env file
with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
    f.write("TEST_VAR=test_value\n")
    env_file = f.name

# Load it
load_dotenv(env_file)
assert os.getenv('TEST_VAR') == 'test_value'

# Cleanup
os.unlink(env_file)
print("✓ Dotenv loading working", end="")
EOF
then
    echo ""
else
    echo "✗ Dotenv test failed"
    exit $FAILURE
fi

# Test 11: aiofiles
echo -n "  Checking aiofiles... "
if python -c "import aiofiles" 2>/dev/null; then
    VERSION=$(python -c "import aiofiles; print(aiofiles.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 12: aiofiles async operations
echo -n "  Testing async file operations... "
if python << 'EOF' 2>/dev/null
import asyncio
import aiofiles
import tempfile
import os

async def test_aiofiles():
    temp_file = tempfile.mktemp()

    # Write async
    async with aiofiles.open(temp_file, 'w') as f:
        await f.write("Test content")

    # Read async
    async with aiofiles.open(temp_file, 'r') as f:
        content = await f.read()

    assert content == "Test content"
    os.unlink(temp_file)
    return True

result = asyncio.run(test_aiofiles())
assert result
print("✓ Async file operations working", end="")
EOF
then
    echo ""
else
    echo "✗ Aiofiles test failed"
    exit $FAILURE
fi

echo ""
echo "CLI component tests passed!"
exit $SUCCESS
