# Docker Permissions Fix

## Problem

When running Docker commands, you see:
```
permission denied while trying to connect to the Docker daemon socket
```

## Solutions

### Option 1: Use sudo (Quick Fix)

Run Docker commands with `sudo`:

```bash
# Start Redis
sudo docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine

# Start Qdrant
sudo docker run -d --name thandev-qdrant -p 6333:6333 qdrant/qdrant:latest

# Or use the helper script
./start_services_with_sudo.sh
```

### Option 2: Add User to Docker Group (Recommended)

Add your user to the docker group so you don't need sudo:

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Logout and login again (or run: newgrp docker)
newgrp docker

# Verify
docker ps
```

**Note:** After adding to docker group, you need to logout/login or run `newgrp docker` for changes to take effect.

### Option 3: Install Redis Locally (No Docker)

If you prefer not to use Docker for Redis:

```bash
# Install Redis
sudo apt update
sudo apt install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Verify
redis-cli ping
# Should return: PONG
```

**Note:** Qdrant still requires Docker (no easy local installation).

### Option 4: Use Docker Compose with sudo

```bash
sudo docker-compose up -d redis qdrant
```

## Quick Start Commands

### With sudo:
```bash
cd /home/shree/ashwath/thandev
./start_services_with_sudo.sh
```

### After adding to docker group:
```bash
cd /home/shree/ashwath/thandev
./start_redis_qdrant.sh
```

## Verification

After starting services:

```bash
# Check Redis
redis-cli ping
# Should return: PONG

# Check Qdrant
curl http://localhost:6333/health
# Should return JSON
```

## Next Steps

Once Redis and Qdrant are running:

1. **Start Celery Worker:**
   ```bash
   cd backend
   source .venv/bin/activate
   ./start_celery.sh
   ```

2. **Start Brain Service:**
   ```bash
   cd services/thandev-brain
   source venv/bin/activate
   ./start_brain.sh
   ```



