"""System-level file picker using native macOS Finder."""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional


async def open_file_picker(
    title: str = "Select PDF Files",
    file_types: Optional[list[tuple[str, str]]] = None,
    multiple: bool = True,
    initial_dir: Optional[str] = None
) -> list[str]:
    """
    Open native macOS Finder file picker dialog.

    Args:
        title: Dialog window title
        file_types: List of (description, pattern) tuples (e.g., [("PDF files", "*.pdf")])
        multiple: Allow selecting multiple files
        initial_dir: Starting directory for the dialog

    Returns:
        List of selected file paths (empty if cancelled)
    """
    if initial_dir is None:
        initial_dir = str(Path.home())

    # Run dialog in executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _show_native_finder_dialog,
        title,
        multiple,
        initial_dir
    )
    return result


def _show_native_finder_dialog(title: str, multiple: bool, initial_dir: str) -> list[str]:
    """
    Show native macOS Finder file picker using AppleScript.

    This launches the actual Finder file picker via osascript.
    """
    try:
        # Build AppleScript to show native file picker
        # Use "choose file" which shows the standard macOS file dialog
        # Accept PDF, TXT, and Markdown files
        if multiple:
            script = f'''
set theFiles to choose file with prompt "{title}" of type {{"pdf", "txt", "md", "markdown"}} default location (POSIX file "{initial_dir}") with multiple selections allowed

set thePaths to {{}}
repeat with aFile in theFiles
    set end of thePaths to POSIX path of aFile
end repeat

set AppleScript's text item delimiters to linefeed
set pathList to thePaths as text
return pathList
'''
        else:
            script = f'''
set theFile to choose file with prompt "{title}" of type {{"pdf", "txt", "md", "markdown"}} default location (POSIX file "{initial_dir}")
return POSIX path of theFile
'''

        # Execute AppleScript
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0 and result.stdout.strip():
            # Parse the output - paths are separated by newlines
            output = result.stdout.strip()
            if multiple:
                # Split by newline and clean up paths
                paths = [p.strip() for p in output.split("\n")]
                return [p for p in paths if p]
            else:
                return [output] if output else []

        # User cancelled or error (returncode 128 is user cancelled in osascript)
        return []

    except subprocess.TimeoutExpired:
        print("File picker dialog timed out")
        return []
    except Exception as e:
        print(f"Error showing file picker: {e}")
        import traceback
        traceback.print_exc()
        return []
