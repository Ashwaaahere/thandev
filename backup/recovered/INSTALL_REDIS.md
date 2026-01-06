# Installing and Starting Redis

Redis is required for Celery to work (it's the message broker).

## Option 1: Install Redis via apt (Recommended for WSL/Ubuntu)

```bash
# Install Redis
sudo apt update
sudo apt install -y redis-server

# Start Redis service
sudo systemctl start redis-server

# Enable Redis to start on boot (optional)
sudo systemctl enable redis-server

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

## Option 2: Run Redis via Docker

If you have Docker installed:

```bash
# Start Redis in Docker
docker run -d --name redis -p 6379:6379 redis:latest

# Verify it's running
docker ps | grep redis

# Test connection
docker exec -it redis redis-cli ping
# Should return: PONG
```

## Option 3: Install Redis from Source

If apt doesn't work:

```bash
# Install dependencies
sudo apt install -y build-essential tcl

# Download and compile Redis
cd /tmp
wget http://download.redis.io/redis-stable.tar.gz
tar xzf redis-stable.tar.gz
cd redis-stable
make
sudo make install

# Start Redis manually
redis-server
```

## Verify Redis is Working

```bash
# Test connection
redis-cli ping
# Should return: PONG

# Check Redis info
redis-cli info server | grep redis_version
```

## After Redis is Running

Once Redis is running, start the Celery worker:

```bash
cd /home/ashwath/thandev/backend
source venv/bin/activate
./start_celery.sh
```

Your queued scans will then start processing automatically!

