#!/bin/bash
# Run database migrations for Thandev backend

set -e

echo "Running database migrations..."

# Check if we're in the backend directory
if [ ! -f "alembic.ini" ]; then
    echo "Error: alembic.ini not found. Make sure you're in the backend directory."
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not detected."
    echo "Activate it with: source .venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Run migrations
echo "Running: alembic upgrade head"
alembic upgrade head

echo ""
echo "✅ Migrations completed successfully!"
echo ""
echo "You can now run the indexing script:"
echo "  cd ../services/thandev-brain"
echo "  source venv/bin/activate"
echo "  python scripts/index_findings.py --limit 1000"




