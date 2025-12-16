# Services Setup Guide

## Required Services

Thandev requires the following services to run:

1. **Redis** (port 6379) - For Celery task queue
2. **Qdrant** (port 6333) - For RAG vector storage (brain service)

## Quick Start

### Option 1: Using Docker (Recommended)

```bash
# Start Docker if not running
sudo systemctl start docker  # or start Docker Desktop

# Start Redis and Qdrant
cd /home/shree/ashwath/thandev
./start_redis_qdrant.sh
```

### Option 2: Manual Docker Commands

```bash
# Start Redis
docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine

# Start Qdrant
docker run -d --name thandev-qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest
```

### Option 3: Using docker-compose

```bash
cd /home/shree/ashwath/thandev
docker-compose up -d redis qdrant
```

### Option 4: System Services (Redis only)

```bash
# Install Redis
sudo apt install redis-server

# Start Redis
sudo systemctl start redis
# or
sudo systemctl start redis-server

# Enable on boot
sudo systemctl enable redis
```

**Note:** Qdrant requires Docker and cannot be installed as a system service easily.

## Verification

### Check Redis
```bash
redis-cli ping
# Should return: PONG
```

### Check Qdrant
```bash
curl http://localhost:6333/health
# Should return JSON with status
```

### Check Both
```bash
cd /home/shree/ashwath/thandev
./start_redis_qdrant.sh
```

## Troubleshooting

### Redis Connection Refused

**Problem:** `Error 111 connecting to localhost:6379. Connection refused`

**Solutions:**
1. Start Redis: `./start_redis_qdrant.sh`
2. Check if Redis is running: `redis-cli ping`
3. Check if port is in use: `sudo lsof -i :6379`
4. Start with Docker: `docker run -d -p 6379:6379 redis:7-alpine`

### Qdrant Connection Refused

**Problem:** `[Errno 111] Connection refused` when brain service starts

**Solutions:**
1. Start Qdrant: `./start_redis_qdrant.sh`
2. Check if Qdrant is running: `curl http://localhost:6333/health`
3. Start with Docker: `docker run -d -p 6333:6333 qdrant/qdrant:latest`
4. Check Docker: `docker ps | grep qdrant`

### Docker Not Running

**Problem:** `Cannot connect to the Docker daemon`

**Solutions:**
1. Start Docker: `sudo systemctl start docker`
2. Add user to docker group: `sudo usermod -aG docker $USER` (then logout/login)
3. Start Docker Desktop (if on Windows/Mac)

## Service URLs

- **Redis**: `redis://localhost:6379/0`
- **Qdrant**: `http://localhost:6333`

## Stopping Services

### Docker
```bash
# Stop Redis
docker stop thandev-redis

# Stop Qdrant
docker stop thandev-qdrant

# Or stop both
docker stop thandev-redis thandev-qdrant
```

### docker-compose
```bash
docker-compose stop redis qdrant
```

### System Service
```bash
sudo systemctl stop redis
```

## Next Steps

After starting Redis and Qdrant:

1. **Start Brain Service:**
   ```bash
   cd services/thandev-brain
   source venv/bin/activate
   ./start_brain.sh
   ```

2. **Start Celery Worker:**
   ```bash
   cd backend
   source .venv/bin/activate
   ./start_celery.sh
   ```

3. **Start Core Backend:**
   ```bash
   cd backend
   source .venv/bin/activate
   ./restart_backend.sh
   ```



