#!/usr/bin/env bash
# Deploy thandev-backend to Fly.io from CLI (no GitHub Actions).
# Usage: from repo root: ./backend/scripts/fly-deploy.sh
#    or: cd backend && flyctl deploy --remote-only --config fly.toml --app thandev-backend

set -e
cd "$(dirname "$0")/.."
echo "Deploying thandev-backend to Fly.io..."
flyctl deploy --remote-only --config fly.toml --app thandev-backend
echo "Done. Check logs: flyctl logs --app thandev-backend"
