#!/bin/bash
set -e

# Development script for running frfr in Electron
# Builds Go backend, starts Vite dev server, launches Electron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== frfr Electron Development Mode ==="

# Build Go backend
echo ""
echo "Building Go backend..."
cd backend
go build -o frfr-server ./cmd/server
cd ..
echo "Backend built: backend/frfr-server"

# Install Electron dependencies if needed
echo ""
echo "Checking Electron dependencies..."
cd electron
if [ ! -d "node_modules" ]; then
    echo "Installing Electron dependencies..."
    npm install
fi

# Build Electron TypeScript
echo ""
echo "Building Electron TypeScript..."
npm run build
cd ..

# Start Vite dev server in background
echo ""
echo "Starting Vite dev server..."
cd frontend
npm run dev &
VITE_PID=$!
cd ..

# Wait for Vite to be ready
echo "Waiting for Vite dev server..."
sleep 3

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    if [ -n "$VITE_PID" ]; then
        kill $VITE_PID 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Electron
echo ""
echo "Starting Electron..."
cd electron
npm run dev

# Cleanup when Electron exits
cleanup
