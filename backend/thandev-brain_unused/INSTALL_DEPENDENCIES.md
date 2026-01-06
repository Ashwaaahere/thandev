# Installing Dependencies for Brain Service

## Required Dependencies

The brain service requires additional dependencies for database access when indexing findings:

```bash
cd services/thandev-brain
source venv/bin/activate

# Install database dependencies
pip install psycopg2-binary sqlalchemy

# Or install all from requirements.txt
pip install -r requirements.txt
```

## Common Issues

### "No module named 'psycopg2'"

**Solution:**
```bash
pip install psycopg2-binary
```

**Note:** Use `psycopg2-binary` (not `psycopg2` or `pycopg2`) - it's the pre-compiled version that doesn't require PostgreSQL development libraries.

### "No module named 'sqlalchemy'"

**Solution:**
```bash
pip install sqlalchemy
```

## Full Installation

```bash
cd services/thandev-brain
source venv/bin/activate
pip install -r requirements.txt
```

The `requirements.txt` now includes:
- `sqlalchemy==2.0.35` - For database access
- `psycopg2-binary==2.9.9` - PostgreSQL adapter

## Verify Installation

```bash
python -c "import sqlalchemy; import psycopg2; print('✓ Dependencies installed')"
```




