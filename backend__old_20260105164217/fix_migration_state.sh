#!/bin/bash
# Fix Alembic migration state when tables already exist

set -e

echo "Fixing Alembic migration state..."

# Check if we're in the backend directory
if [ ! -f "alembic.ini" ]; then
    echo "Error: alembic.ini not found. Make sure you're in the backend directory."
    exit 1
fi

# Check current migration state
echo "Current migration state:"
alembic current

echo ""
echo "If tables already exist, we need to stamp the database to match."
echo "This tells Alembic that migrations have already been applied."
echo ""

# Get the latest revision
LATEST_REVISION=$(alembic heads | head -1 | awk '{print $1}')

if [ -z "$LATEST_REVISION" ]; then
    echo "Error: Could not determine latest revision"
    exit 1
fi

echo "Latest revision: $LATEST_REVISION"
echo ""
read -p "Stamp database to this revision? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Stamping database to revision: $LATEST_REVISION"
    alembic stamp $LATEST_REVISION
    echo "✅ Database stamped successfully!"
    echo ""
    echo "Now you can run migrations normally:"
    echo "  alembic upgrade head"
else
    echo "Cancelled."
fi




