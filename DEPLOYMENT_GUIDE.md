# 🚀 Professional Lighthouse Scanner Deployment Guide

## Current Issue Analysis

### ❌ Problem
- Cloud Run service is running old mock server (version 1.0.0)
- No real jobs showing in Google Cloud Run Jobs
- Performance data is random, not URL-specific
- Missing professional report features like PageSpeed Insights

### ✅ Solution
Deploy the professional Lighthouse scanner with real data and proper Cloud Run Jobs integration.

## Step 1: Deploy Professional Scanner

### Option A: Manual Deployment (Recommended)

1. **Open Google Cloud Console**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Select project: `thandev`
   - Navigate to Cloud Run

2. **Update Service**
   - Find `lighthouse-scanner` service
   - Click "Edit & Deploy New Revision"
   - Change source to "Container image URL"
   - Use: `gcr.io/thandev/lighthouse-scanner:latest`

3. **Build New Image**
   ```bash
   cd cloud-run/lighthouse-scanner
   
   # Build the image
   gcloud builds submit --tag gcr.io/thandev/lighthouse-scanner:professional --project=thandev
   
   # Deploy to Cloud Run
   gcloud run deploy lighthouse-scanner \
     --image gcr.io/thandev/lighthouse-scanner:professional \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --project thandev
   ```

### Option B: Using Docker (Alternative)

```bash
cd cloud-run/lighthouse-scanner

# Build locally
docker build -t lighthouse-scanner-professional .

# Tag for GCR
docker tag lighthouse-scanner-professional gcr.io/thandev/lighthouse-scanner:professional

# Push to GCR
docker push gcr.io/thandev/lighthouse-scanner:professional
```

## Step 2: Verify Deployment

### Check Service Health
```bash
curl "https://lighthouse-scanner-697855159499.us-central1.run.app/health"
```

Expected response:
```json
{
  "status": "healthy",
  "version": "3.0.0-professional"
}
```

### Test Real Scan
```bash
# Start scan
curl -X POST https://lighthouse-scanner-697855159499.us-central1.run.app/run \
  -H "Content-Type: application/json" \
  -d '{"url":"https://google.com","device":"desktop","category":"performance"}'

# Check status (replace JOB_ID)
curl "https://lighthouse-scanner-697855159499.us-central1.run.app/status/JOB_ID"
```

## Step 3: Professional Features

### Real Performance Data
- ✅ Actual Lighthouse audits
- ✅ Real Core Web Vitals
- ✅ URL-specific performance scores
- ✅ Professional opportunities & diagnostics
- ✅ Full-page screenshots

### Cloud Run Jobs Integration
- ✅ Real job tracking
- ✅ Job status monitoring
- ✅ Professional error handling
- ✅ Scalable execution

## Step 4: Frontend Integration

The frontend is already configured to use the Cloud Run service. After deployment:

1. **Test Dashboard**: Go to `/dashboard/scan`
2. **Select Performance Scan**: Choose performance category
3. **Enter URL**: Try different URLs for varied results
4. **View Results**: See professional performance data

## Expected Results

### Professional Performance Scores
- **Google.com**: 85-95 (fast, optimized)
- **GitHub.com**: 70-85 (complex but optimized)
- **Example.com**: 60-75 (basic site)
- **Local sites**: 50-70 (development)

### Real Metrics
- First Contentful Paint (FCP)
- Largest Contentful Paint (LCP)
- Cumulative Layout Shift (CLS)
- Speed Index
- Total Blocking Time (TBT)
- Time to Interactive (TTI)

### Professional Opportunities
- Remove unused CSS
- Eliminate render-blocking resources
- Optimize images
- Minimize main-thread work

## Troubleshooting

### If Deployment Fails
1. Check Google Cloud permissions
2. Verify project ID: `thandev`
3. Ensure Cloud Run API is enabled
4. Check billing account

### If Scans Fail
1. Verify URL accessibility
2. Check Cloud Run logs
3. Ensure Chromium is installed in container
4. Verify network connectivity

## Next Steps

After successful deployment:
1. ✅ Real jobs will appear in Google Cloud Run Jobs
2. ✅ Professional performance reports
3. ✅ Accurate, URL-specific data
4. ✅ Full-page screenshots
5. ✅ Real Lighthouse audits

This will give you the professional, accurate scan reports like PageSpeed Insights!