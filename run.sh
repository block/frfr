#!/bin/bash

# frfr - Document Fact Extraction
# Usage: ./run.sh [--no-frontend] [--build]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
NO_FRONTEND=false
BUILD_FRONTEND=false
for arg in "$@"; do
    case $arg in
        --no-frontend)
            NO_FRONTEND=true
            ;;
        --build)
            BUILD_FRONTEND=true
            ;;
    esac
done

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  frfr - Document Fact Extraction${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check for required tools
echo -e "${YELLOW}Checking dependencies...${NC}"

if ! command -v go &> /dev/null; then
    echo -e "${RED}Error: Go is not installed${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Go $(go version | awk '{print $3}')"

if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Node.js $(node --version)"

# Check Claude API credentials
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo -e "  ${GREEN}✓${NC} Claude API: using explicit API key"
else
    if command -v claude &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Claude API: using native credentials (claude CLI)"
    else
        echo -e "  ${YELLOW}!${NC} Claude API: claude CLI not found, fact extraction may fail"
        echo -e "    Install with: ${BLUE}npm install -g @anthropic-ai/claude-code${NC}"
        echo -e "    Or set: ${BLUE}export ANTHROPIC_API_KEY=your_key${NC}"
    fi
fi

# Install frontend dependencies if needed
if [ "$NO_FRONTEND" = false ]; then
    cd "$SCRIPT_DIR/frontend"
    if [ ! -d "node_modules" ]; then
        echo -e "\n${YELLOW}Installing frontend dependencies...${NC}"
        npm install --silent
    fi
    echo -e "  ${GREEN}✓${NC} Frontend dependencies ready"
fi

# Build Go backend
echo -e "\n${YELLOW}Building Go backend...${NC}"
cd "$SCRIPT_DIR/backend"
go build -o frfr-server ./cmd/server
echo -e "  ${GREEN}✓${NC} Backend built"

# Start backend
echo -e "\n${YELLOW}Starting backend server...${NC}"
./frfr-server &
BACKEND_PID=$!
sleep 1

# Check if backend started
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Error: Backend failed to start${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Backend running on http://localhost:8080"

# Start frontend
if [ "$NO_FRONTEND" = false ]; then
    echo -e "\n${YELLOW}Starting frontend...${NC}"
    cd "$SCRIPT_DIR/frontend"

    if [ "$BUILD_FRONTEND" = true ]; then
        echo -e "  Building production frontend..."
        npm run build --silent
        echo -e "  ${GREEN}✓${NC} Frontend built to dist/"
        echo -e "\n${GREEN}Backend ready at http://localhost:8080${NC}"
        echo -e "Serve frontend with: ${BLUE}npx serve frontend/dist${NC}"
    else
        npm run dev -- --host &>/dev/null &
        FRONTEND_PID=$!
        sleep 2
        echo -e "  ${GREEN}✓${NC} Frontend running on http://localhost:3000"
    fi
fi

# Print status
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  frfr is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC}  http://localhost:3000"
echo -e "  ${BLUE}API:${NC}       http://localhost:8080/api"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop"
echo ""

# Wait for processes
wait
