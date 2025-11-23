# Security Scanner Deployment Guide

This guide walks you through deploying the complete Security Scanner implementation.

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker installed
- Node.js 18+ and Python 3.9+

## Step 1: Backend Deployment

### 1.1 Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 1.2 Set Environment Variables
```bash
export BACKEND_URL=http://localhost:8000
export CLOUD_RUN_JOB_URL=https://your-region-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/your-project/jobs/security-scanner-job
```

### 1.3 Start Backend Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Step 2: Cloud Run Job Deployment

### 2.1 Deploy Security Scanner Job
```bash
cd cloud-run
chmod +x deploy-security-scanner.sh
./deploy-security-scanner.sh YOUR_PROJECT_ID us-central1
```

### 2.2 Update Backend Environment
After deployment, update your backend environment with the Cloud Run Job URL:
```bash
export CLOUD_RUN_JOB_URL=https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/YOUR_PROJECT_ID/jobs/security-scanner-job
```

## Step 3: Frontend Setup

### 3.1 Install Dependencies
```bash
cd frontend
npm install
```

### 3.2 Set Environment Variables
Create `.env.local`:
```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
BACKEND_URL=http://localhost:8000
```

### 3.3 Start Frontend
```bash
npm run dev
```

## Step 4: Testing

### 4.1 Run Integration Test
```bash
node test-security-scan.js
```

### 4.2 Manual Testing
1. Open http://localhost:3000/dashboard/scan
2. Enter a test URL (e.g., https://httpbin.org)
3. Select "Quick Scan"
4. Click "Start Quick Security Scan"
5. Monitor progress and view results

## Step 5: Production Deployment

### 5.1 Deploy Backend to Cloud Run
```bash
# Build and deploy backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/thandev-backend ./backend
gcloud run deploy thandev-backend \
  --image gcr.io/YOUR_PROJECT_ID/thandev-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300
```

### 5.2 Deploy Frontend to Vercel
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy frontend
cd frontend
vercel --prod
```

### 5.3 Update Environment Variables
Update production environment variables:
- `NEXT_PUBLIC_BACKEND_URL` to your Cloud Run backend URL
- `BACKEND_URL` to your Cloud Run backend URL
- `CLOUD_RUN_JOB_URL` to your Cloud Run Job URL

## Monitoring

### 6.1 View Logs
```bash
# Backend logs
gcloud logs read --service=thandev-backend --limit=50

# Cloud Run Job logs
gcloud logs read --service=security-scanner-job --limit=50
```

### 6.2 Monitor Performance
- Check Cloud Run metrics in Google Cloud Console
- Monitor scan success rates and durations
- Set up alerts for failed scans

## Troubleshooting

### Common Issues

1. **Scan Timeout**
   - Increase Cloud Run Job timeout to 30 minutes
   - Check if target URL is accessible

2. **Memory Issues**
   - Increase Cloud Run Job memory to 4Gi
   - Optimize scan parameters

3. **Network Errors**
   - Verify firewall rules
   - Check VPC configuration

4. **Tool Failures**
   - Ensure security tools are installed in container
   - Check tool permissions

### Debug Mode
Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
```

## Security Considerations

1. **Rate Limiting**: Implement rate limiting for scan requests
2. **Authentication**: Ensure proper user authentication
3. **Input Validation**: Validate all input parameters
4. **Resource Limits**: Set appropriate resource limits
5. **Logging**: Monitor and log all scan activities

## Cost Optimization

1. **Auto-scaling**: Configure appropriate scaling parameters
2. **Resource Allocation**: Right-size memory and CPU
3. **Timeout Settings**: Set reasonable timeout values
4. **Monitoring**: Track usage and costs

## Support

For issues or questions:
1. Check the logs for error messages
2. Review the troubleshooting section
3. Check Google Cloud Console for resource issues
4. Contact the development team

## Next Steps

1. Set up monitoring and alerting
2. Implement additional security tools
3. Add more scan types and templates
4. Integrate with CI/CD pipelines
5. Add compliance reporting features


