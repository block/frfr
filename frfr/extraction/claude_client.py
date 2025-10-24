"""
Claude CLI client wrapper for making LLM calls via subprocess.
"""

import json
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Wrapper around Claude CLI for headless LLM calls."""

    def __init__(self, claude_command: str = "claude"):
        """
        Initialize Claude client.

        Args:
            claude_command: Path to claude CLI (default: "claude")
        """
        self.claude_command = claude_command
        self._verify_cli()

    def _verify_cli(self):
        """Verify Claude CLI is available."""
        try:
            result = subprocess.run(
                [self.claude_command, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Claude CLI returned error: {result.stderr}")
            logger.info(f"Claude CLI version: {result.stdout.strip()}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Claude CLI not found at '{self.claude_command}'. "
                "Please install it with: npm install -g @anthropic-ai/claude-cli"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to verify Claude CLI: {e}")

    def prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4000,
        timeout: int = 600,
    ) -> str:
        """
        Send a prompt to Claude and get the response.

        Args:
            prompt: The prompt to send
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            timeout: Timeout in seconds

        Returns:
            Response text from Claude

        Raises:
            RuntimeError: If the CLI call fails
        """
        cmd = [
            self.claude_command,
            "-p",  # Print mode (non-interactive)
            "--output-format",
            "json",
        ]

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        cmd.append(prompt)

        try:
            logger.debug(f"Calling Claude CLI with prompt length: {len(prompt)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise RuntimeError(f"Claude CLI failed: {error_msg}")

            # Parse JSON response
            try:
                response = json.loads(result.stdout)
                if response.get("is_error"):
                    raise RuntimeError(f"Claude returned error: {response.get('result')}")

                # Extract the result text
                result_text = response.get("result", "")

                # Log usage stats
                usage = response.get("usage", {})
                cost = response.get("total_cost_usd", 0)
                logger.info(
                    f"Claude response: {usage.get('input_tokens', 0)} input tokens, "
                    f"{usage.get('output_tokens', 0)} output tokens, "
                    f"${cost:.4f} cost"
                )

                return result_text

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Claude response as JSON: {e}")
                logger.error(f"Response: {result.stdout[:500]}")
                raise RuntimeError(f"Invalid JSON response from Claude: {e}")

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Claude CLI call failed: {e}")
            raise


def test_claude_client():
    """Test the Claude client."""
    client = ClaudeClient()
    result = client.prompt("What is 2+2? Respond with just the number.")
    print(f"Result: {result}")
    assert "4" in result, f"Expected '4', got: {result}"
    print("✓ Claude client working!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_claude_client()
