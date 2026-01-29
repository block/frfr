#!/bin/bash
set -e

# Production build script for frfr Electron app
# Builds Go backend for both architectures, frontend, and packages with electron-builder

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "=== frfr Electron Production Build ==="

# Parse arguments
BUILD_ARCH="both"  # arm64, x64, or both
while [[ $# -gt 0 ]]; do
    case $1 in
        --arch)
            BUILD_ARCH="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create resources directories
echo ""
echo "Creating resource directories..."
mkdir -p electron/resources/bin/arm64
mkdir -p electron/resources/bin/x64

# Build Go backend for target architectures
echo ""
echo "Building Go backend..."
cd backend

if [ "$BUILD_ARCH" = "arm64" ] || [ "$BUILD_ARCH" = "both" ]; then
    echo "  Building for arm64..."
    GOOS=darwin GOARCH=arm64 go build -o ../electron/resources/bin/arm64/frfr-server ./cmd/server
    echo "  arm64 binary built"
fi

if [ "$BUILD_ARCH" = "x64" ] || [ "$BUILD_ARCH" = "both" ]; then
    echo "  Building for x64..."
    GOOS=darwin GOARCH=amd64 go build -o ../electron/resources/bin/x64/frfr-server ./cmd/server
    echo "  x64 binary built"
fi

cd ..

# Build frontend
echo ""
echo "Building frontend..."
cd frontend
npm run build
cd ..
echo "Frontend built: frontend/dist/"

# Install Electron dependencies
echo ""
echo "Installing Electron dependencies..."
cd electron
npm install

# Build Electron TypeScript
echo ""
echo "Building Electron TypeScript..."
npm run build

# Package with electron-builder
echo ""
echo "Packaging Electron app..."
if [ "$BUILD_ARCH" = "arm64" ]; then
    npm run dist -- --mac --arm64
elif [ "$BUILD_ARCH" = "x64" ]; then
    npm run dist -- --mac --x64
else
    # Build universal (both architectures)
    npm run dist:mac
fi

cd ..

echo ""
echo "=== Build Complete ==="
echo "Output: electron/release/"
ls -la electron/release/
