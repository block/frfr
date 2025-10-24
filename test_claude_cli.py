#!/usr/bin/env python3
"""Quick test of ClaudeClient wrapper."""

import sys
import os

# Add frfr to path
sys.path.insert(0, os.path.dirname(__file__))

from frfr.extraction.claude_client import ClaudeClient

def test_claude_client():
    """Test that Claude CLI works."""
    print("Testing Claude CLI wrapper...")

    try:
        client = ClaudeClient()
        print("✓ Claude CLI found and verified")

        # Test a simple prompt
        print("\nTesting simple prompt...")
        result = client.prompt("What is 2+2? Respond with just the number.", max_tokens=50)
        print(f"Response: {result}")

        if "4" in result:
            print("✓ Claude CLI responding correctly!")
            return True
        else:
            print(f"✗ Unexpected response: {result}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_claude_client()
    sys.exit(0 if success else 1)
