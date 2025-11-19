# Frfr Executable

This directory contains the main `frfr` shell script that serves as the entry point for the Frfr application.

## Usage

### From the project directory:
```bash
./bin/frfr          # Launch TUI (default)
./bin/frfr tui      # Explicitly launch TUI
./bin/frfr --help   # Show help
./bin/frfr process <pdf>  # Process a PDF
```

### Add to PATH (optional):
To use `frfr` from anywhere, add this directory to your PATH:

```bash
# Add to your ~/.bashrc or ~/.zshrc
export PATH="/Users/nesposito/Development/frfr/bin:$PATH"

# Then reload your shell or run:
source ~/.bashrc  # or ~/.zshrc
```

After adding to PATH, you can simply run:
```bash
frfr              # Launch from anywhere
```

## How it works

The `frfr` script:
1. Automatically locates the project root directory
2. Sources the virtual environment (`venv/`)
3. Launches the frfr CLI with any provided arguments
4. Defaults to TUI mode when no command is specified

## Requirements

- Virtual environment must exist at `<project_root>/venv/`
- Dependencies must be installed: `pip install -e .`
