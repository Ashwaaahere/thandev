# Fly.io CLI Deployment Guide - Using Docker Containers 🐳

## 🎯 **Manual Deployment Using Fly CLI**

This guide shows how to deploy all services manually using Fly CLI, which automatically builds Docker containers from your Dockerfiles.

---

## ✅ **Prerequisites**

### **1. Install Fly CLI**

```bash
curl -L https://fly.io/install.sh | sh
```

### **2. Login to Fly.io**

```bash
fly auth login
```

### **3. Verify Login**

```bash
fly auth whoami
# Should show your email address
```

### **4. Verify Apps Exist**

```bash
fly apps list
```

**Expected apps:**
- `thandev-backend`
- `thandev-brain`
- `thandev-runner`
- `thandev-qdrant`

---

## 🚀 **Quick Deployment (All Services)**

### **Option 1: Use Deployment Script** ✅

```bash
# Deploy all services
./deploy_fly.sh all

# Or deploy individual services
./deploy_fly.sh backend
./deploy_fly.sh brain
./deploy_fly.sh runner
./deploy_fly.sh qdrant
```

---

### **Option 2: Manual Commands**

Deploy each service individually:

#### **1. Deploy Backend**

```bash
cd backend
fly deploy --remote-only --app thandev-backend
cd ..
```

**What happens:**
- Fly CLI reads `backend/fly.toml`
- Builds Docker image from `backend/Dockerfile`
- Pushes image to Fly.io registry
- Deploys to `thandev-backend` app
- Runs `release_command`: `alembic upgrade head` (database migrations)

**Duration:** ~5-7 minutes

---

#### **2. Deploy Brain**

```bash
cd services/thandev-brain
fly deploy --remote-only --app thandev-brain
cd ../..
```

**What happens:**
- Fly CLI reads `services/thandev-brain/fly.toml`
- Builds Docker image from `services/thandev-brain/Dockerfile`
- Pushes image to Fly.io registry
- Deploys to `thandev-brain` app

**Duration:** ~5-7 minutes

---

#### **3. Deploy Runner**

```bash
cd services/thandev-runner
fly deploy --remote-only --app thandev-runner
cd ../..
```

**What happens:**
- Fly CLI reads `services/thandev-runner/fly.toml`
- Builds Docker image from `services/thandev-runner/Dockerfile`
- Installs all security tools (nuclei, dalfox, nmap, etc.)
- Pushes image to Fly.io registry
- Deploys to `thandev-runner` app

**Duration:** ~10-15 minutes (largest build)

---

#### **4. Deploy Qdrant (if needed)**

```bash
cd services/qdrant-fly
fly deploy --remote-only --app thandev-qdrant
cd ../..
```

**What happens:**
- Uses pinned image: `qdrant/qdrant:v1.7.4`
- No Docker build needed (uses pre-built image)
- Deploys to `thandev-qdrant` app

**Duration:** ~2-3 minutes

---

## 📋 **Deployment Checklist**

### **Before Deployment:**

- [ ] Fly CLI installed (`fly version`)
- [ ] Logged in to Fly.io (`fly auth whoami`)
- [ ] All apps exist (`fly apps list`)
- [ ] Secrets are set (see below)
- [ ] Code changes committed locally

### **Secrets Verification:**

```bash
# Check backend secrets
fly secrets list -a thandev-backend

# Check brain secrets
fly secrets list -a thandev-brain

# Check runner secrets
fly secrets list -a thandev-runner
```

**Required Secrets:**

**Backend:**
- `DATABASE_URL` - Neon PostgreSQL URL
- `REDIS_URL` - Upstash Redis URL
- `BRAIN_URL` - `http://thandev-brain.internal:8001`

**Brain:**
- `REDIS_URL` - Upstash Redis URL
- `QDRANT_URL` - `http://thandev-qdrant.internal:6333`
- `RAG_STORE_TYPE` - `qdrant`
- `EMBEDDING_PROVIDER` - `sentence_transformers`

**Runner:**
- `DATABASE_URL` - **Same Neon URL as backend** (CRITICAL!)
- `REDIS_URL` - Upstash Redis URL
- `WORDLISTS_DIR` - `/opt/thandev/wordlists`

---

## 🔧 **Setting Secrets (If Needed)**

### **Backend Secrets:**

```bash
fly secrets set \
  REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379" \
  BRAIN_URL="http://thandev-brain.internal:8001" \
  -a thandev-backend
```

### **Brain Secrets:**

```bash
fly secrets set \
  REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379" \
  QDRANT_URL="http://thandev-qdrant.internal:6333" \
  RAG_STORE_TYPE="qdrant" \
  EMBEDDING_PROVIDER="sentence_transformers" \
  -a thandev-brain
```

### **Runner Secrets:**

```bash
# Get backend DATABASE_URL first
BACKEND_DB_URL=$(fly secrets list -a thandev-backend | grep DATABASE_URL | awk '{print $2}')

fly secrets set \
  DATABASE_URL="${BACKEND_DB_URL}" \
  REDIS_URL="redis://default:XXXXX@XXX.upstash.io:6379" \
  WORDLISTS_DIR="/opt/thandev/wordlists" \
  -a thandev-runner
```

---

## 📊 **Deployment Process**

### **How Fly CLI Deploys:**

