#!/bin/bash
# Quick verification script for Fly.io deployment
# Usage: bash QUICK_VERIFY.sh

echo "=== Checking Both Time Columns Exist ==="
fly ssh console -a thandev-backend -C "sh -c 'cd /app && python3 << \"EOF\"
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ[\"DATABASE_URL\"])
with engine.connect() as conn:
    result = conn.execute(text(\"\"\"
        SELECT column_name 
        FROM information_schema.columns
        WHERE table_schema = '\''public'\'' AND table_name = '\''scan_jobs'\''
        AND column_name IN ('\''finished_at'\'', '\''completed_at'\'')
        ORDER BY column_name
    \"\"\"))
    columns = [row[0] for row in result.fetchall()]
    print('\''Time columns in scan_jobs:'\'')
    for col in columns:
        print(f'\''  ✓ {col}'\'')
    if '\''finished_at'\'' not in columns:
        print('\''  ✗ finished_at missing!'\'')
    if '\''completed_at'\'' not in columns:
        print('\''  ✗ completed_at missing!'\'')
    if len(columns) == 2:
        print('\''\n✓ Both columns exist'\'')
EOF
'"

echo ""
echo "=== Checking Alembic Version ==="
fly ssh console -a thandev-backend -C "sh -c 'cd /app && alembic current'"

echo ""
echo "=== Checking All scan_jobs Columns ==="
fly ssh console -a thandev-backend -C "sh -c 'cd /app && python3 << \"EOF\"
import os
from sqlalchemy import create_engine, text
engine = create_engine(os.environ[\"DATABASE_URL\"])
with engine.connect() as conn:
    result = conn.execute(text(\"\"\"
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = '\''public'\'' AND table_name = '\''scan_jobs'\''
        ORDER BY ordinal_position
    \"\"\"))
    columns = result.fetchall()
    print('\''scan_jobs columns:'\'')
    for col in columns:
        print(f'\''  - {col[0]}: {col[1]}'\'')
    col_names = {col[0] for col in columns}
    required = ['\''id'\'', '\''project_id'\'', '\''scan_level'\'', '\''status'\'', '\''finished_at'\'', '\''completed_at'\'']
    missing = [col for col in required if col not in col_names]
    if missing:
        print(f'\''\n✗ Missing required columns: {missing}'\'')
    else:
        print('\''\n✓ All required columns present'\'')
EOF
'"

