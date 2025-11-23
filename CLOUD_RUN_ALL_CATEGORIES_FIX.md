# Fix: Enable All Lighthouse Categories in Cloud Run Service

## 🔴 Problem

Accessibility, Best Practices, and SEO were showing as **0** because:
- Cloud Run Service was only scanning the `performance` category
- `onlyCategories: ['performance']` excluded other categories
- These categories were never measured, so they defaulted to 0

## ✅ Fix Applied

### 1. Updated `cloud-run/lighthouse-scanner/server.js`

**Changed:**
```javascript
onlyCategories: ['performance']
```

**To:**
```javascript
onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo']
```

### 2. Extract All Category Scores

Now extracts scores for all 4 categories:
- `performance`
- `accessibility`
- `best-practices` (mapped to `bestPractices`)
- `seo`

### 3. Return Categories Object

Cloud Run Service now returns:
```javascript
{
  categories: {
    performance: 58,
    accessibility: 85,
    bestPractices: 92,
    seo: 78
  },
  metrics: {...},
  opportunities: [...],
  diagnostics: [...]
}
```

## 🚀 Deployment Required

**The Cloud Run Service needs to be redeployed for this to take effect!**

### Option 1: Using gcloud CLI

```bash
cd cloud-run/lighthouse-scanner
gcloud run deploy lighthouse-scanner \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900
```

### Option 2: Using Cloud Build (if configured)

```bash
cd cloud-run/lighthouse-scanner
gcloud builds submit --tag gcr.io/PROJECT_ID/lighthouse-scanner
gcloud run deploy lighthouse-scanner \
  --image gcr.io/PROJECT_ID/lighthouse-scanner \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900
```

### Option 3: Check for Deployment Script

```bash
cd cloud-run
ls -la *.sh
# Look for deploy-lighthouse.sh or similar
```

## ✅ After Redeployment

1. **Submit a new performance scan** from the frontend
2. **Check the results** - you should now see:
   - ✅ Real **Performance** score (already working)
   - ✅ Real **Accessibility** score (was 0, now will be real)
   - ✅ Real **Best Practices** score (was 0, now will be real)
   - ✅ Real **SEO** score (was 0, now will be real)

## 📊 Expected Results

After redeployment, scans will take slightly longer (scanning 4 categories instead of 1), but you'll get:
- Complete Lighthouse audit results
- All category scores (0-100)
- More comprehensive optimization opportunities
- Better diagnostic information

## ⚠️ Important Notes

- **Scan time will increase**: ~30-60 seconds → ~60-90 seconds (scanning 4 categories)
- **Memory usage may increase**: Lighthouse needs more memory for full audits
- **Backend already handles the new format**: No backend changes needed after Cloud Run redeploy

## 🔍 Verify Deployment

After redeploying, test the Cloud Run Service directly:

```bash
# Start a scan
curl -X POST https://lighthouse-scanner-697855159499.us-central1.run.app/run \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "device": "desktop"}'

# Check status (use jobId from response)
curl https://lighthouse-scanner-697855159499.us-central1.run.app/status/JOB_ID

# Response should include:
# {
#   "categories": {
#     "performance": 85,
#     "accessibility": 90,
#     "bestPractices": 92,
#     "seo": 78
#   },
#   ...
# }
```

