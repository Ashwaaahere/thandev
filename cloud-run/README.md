# Lighthouse Scanner - Cloud Run Deployment

This directory contains the scalable Lighthouse performance scanner for Thandev, deployed on Google Cloud Run.

## Architecture

- **Vercel Frontend**: Control API and user interface
- **Cloud Run**: Scalable Lighthouse scanning service
- **Lighthouse**: Google's performance auditing tool
- **Puppeteer**: Headless Chrome automation

## Features

- ⚡ **Fast Performance Scans**: 30-60 second scans
- 📱 **Mobile & Desktop**: Device-specific analysis
- 🔄 **Scalable**: Auto-scaling Cloud Run instances
- 📊 **Core Web Vitals**: FCP, LCP, CLS metrics
- 🎯 **Optimization Opportunities**: Actionable recommendations

## Setup

### Prerequisites

1. Google Cloud Project with billing enabled
2. `gcloud` CLI installed and authenticated
3. Cloud Run API enabled

### Deployment

```bash
# Deploy to Cloud Run
./deploy.sh your-project-id us-central1

# Or manually:
gcloud builds submit --tag gcr.io/PROJECT_ID/lighthouse-scanner ./lighthouse-scanner
gcloud run deploy lighthouse-scanner \
  --image gcr.io/PROJECT_ID/lighthouse-scanner \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900
```

### Environment Variables

Update your frontend `.env.local`:

```env
CLOUD_RUN_JOB_URL=https://lighthouse-scanner-xxxxx-uc.a.run.app
CLOUD_RUN_TOKEN=your-service-account-token
```

## API Endpoints

### POST /run
Start a new Lighthouse scan

```json
{
  "url": "https://example.com",
  "device": "desktop",
  "category": "performance"
}
```

### GET /status/:jobId
Check scan status and get results

## Performance Metrics

The scanner provides:

- **Core Web Vitals**: FCP, LCP, CLS
- **Performance Metrics**: Speed Index, TBT, TTI
- **Optimization Opportunities**: Actionable recommendations
- **Diagnostics**: Detailed performance analysis

## Cost Optimization

- **Auto-scaling**: Scales to zero when not in use
- **Concurrency**: Handles multiple scans efficiently
- **Timeout**: 15-minute maximum per scan
- **Memory**: 2GB allocated for Chrome + Lighthouse

## Monitoring

Monitor your Cloud Run service:

```bash
# View logs
gcloud logs read --service=lighthouse-scanner

# Check metrics
gcloud run services describe lighthouse-scanner --region=us-central1
```

## Security

- **CORS**: Configured for Thandev domain
- **Helmet**: Security headers enabled
- **Input Validation**: URL validation and sanitization
- **Resource Limits**: Memory and CPU constraints

## Troubleshooting

### Common Issues

1. **Chrome crashes**: Increase memory allocation
2. **Timeout errors**: Check network connectivity
3. **CORS errors**: Verify domain configuration

### Debug Mode

Set `NODE_ENV=development` for detailed logging.

## Scaling

The service automatically scales based on demand:
- **Min instances**: 0 (scales to zero)
- **Max instances**: 100
- **Concurrency**: 10 requests per instance
- **Memory**: 2GB per instance
- **CPU**: 2 vCPUs per instance







