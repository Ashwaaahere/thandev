# Deployment Guide

## Database Migrations on Neon/PostgreSQL

### Automatic Migrations on Fly.io

Migrations run automatically during deployment via the `release_command` in `backend/fly.toml`:

```toml
[deploy]
  release_command = "python fix_alembic_version_column.py && alembic upgrade head"
```

This ensures:
- Migrations run **before** app containers start
- Migrations run on the same database as the application
- The `alembic_version` column is fixed if needed (to support longer revision IDs)

### Manual Migration Check

To verify migrations have run successfully:

```bash
# Check current database version
fly ssh console -a thandev-backend -C "alembic current"

# Check expected head revision
fly ssh console -a thandev-backend -C "alembic heads"
```

### Running Migrations Locally (for Testing)

Before deploying, test migrations against your Neon database:

```bash
cd backend

# Set DATABASE_URL to your Neon connection string
export DATABASE_URL="postgresql://user:pass@host.neon.tech/dbname"

# Run migrations
alembic upgrade head
```

### Troubleshooting Migration Issues

If you see errors like:
- `column scan_jobs.scan_level does not exist`
- `column scan_jobs.stack_info does not exist`

**Solution**: These columns should be added by migration `0022_add_scan_jobs_columns`. 

1. Check if migration ran: `alembic current`
2. If migration hasn't run, run it: `alembic upgrade head`
3. Check logs: Backend startup logs show Alembic version info for debugging

### Migration Safety

All migrations are designed to be:
- **Idempotent**: Safe to run multiple times
- **Non-destructive**: Use `IF NOT EXISTS` checks where possible
- **Backward compatible**: Add nullable columns with safe defaults when needed