1. **Reads `fly.toml`** - Gets app configuration
2. **Builds Docker Image** - Uses `Dockerfile` in service directory
3. **Pushes to Registry** - Uploads image to Fly.io registry
4. **Creates New Machine** - Spins up new VM with new image
5. **Health Checks** - Verifies service is healthy
6. **Switches Traffic** - Routes traffic to new machine
7. **Stops Old Machine** - Shuts down old instance

**Result:** Zero-downtime deployment! ✅

---

## 🧪 **Post-Deployment Verification**

### **1. Check Service Status:**

```bash
# Check all services
fly status -a thandev-backend
fly status -a thandev-brain
fly status -a thandev-runner
fly status -a thandev-qdrant

# All should show: STATUS = running
```

---

### **2. View Logs:**

```bash
# Backend logs
fly logs -a thandev-backend

# Brain logs
fly logs -a thandev-brain

# Runner logs (check for tool verification)
fly logs -a thandev-runner | grep -A 20 "Tool Verification"
```

---

### **3. Test Health Endpoints:**

```bash
# Backend health (public)
curl https://thandev-backend.fly.dev/healthz

# Expected: {"status":"ok",...}

# Brain health (from backend VM)
fly ssh console -a thandev-backend -C "curl -sS http://thandev-brain.internal:8001/healthz"

# Expected: {"status":"ok","service":"thandev-brain",...}
```

---

### **4. Test Internal Connectivity:**

```bash
# Test Backend → Brain
fly ssh console -a thandev-backend -C "curl -sS http://thandev-brain.internal:8001/healthz"

# Test Brain → Qdrant
fly ssh console -a thandev-brain -C "curl -sS http://thandev-qdrant.internal:6333/collections"
```

---

## 🔍 **Troubleshooting**

### **Issue: Build Fails**

**Check build logs:**
```bash
fly logs -a thandev-backend
```

**Common causes:**
- Dockerfile syntax errors
- Missing dependencies
- Build timeout

**Solution:**
- Check Dockerfile for errors
- Verify all dependencies in `requirements.txt`
- Try building locally first: `docker build -t test .`

---

### **Issue: Service Won't Start**

**Check startup logs:**
```bash
fly logs -a thandev-backend | tail -50
```

**Common causes:**
- Missing secrets
- Database connection failed
- Port conflicts

**Solution:**
- Verify all secrets are set
- Check database URL is correct
- Verify port configuration in `fly.toml`

---

### **Issue: Health Check Fails**

**Check health endpoint:**
```bash
fly ssh console -a thandev-backend -C "curl http://localhost:8000/healthz"
```

**Common causes:**
- Service not listening on correct port
- Health endpoint not implemented
- Dependencies not available

**Solution:**
- Verify `fly.toml` port matches service port
- Check health endpoint exists in code
- Verify all dependencies installed

---

## 📝 **Deployment Order (Recommended)**

### **Staged Deployment:**

1. **Backend First** (5-7 min)
   - Database migrations run automatically
   - Health checks verify connectivity

2. **Brain Second** (5-7 min)
   - Connects to Qdrant
   - Health checks verify Redis connection

3. **Runner Third** (10-15 min)
   - Longest build (installs all tools)
   - Tool verification runs on startup

4. **Qdrant Last** (2-3 min, if needed)
   - Usually doesn't need redeployment
   - Uses pinned image

**Total Time:** ~25-35 minutes

---

## 🎯 **Quick Reference**

### **Deploy Commands:**

```bash
# Deploy all (using script)
./deploy_fly.sh all

# Deploy individual services
cd backend && fly deploy --remote-only -a thandev-backend
cd services/thandev-brain && fly deploy --remote-only -a thandev-brain
cd services/thandev-runner && fly deploy --remote-only -a thandev-runner
```

### **Status Commands:**

```bash
# Check all apps
fly apps list

# Check specific app
fly status -a thandev-backend

# View logs
fly logs -a thandev-backend
```

### **Secret Commands:**

```bash
# List secrets
fly secrets list -a thandev-backend

# Set secrets
fly secrets set KEY="value" -a thandev-backend

# Remove secret
fly secrets unset KEY -a thandev-backend
```

---

## ✅ **What Gets Deployed**

### **Backend:**
- ✅ New timeout values (Nuclei: 30min, Dalfox: 40min, SQLMap: 40min)
- ✅ Watchdog timeout fixes
- ✅ Database schema updates
- ✅ All 34 fixes from today

### **Brain:**
- ✅ New timeout values (matches backend)
- ✅ Increased parallelism (10 concurrent tools)
- ✅ Better error handling

### **Runner:**
- ✅ Headless browser flags removed
- ✅ AsyncIO fixes (6 bugs)
- ✅ Redis timeout increases
- ✅ All tool execution improvements

---

## 🚀 **Ready to Deploy!**

**Run the deployment script:**

```bash
./deploy_fly.sh all
```

**Or deploy manually:**

```bash
# Backend
cd backend && fly deploy --remote-only -a thandev-backend && cd ..

# Brain
cd services/thandev-brain && fly deploy --remote-only -a thandev-brain && cd ../..

# Runner
cd services/thandev-runner && fly deploy --remote-only -a thandev-runner && cd ../..
```

**Your services will be deployed using Docker containers built from your Dockerfiles!** 🐳
