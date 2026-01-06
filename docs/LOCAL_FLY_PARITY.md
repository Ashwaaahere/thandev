# Local Fly-Parity Runbook

This repo is restored from Fly backups into:
- `backend/`
- `services/thandev-brain/`
- `services/thandev-runner/`

## Environment files
- Copy `env-examples/fly-local.env.example` to `.env.fly.local` (gitignored) and adjust values (secrets/tokens).
- Key defaults (docker compose network):
  - `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/thandev`
  - `REDIS_URL=redis://redis:6379/0`
  - `BACKEND_URL=http://backend:8000`
  - `CORE_BACKEND_URL=http://backend:8000`
  - `BRAIN_SERVICE_URL=http://thandev-brain:8001`
  - `RUNNER_API_TOKEN=dev-runner-token` (keep same in backend/runner)

## Compose
- File: `docker-compose.fly-local.yml`
- Services: postgres, redis, qdrant, backend, thandev-brain, thandev-runner.
- All share the default compose network; service DNS names match service keys.

## Scripts
- `scripts/reset_local_db.sh`  
  Stops stack, recreates infra, runs `alembic upgrade head` inside backend container.
- `scripts/up_fly_local.sh`  
  `docker compose -f docker-compose.fly-local.yml --env-file .env.fly.local up --build`
- `scripts/health_check.sh`  
  Hits backend `/health`, brain `/health` (fallback `/`), redis ping.

## Startup (fresh)
1) `./scripts/reset_local_db.sh`
2) `./scripts/up_fly_local.sh`
3) `./scripts/health_check.sh`

## Notes
- No real secrets are committed. Place real values only in `.env.fly.local`.
- Backend entrypoint: `./entrypoint.sh` (runs uvicorn; release-style migrations run via script above).
- Brain entrypoint: `./start_brain.sh`
- Runner entrypoint: `./start_runner.sh`
- If you prefer host Postgres instead of compose: set `DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/thandev` and ensure `extra_hosts` is present (already configured).


