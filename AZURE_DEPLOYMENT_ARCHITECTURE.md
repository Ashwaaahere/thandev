# Azure Deployment Architecture

## Overview
All Thandev services are deployed on **Azure Container Apps** in the `rg-thandev-prod` resource group in the **East US** region.

## Deployed Services

### 1. Frontend (Vercel)
- **Platform**: Vercel
- **URL**: https://thandev.vercel.app
- **Environment Variables**:
  - `NEXT_PUBLIC_API_BASE_URL`: `https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
  - Content Security Policy configured to allow connections to Azure backend
  
### 2. Backend (Azure Container App)
- **Service Name**: `thandev-backend`
- **Type**: Public (External ingress)
- **FQDN**: `thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
- **Port**: 8080
- **Status**: ✅ Running
- **Environment Variables**:
  - `DATABASE_URL`: PostgreSQL (Neon.tech)
  - `REDIS_URL`: Redis connection string (secret)
  - `PORT`: 8080
  - `CORS_ORIGINS`: `https://thandev.vercel.app,https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
  - `THANDEV_SUPERADMIN_EXTERNAL_IDS`: `github:97579623`
  - `BRAIN_SERVICE_ENABLED`: Not set (defaults to False)

### 3. Runner (Azure Container App)
- **Service Name**: `thandev-runner`
- **Type**: Internal (No external ingress)
- **FQDN**: `thandev-runner.internal.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
- **Status**: ✅ Running
- **Purpose**: Background worker for executing security scans
- **Environment Variables**:
  - `DATABASE_URL`: Shared PostgreSQL database (secret)
  - `REDIS_URL`: Redis connection string (secret)
  - `CELERY_BROKER_URL`: Redis connection string (secret)
  - `BACKEND_URL`: ✅ `https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
  - `ZAP_API_URL`: ✅ `http://thandev-zap.internal.thankfulisland-9a04feba.eastus.azurecontainerapps.io:8090`

### 4. ZAP (OWASP ZAP - Azure Container App)
- **Service Name**: `thandev-zap`
- **Type**: Internal (No external ingress)
- **FQDN**: `thandev-zap.internal.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
- **Port**: 8090
- **Status**: ✅ Running
- **Purpose**: OWASP ZAP security scanner for web application vulnerability scanning

## Service Communication Flow

```
┌─────────────────┐
│   Frontend      │
│   (Vercel)      │
│  thandev.vercel │
│      .app       │
└────────┬────────┘
         │ HTTPS
         │ API Calls
         ↓
┌─────────────────────────────────────────────┐
│         Backend (Azure Container App)        │
│  thandev-backend.thankfulisland-...         │
│  - Handles API requests                     │
│  - Admin authentication                      │
│  - Database operations                       │
│  - Publishes scan jobs to Redis             │
└──────────────┬──────────────────────────────┘
               │
               │ Redis Streams
               ↓
┌─────────────────────────────────────────────┐
│        Runner (Azure Container App)         │
│  thandev-runner.internal...                 │
│  - Consumes scan jobs from Redis            │
│  - Executes security tools                  │
│  - Calls ZAP for web scanning               │
│  - Writes findings back to database         │
└──────────────┬──────────────────────────────┘
               │ HTTP API
               ↓
┌─────────────────────────────────────────────┐
│          ZAP (Azure Container App)          │
│  thandev-zap.internal...                    │
│  - Passive scanning                         │
│  - Active scanning                          │
│  - AJAX spider                              │
└─────────────────────────────────────────────┘
```

## Shared Resources

### PostgreSQL Database (Neon.tech)
- **Provider**: Neon.tech (Serverless PostgreSQL)
- **Region**: US East 1 (AWS)
- **Shared by**: Backend + Runner
- **Purpose**: Store users, scans, findings, projects

### Redis
- **Type**: Redis stream
- **Shared by**: Backend (publisher) + Runner (consumer)
- **Purpose**: Job queue for scan orchestration

## Recent Configuration Updates ✅

### 1. CSP Configuration (Frontend)
- **Issue**: Content Security Policy was blocking connections to Azure backend
- **Fix**: Added `https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io` to `connect-src` directive
- **File**: `frontend/next.config.mjs`
- **Status**: ✅ Deployed to Vercel

### 2. Backend Configuration
- **Added**: `PORT=8080` (matches Azure ingress configuration)
- **Added**: `CORS_ORIGINS` with Vercel and Azure backend URLs
- **Added**: `THANDEV_SUPERADMIN_EXTERNAL_IDS=github:97579623` (admin access)
- **Status**: ✅ Configured and running

### 3. Runner Configuration
- **Added**: `ZAP_API_URL=http://thandev-zap.internal.thankfulisland-9a04feba.eastus.azurecontainerapps.io:8090`
- **Added**: `BACKEND_URL=https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io`
- **Status**: ✅ Configured and running

## Security Notes

1. **Internal Services**: Runner and ZAP are configured with internal ingress only - they cannot be accessed from the public internet
2. **Admin Access**: Admin privileges are granted via `THANDEV_SUPERADMIN_EXTERNAL_IDS` based on GitHub user ID
3. **CORS**: Backend is configured to only accept requests from Vercel frontend
4. **Database**: Uses SSL/TLS with certificate validation (Neon.tech)

## Verification Steps

### Test Frontend → Backend Connection
```bash
curl https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io/api/health
```

### Check Backend Logs
```bash
az containerapp logs show --name thandev-backend --resource-group rg-thandev-prod --tail 50
```

### Check Runner Logs
```bash
az containerapp logs show --name thandev-runner --resource-group rg-thandev-prod --tail 50
```

### Check ZAP Status
```bash
az containerapp show --name thandev-zap --resource-group rg-thandev-prod --query "properties.runningStatus"
```

## Troubleshooting

### If Frontend Shows "Failed to fetch"
1. Check CSP configuration in `frontend/next.config.mjs`
2. Verify `NEXT_PUBLIC_API_BASE_URL` is set correctly in Vercel
3. Check backend CORS configuration

### If Scans Get Stuck
1. Check runner is running: `az containerapp show --name thandev-runner --resource-group rg-thandev-prod --query "properties.runningStatus"`
2. Verify runner can connect to ZAP
3. Check Redis connectivity
4. Verify DATABASE_URL is the same for backend and runner

### If ZAP Scans Fail
1. Verify ZAP service is running
2. Check ZAP_API_URL is configured correctly in runner
3. Verify internal DNS resolution works within Azure Container Apps environment

## Next Steps

1. ✅ Frontend deployment complete (Vercel)
2. ✅ Backend deployment complete (Azure)
3. ✅ Runner deployment complete (Azure)
4. ✅ ZAP deployment complete (Azure)
5. ✅ All services connected and configured
6. ✅ Admin access configured
7. ✅ CSP configuration fixed

**Status**: All services are deployed and connected! 🎉

## Access Your Application

- **Frontend**: https://thandev.vercel.app
- **Backend API**: https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io
- **Admin User**: Your GitHub account (asatishkumar@binghamton.edu)

After the Vercel deployment completes (wait 2-3 minutes), refresh your browser and you should be able to access the full dashboard!


