#!/bin/bash
# Test suite for Docker components
# This script orchestrates all component tests

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Function to print section headers
print_section() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to print test results
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((TESTS_FAILED++))
        FAILED_TESTS+=("$2")
    fi
}

# Function to run a test script
run_test() {
    local test_name=$1
    local test_script=$2

    echo -e "${YELLOW}Running: $test_name${NC}"

    if bash "$test_script"; then
        print_result 0 "$test_name"
    else
        print_result 1 "$test_name"
    fi
    echo ""
}

# Main test execution
print_section "Frfr Docker Component Test Suite"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run all component tests
run_test "System Dependencies" "$SCRIPT_DIR/test_system_deps.sh"
run_test "Python Environment" "$SCRIPT_DIR/test_python_env.sh"
run_test "Document Processing" "$SCRIPT_DIR/test_document_processing.sh"
run_test "ML/Embeddings" "$SCRIPT_DIR/test_ml_components.sh"
run_test "Temporal Integration" "$SCRIPT_DIR/test_temporal.sh"
run_test "CLI Framework" "$SCRIPT_DIR/test_cli_components.sh"

# Print summary
print_section "Test Summary"
echo -e "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "\n${RED}Failed Tests:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  - $test"
    done
    exit 1
else
    echo -e "\n${GREEN}All tests passed!${NC}"
    exit 0
fi
