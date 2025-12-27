# Snap Docker Setup Guide

## Current Status
✅ Docker snap is installed (version 28.4.0)
❌ Docker daemon is not running
❌ Permissions need to be configured

## Setup Steps

### Step 1: Start Docker Service
```bash
sudo snap start docker
```

### Step 2: Enable Docker on Boot
```bash
sudo snap enable docker
```

### Step 3: Verify Docker is Running
```bash
docker ps
```

If you get permission errors, try:
```bash
sudo docker ps
```

### Step 4: Set Up Permissions (Optional - to avoid sudo)

Snap Docker works differently than apt Docker. You have two options:

**Option A: Use sudo for Docker commands**
- Just use `sudo docker` for all commands
- Update your scripts to use `sudo docker` instead of `docker`

**Option B: Create docker group (for snap Docker)**
```bash
# Create docker group
sudo groupadd docker

# Add your user to the group
sudo usermod -aG docker ashwath

# Apply group changes
newgrp docker

# Test
docker ps
```

**Option C: Use snap's built-in permissions**
```bash
# Connect docker to home interface (if needed)
sudo snap connect docker:home

# Check current connections
snap connections docker
```

## Verify Installation

After starting Docker, verify it works:

```bash
# Check Docker version
docker --version

# List running containers
docker ps

# Test with a simple container
docker run hello-world
```

## Starting Your Services

Once Docker is running, you can start Redis and Qdrant:

```bash
cd /home/ashwath/thandev

# If using sudo (recommended for snap Docker)
sudo docker run -d --name thandev-redis -p 6379:6379 redis:7-alpine
sudo docker run -d --name thandev-qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant:latest

# Or use the start script with sudo
./start_services_with_sudo.sh
```

## Troubleshooting

### Docker daemon not running
```bash
# Check snap service status
snap services docker

# Start it
sudo snap start docker

# Check logs
sudo snap logs docker
```

### Permission denied errors
- Use `sudo docker` for commands
- Or follow Option B above to set up the docker group

### Socket connection errors
```bash
# Check if socket exists
ls -la /var/run/docker.sock

# If it doesn't exist, Docker snap may need to be restarted
sudo snap restart docker
```

## Important Notes

- Snap Docker uses a different permission model than apt Docker
- You may need to use `sudo` for Docker commands
- The docker group approach works but may require additional configuration
- For production, consider using apt Docker instead of snap Docker

