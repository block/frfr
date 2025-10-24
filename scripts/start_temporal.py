#!/usr/bin/env python3
"""
Start Temporal dev server and ensure namespace exists.

This script:
1. Checks if Temporal dev server is already running
2. Starts it if not running
3. Creates the 'frfr' namespace if it doesn't exist
"""

import subprocess
import sys
import time
import socket
from typing import Optional


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def is_temporal_running() -> bool:
    """Check if Temporal dev server is running."""
    # Temporal dev server uses port 7233 by default
    return is_port_in_use(7233)


def start_temporal_dev_server() -> Optional[subprocess.Popen]:
    """Start Temporal dev server in background."""
    print("Starting Temporal dev server...")
    try:
        # Start temporal dev server
        process = subprocess.Popen(
            ["temporal", "server", "start-dev"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for server to be ready
        print("Waiting for Temporal server to start...")
        max_retries = 30
        for i in range(max_retries):
            if is_temporal_running():
                print("Temporal server is ready!")
                return process
            time.sleep(1)
            if i % 5 == 0:
                print(f"  Still waiting... ({i}/{max_retries})")

        print("ERROR: Temporal server failed to start within 30 seconds")
        process.kill()
        return None

    except FileNotFoundError:
        print("ERROR: 'temporal' CLI not found.")
        print("Please install Temporal CLI:")
        print("  brew install temporal  # macOS")
        print("  Or visit: https://docs.temporal.io/cli")
        return None
    except Exception as e:
        print(f"ERROR starting Temporal: {e}")
        return None


def create_namespace(namespace: str = "frfr") -> bool:
    """Create Temporal namespace if it doesn't exist."""
    print(f"Checking namespace '{namespace}'...")

    try:
        # Check if namespace exists
        result = subprocess.run(
            ["temporal", "operator", "namespace", "describe", namespace],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"Namespace '{namespace}' already exists")
            return True

        # Create namespace
        print(f"Creating namespace '{namespace}'...")
        result = subprocess.run(
            [
                "temporal",
                "operator",
                "namespace",
                "create",
                namespace,
                "--description",
                "frfr document Q&A system",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"Successfully created namespace '{namespace}'")
            return True
        else:
            print(f"ERROR creating namespace: {result.stderr}")
            return False

    except Exception as e:
        print(f"ERROR managing namespace: {e}")
        return False


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("frfr - Temporal Setup")
    print("=" * 60)
    print()

    # Check if already running
    if is_temporal_running():
        print("Temporal server is already running on port 7233")
    else:
        # Start server
        process = start_temporal_dev_server()
        if not process:
            return 1

        print()
        print("Temporal dev server started successfully!")
        print("  Web UI: http://localhost:8233")
        print("  gRPC:   localhost:7233")
        print()
        print("Note: Server is running in the background")
        print("      To stop: pkill -f 'temporal server'")

    print()

    # Create namespace
    if not create_namespace("frfr"):
        return 1

    print()
    print("=" * 60)
    print("Setup complete! Temporal is ready for frfr.")
    print("=" * 60)
    print()
    print("You can now run:")
    print("  frfr start-session --docs your-document.pdf")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
