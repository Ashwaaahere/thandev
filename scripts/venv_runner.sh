#!/bin/bash
# Venv wrapper for runner service
# Usage: scripts/venv_runner.sh <command>
# Example: scripts/venv_runner.sh "python -m app.main"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNNER_DIR="$REPO_ROOT/services/thandev-runner"
VENV_DIR="$RUNNER_DIR/venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating runner virtual environment..."
    cd "$RUNNER_DIR"
    python3 -m venv venv
fi

# Activate venv and run command
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies if requirements.txt is newer than venv
if [ "$RUNNER_DIR/requirements.txt" -nt "$VENV_DIR/.installed" ] || [ ! -f "$VENV_DIR/.installed" ]; then
    echo "Installing/updating runner dependencies..."
    pip install --upgrade pip
    pip install -r "$RUNNER_DIR/requirements.txt"
    touch "$VENV_DIR/.installed"
fi

# Run the command
cd "$RUNNER_DIR"
# Use eval to properly handle quoted arguments
eval "$@"

