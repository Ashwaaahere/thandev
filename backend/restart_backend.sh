#!/bin/bash
# Script to restart the FastAPI backend with proper CORS configuration

echo "Stopping any existing uvicorn processes on port 8000..."
pkill -f "uvicorn.*8000" || true
sleep 2

echo "Starting FastAPI backend on http://localhost:8000..."
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
