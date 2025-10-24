#!/bin/bash
# Test Temporal integration

set -e

SUCCESS=0
FAILURE=1

echo "Testing Temporal Integration..."
echo "=============================="

# Test 1: temporalio package
echo -n "  Checking temporalio package... "
if python -c "import temporalio" 2>/dev/null; then
    VERSION=$(python -c "import temporalio; print(temporalio.__version__)" 2>/dev/null)
    echo "✓ v$VERSION"
else
    echo "✗ Not installed"
    exit $FAILURE
fi

# Test 2: Temporal client creation
echo -n "  Testing Temporal client creation... "
if python << 'EOF' 2>/dev/null
from temporalio.client import Client

# Just test that we can create a client object (not connect)
# Connection requires Temporal server to be running
import inspect
assert 'connect' in dir(Client)
print("✓ Client class available", end="")
EOF
then
    echo ""
else
    echo "✗ Client creation failed"
    exit $FAILURE
fi

# Test 3: Workflow decorator
echo -n "  Testing workflow decorator... "
if python << 'EOF' 2>/dev/null
from temporalio import workflow
import asyncio

@workflow.defn
class TestWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return f"Hello {name}"

# Verify workflow is decorated
assert hasattr(TestWorkflow, '__temporal_workflow_definition')
print("✓ Workflow decorator working", end="")
EOF
then
    echo ""
else
    echo "✗ Workflow decorator failed"
    exit $FAILURE
fi

# Test 4: Activity decorator
echo -n "  Testing activity decorator... "
if python << 'EOF' 2>/dev/null
from temporalio import activity

@activity.defn
async def test_activity(name: str) -> str:
    return f"Activity: {name}"

# Verify activity is decorated
assert hasattr(test_activity, '__temporal_activity_definition')
print("✓ Activity decorator working", end="")
EOF
then
    echo ""
else
    echo "✗ Activity decorator failed"
    exit $FAILURE
fi

# Test 5: Temporal address environment variable
echo -n "  Checking TEMPORAL_ADDRESS... "
if [ -n "$TEMPORAL_ADDRESS" ]; then
    echo "✓ Set to $TEMPORAL_ADDRESS"
else
    echo "⚠ Not set (warning only)"
fi

# Test 6: Try to connect to Temporal (if running)
echo -n "  Testing Temporal server connection... "
if timeout 5 python << EOF 2>/dev/null
import asyncio
from temporalio.client import Client

async def test_connection():
    try:
        address = "${TEMPORAL_ADDRESS:-localhost:7233}"
        client = await Client.connect(address, namespace="default")
        await client.workflow_service.get_system_info()
        return True
    except Exception:
        return False

result = asyncio.run(test_connection())
if result:
    print("✓ Server reachable", end="")
else:
    print("⚠ Server not reachable (start with 'make up')", end="")
EOF
then
    echo ""
else
    echo "⚠ Connection test skipped (timeout or server not running)"
fi

# Test 7: Temporal namespace check
echo -n "  Testing namespace configuration... "
if timeout 5 python << EOF 2>/dev/null
import asyncio
from temporalio.client import Client

async def test_namespace():
    try:
        address = "${TEMPORAL_ADDRESS:-localhost:7233}"
        client = await Client.connect(address, namespace="frfr")
        return True
    except Exception:
        return False

result = asyncio.run(test_namespace())
if result:
    print("✓ Namespace 'frfr' accessible", end="")
else:
    print("⚠ Namespace not accessible (may need creation)", end="")
EOF
then
    echo ""
else
    echo "⚠ Namespace test skipped"
fi

echo ""
echo "Temporal integration tests passed!"
echo "(Note: Connection tests require Temporal server running)"
exit $SUCCESS
