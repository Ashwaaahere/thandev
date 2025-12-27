# Quick Start Guide

## Important: Run Commands from Repo Root

All `make` commands must be run from the **repo root directory** (`/home/ashwath/thandev`), not from subdirectories.

```bash
# ✅ Correct: From repo root
cd /home/ashwath/thandev
make doctor
make dev

# ❌ Wrong: From subdirectory
cd services/backend
make doctor  # This will fail!
```

## Quick Start Commands

```bash
# 1. Navigate to repo root
cd /home/ashwath/thandev

# 2. Check system health
make doctor

# 3. Start development environment (includes migrations)
make dev

# 4. In another terminal, bootstrap dev environment
cd /home/ashwath/thandev
make bootstrap

# 5. Run tests
cd /home/ashwath/thandev
make test
```

## Available Make Targets

Run `make help` or `make` from the repo root to see all available targets:

- `make infra-up` - Start Postgres and Redis
- `make backend` - Start backend API
- `make runner` - Start runner service
- `make brain` - Start brain service (optional)
- `make dev` - Start full dev environment (infra + backend + runner)
- `make migrate` - Run database migrations
- `make test` - Run backend tests
- `make bootstrap` - Bootstrap dev environment
- `make doctor` - System health check

## Troubleshooting

If you get "No rule to make target", ensure you're in the repo root:

```bash
pwd  # Should show: /home/ashwath/thandev
ls Makefile  # Should show the Makefile
```
