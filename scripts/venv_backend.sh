#!/bin/bash
# Venv wrapper for backend service
# Usage: scripts/venv_backend.sh <command>
# Example: scripts/venv_backend.sh "python -m uvicorn app.main:app --reload"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
VENV_DIR="$BACKEND_DIR/venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating backend virtual environment..."
    cd "$BACKEND_DIR"
    python3 -m venv venv
fi

# Activate venv and run command
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies if requirements.txt is newer than venv
if [ "$BACKEND_DIR/requirements.txt" -nt "$VENV_DIR/.installed" ] || [ ! -f "$VENV_DIR/.installed" ]; then
    echo "Installing/updating backend dependencies..."
    pip install --upgrade pip
    pip install -r "$BACKEND_DIR/requirements.txt"
    touch "$VENV_DIR/.installed"
fi

# Run the command
cd "$BACKEND_DIR"
# Use eval to properly handle quoted arguments
eval "$@"

