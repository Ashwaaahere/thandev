.PHONY: help infra-up infra-down backend runner brain dev migrate test bootstrap doctor clean

# Default target
help:
	@echo "Thandev Development Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make infra-up      - Start Postgres and Redis (docker compose)"
	@echo "  make infra-down    - Stop Postgres and Redis"
	@echo "  make backend       - Start backend API (uvicorn)"
	@echo "  make runner        - Start runner service"
	@echo "  make brain         - Start brain service (optional)"
	@echo "  make dev           - Start infra + backend + runner (brain optional via BRAIN_ENABLED=1)"
	@echo "  make migrate       - Run database migrations (alembic upgrade head)"
	@echo "  make test          - Run backend tests (non-integration)"
	@echo "  make bootstrap     - Bootstrap dev environment (create tenant/user/project)"
	@echo "  make doctor        - Check system health (python paths, imports, DB URLs)"
	@echo "  make clean         - Clean venv directories (use with caution)"

# Start infrastructure (Postgres + Redis)
infra-up:
	@echo "Starting infrastructure (Postgres + Redis)..."
	docker-compose up -d postgres redis
	@echo "Waiting for services to be healthy..."
	@sleep 5
	@echo "Infrastructure ready!"

# Stop infrastructure
infra-down:
	@echo "Stopping infrastructure..."
	docker-compose down

# Start backend API
backend:
	@echo "Starting backend API..."
	@scripts/venv_backend.sh "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

# Start runner service
runner:
	@echo "Starting runner service..."
	@scripts/venv_runner.sh "python -m app.main"

# Start brain service
brain:
	@echo "Starting brain service..."
	@scripts/venv_brain.sh "python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload"

# Start full dev environment
dev: infra-up
	@echo "Starting development environment..."
	@echo "Running migrations..."
	@$(MAKE) migrate
	@echo ""
	@echo "Backend: http://localhost:8000"
	@echo "Runner: running in background"
	@echo ""
	@if [ "$(BRAIN_ENABLED)" = "1" ]; then \
		echo "Brain: http://localhost:8001"; \
		$(MAKE) -j3 backend runner brain; \
	else \
		$(MAKE) -j2 backend runner; \
	fi

# Run database migrations
migrate:
	@echo "Running database migrations..."
	@scripts/venv_backend.sh "python -m alembic upgrade head"
	@echo "Migrations complete!"

# Run tests
test:
	@echo "Running backend tests (non-integration)..."
	@scripts/venv_backend.sh 'pytest -m "not integration" -v'

# Bootstrap dev environment
bootstrap:
	@echo "Bootstrapping dev environment..."
	@scripts/bootstrap_dev.sh

# System health check
doctor:
	@echo "Running system health check..."
	@scripts/venv_backend.sh python3 $(shell pwd)/scripts/doctor.py

# Clean venv directories (use with caution)
clean:
	@echo "Cleaning virtual environments..."
	@read -p "This will delete all venv directories. Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf backend/venv services/thandev-runner/venv services/thandev-brain/venv; \
		echo "Virtual environments cleaned!"; \
	else \
		echo "Cancelled."; \
	fi

