# Docker Installation Guide for Thandev

## Current Status
- ❌ Docker is not installed
- ❌ User is not in docker group

## Installation Steps

### Step 1: Install Docker

**Option A: Using Snap (Recommended for WSL2/Ubuntu)**
```bash
sudo snap install docker
```

**Option B: Using apt (Traditional method)**
```bash
sudo apt update
sudo apt install docker.io
```

### Step 2: Start Docker Service
```bash
sudo systemctl start docker
sudo systemctl enable docker  # Enable on boot
```

### Step 3: Add User to Docker Group
```bash
sudo usermod -aG docker ashwath
```

### Step 4: Apply Group Changes
You need to logout and login again, OR run:
```bash
newgrp docker
```

### Step 5: Verify Installation
```bash
docker --version
docker ps
```

## After Installation

Once Docker is installed, you can start the services:

```bash
cd /home/ashwath/thandev
./start_services_with_sudo.sh
```

Or if you're in the docker group (after logout/login):
```bash
./start_services.sh  # (if this script exists)
```

## Troubleshooting

### If Docker service won't start:
```bash
sudo systemctl status docker
sudo journalctl -u docker
```

### If permission denied errors:
- Make sure you're in the docker group: `groups | grep docker`
- If not, run: `sudo usermod -aG docker $USER` and logout/login

### For WSL2 specific issues:
- Make sure WSL2 is updated: `wsl --update`
- Docker Desktop for Windows might be needed instead

## Services That Will Be Started

1. **Redis** (port 6379)
   - Container: `thandev-redis`
   - Image: `redis:7-alpine`

2. **Qdrant** (port 6333)
   - Container: `thandev-qdrant`
   - Image: `qdrant/qdrant:latest`
   - Volume: `qdrant_data`

