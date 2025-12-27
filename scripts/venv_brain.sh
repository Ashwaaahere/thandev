#!/bin/bash
# Venv wrapper for brain service
# Usage: scripts/venv_brain.sh <command>
# Example: scripts/venv_brain.sh "python -m uvicorn app.main:app --reload --port 8001"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BRAIN_DIR="$REPO_ROOT/services/thandev-brain"
VENV_DIR="$BRAIN_DIR/venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating brain virtual environment..."
    cd "$BRAIN_DIR"
    python3 -m venv venv
fi

# Activate venv and run command
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies if requirements.txt is newer than venv
if [ "$BRAIN_DIR/requirements.txt" -nt "$VENV_DIR/.installed" ] || [ ! -f "$VENV_DIR/.installed" ]; then
    echo "Installing/updating brain dependencies..."
    pip install --upgrade pip
    pip install -r "$BRAIN_DIR/requirements.txt"
    touch "$VENV_DIR/.installed"
fi

# Run the command
cd "$BRAIN_DIR"
# Use eval to properly handle quoted arguments
eval "$@"

