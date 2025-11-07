"""Path input widget with autocomplete."""

from pathlib import Path
from typing import List
import os
from glob import glob

from textual.widgets import Input
from textual.events import Key


class PathInput(Input):
    """Input widget with path autocomplete on Tab."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completions: List[str] = []
        self.completion_index = 0

    def on_key(self, event: Key) -> None:
        """Handle key events for autocomplete."""
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self._complete_path()

    def _complete_path(self) -> None:
        """Complete the current path."""
        current = self.value.strip()

        if not current:
            # If empty, show current directory
            self.value = "./"
            return

        # Expand user home directory
        if current.startswith("~"):
            current = os.path.expanduser(current)

        # Get the directory and partial filename
        if current.endswith("/"):
            directory = current
            partial = ""
        else:
            directory = os.path.dirname(current) or "."
            partial = os.path.basename(current)

        # Find matching files/directories
        try:
            if os.path.isdir(directory):
                items = os.listdir(directory)
                matches = [
                    item for item in items
                    if item.startswith(partial)
                ]

                if len(matches) == 1:
                    # Single match - complete it
                    match = matches[0]
                    full_path = os.path.join(directory, match)

                    if os.path.isdir(full_path):
                        self.value = full_path + "/"
                    else:
                        self.value = full_path

                    # Move cursor to end
                    self.cursor_position = len(self.value)

                elif len(matches) > 1:
                    # Multiple matches - complete common prefix
                    common_prefix = os.path.commonprefix(matches)
                    if len(common_prefix) > len(partial):
                        full_path = os.path.join(directory, common_prefix)
                        self.value = full_path
                        self.cursor_position = len(self.value)
                    else:
                        # Show first match as a hint
                        if self.completions != matches:
                            self.completions = matches
                            self.completion_index = 0

                        # Cycle through matches on repeated Tab
                        match = matches[self.completion_index % len(matches)]
                        full_path = os.path.join(directory, match)
                        if os.path.isdir(full_path):
                            self.value = full_path + "/"
                        else:
                            self.value = full_path
                        self.cursor_position = len(self.value)
                        self.completion_index += 1
        except (OSError, PermissionError):
            # Ignore errors accessing directories
            pass
