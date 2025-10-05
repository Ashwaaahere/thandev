# 🚀 Quick Google Cloud Deployment Guide

## Prerequisites
- Google Cloud Account with billing enabled
- Google Cloud Project created

## Step 1: Install Google Cloud CLI
```bash
sudo snap install google-cloud-cli --classic
```

## Step 2: Initialize Google Cloud
```bash
# Navigate to cloud-run directory
cd /home/avi/Downloads/thandev-github-starter/thandev/cloud-run

# Initialize gcloud (this will open a browser for authentication)
gcloud init

# Select your project when prompted
# Choose "Y" for default region (us-central1)
```

## Step 3: Enable Required APIs
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

## Step 4: Deploy Lighthouse Scanner
```bash
# Replace YOUR_PROJECT_ID with your actual project ID
./deploy.sh YOUR_PROJECT_ID us-central1
```

**Example:**
```bash
./deploy.sh my-thandev-project-123 us-central1
```

## Step 5: Update Environment Variables

After deployment, you'll get a service URL like:
`https://lighthouse-scanner-xxxxx-uc.a.run.app`

Update your `frontend/.env.local` file:

```env
# Replace these placeholder values with actual values from deployment
CLOUD_RUN_JOB_URL=https://lighthouse-scanner-xxxxx-uc.a.run.app
CLOUD_RUN_TOKEN=your-service-account-token
PROJECT_ID=your-project-id
```

## Step 6: Test Deployment

### Test Cloud Run Service:
```bash
# Health check
curl https://lighthouse-scanner-xxxxx-uc.a.run.app/health

# Test scan
curl -X POST https://lighthouse-scanner-xxxxx-uc.a.run.app/run \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","device":"desktop","category":"performance"}'
```

### Test Frontend Integration:
1. Start your frontend: `npm run dev`
2. Go to: `http://localhost:3000/dashboard/scan`
3. Select "Performance Scan" category
4. Enter a test URL (e.g., `https://example.com`)
5. Click "Start Performance Scan"
6. Wait for results (30-60 seconds)

## Troubleshooting

### If deployment fails:
```bash
# Check authentication
gcloud auth list

# Check project
gcloud config get-value project

# Check billing
gcloud billing projects describe YOUR_PROJECT_ID
```

### If service doesn't start:
```bash
# Check logs
gcloud logs read --service=lighthouse-scanner --limit=20

# Check service status
gcloud run services describe lighthouse-scanner --region=us-central1
```

### If frontend can't connect:
1. Verify `CLOUD_RUN_JOB_URL` in `.env.local`
2. Check CORS settings
3. Test Cloud Run service directly

## Expected Output

After successful deployment, you should see:
```
✅ Deployment complete!
Service URL: https://lighthouse-scanner-xxxxx-uc.a.run.app

🔧 Update your frontend environment variables:
CLOUD_RUN_JOB_URL=https://lighthouse-scanner-xxxxx-uc.a.run.app
CLOUD_RUN_TOKEN=your-service-account-token
```

## Cost Estimate

- **Free tier**: 2 million requests/month
- **After free tier**: ~$0.40 per million requests
- **Compute**: Scales to zero when not in use
- **Storage**: Minimal (logs only)

---

**🎯 Goal**: Deploy a scalable Lighthouse scanner that integrates with your Thandev dashboard for real-time website performance analysis.





