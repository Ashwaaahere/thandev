# ✅ Google Cloud Deployment Checklist

## Pre-Deployment Checklist

- [ ] **Google Cloud Account** with billing enabled
- [ ] **Google Cloud Project** created
- [ ] **Google Cloud CLI** installed (`gcloud --version`)
- [ ] **Docker** installed (for local testing)
- [ ] **Required APIs** enabled:
  - [ ] Cloud Build API
  - [ ] Cloud Run API
  - [ ] Container Registry API

## Deployment Steps

### 1. Authentication & Setup
- [ ] Run `gcloud init` and select your project
- [ ] Run `./setup-gcloud.sh` (or manual setup)
- [ ] Verify project: `gcloud config get-value project`
- [ ] Enable APIs: `gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com`

### 2. Deploy Service
- [ ] Navigate to `cloud-run/` directory
- [ ] Run `./deploy.sh YOUR_PROJECT_ID us-central1`
- [ ] Wait for deployment to complete
- [ ] Note the service URL from output

### 3. Configure Frontend
- [ ] Update `frontend/.env.local` with:
  - [ ] `CLOUD_RUN_JOB_URL=https://lighthouse-scanner-xxxxx-uc.a.run.app`
  - [ ] `CLOUD_RUN_TOKEN=your-service-account-token`
  - [ ] `PROJECT_ID=your-project-id`

### 4. Test Deployment
- [ ] Test Cloud Run health: `curl https://your-service-url/health`
- [ ] Test scan endpoint: `curl -X POST https://your-service-url/run -H "Content-Type: application/json" -d '{"url":"https://example.com"}'`
- [ ] Test frontend API: `curl -X POST http://localhost:3000/api/lighthouse -H "Content-Type: application/json" -d '{"url":"https://example.com"}'`

### 5. Verify Integration
- [ ] Open dashboard: `http://localhost:3000/dashboard/scan`
- [ ] Select "Performance Scan" category
- [ ] Enter a test URL
- [ ] Start a performance scan
- [ ] Verify results display correctly

## Post-Deployment Monitoring

- [ ] **Check logs**: `gcloud logs read --service=lighthouse-scanner --limit=20`
- [ ] **Monitor costs**: Check Google Cloud Console billing
- [ ] **Set up alerts**: Configure budget alerts
- [ ] **Test scaling**: Run multiple scans simultaneously
- [ ] **Verify security**: Check CORS and authentication

## Troubleshooting Checklist

### If deployment fails:
- [ ] Check `gcloud auth list` - are you authenticated?
- [ ] Verify project: `gcloud config get-value project`
- [ ] Check billing: `gcloud billing projects describe YOUR_PROJECT_ID`
- [ ] Enable APIs: `gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com`

### If service doesn't start:
- [ ] Check logs: `gcloud logs read --service=lighthouse-scanner`
- [ ] Verify memory/CPU limits in deployment
- [ ] Check Dockerfile syntax
- [ ] Verify package.json dependencies

### If frontend can't connect:
- [ ] Verify `CLOUD_RUN_JOB_URL` in `.env.local`
- [ ] Check CORS settings in Cloud Run service
- [ ] Verify service account permissions
- [ ] Test Cloud Run service directly

### If scans fail:
- [ ] Check Cloud Run service logs
- [ ] Verify Lighthouse dependencies
- [ ] Check Chrome/Puppeteer configuration
- [ ] Test with simple URLs first

## Success Criteria

- [ ] ✅ Cloud Run service deployed and accessible
- [ ] ✅ Frontend can initiate scans
- [ ] ✅ Performance results display correctly
- [ ] ✅ Multiple scans can run concurrently
- [ ] ✅ Service scales automatically
- [ ] ✅ Costs are within expected range

## Quick Commands Reference

```bash
# Check status
gcloud run services describe lighthouse-scanner --region=us-central1

# View logs
gcloud logs read --service=lighthouse-scanner --limit=50

# Test health
curl https://lighthouse-scanner-xxxxx-uc.a.run.app/health

# Redeploy
./deploy.sh YOUR_PROJECT_ID us-central1

# Check costs
gcloud billing accounts list
```

---

**🎯 Goal**: Successfully deploy a scalable Lighthouse performance scanner that integrates with the Thandev dashboard and provides real-time website performance analysis.





