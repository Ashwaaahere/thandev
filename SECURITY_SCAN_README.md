# Security Scanner Implementation

This document describes the implementation of the "Quick Scan" flow for the Security Scan page, featuring a complete integration between Next.js frontend, FastAPI backend, and Google Cloud Run Jobs.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Next.js       │    │   FastAPI       │    │   Cloud Run     │
│   Frontend      │    │   Backend       │    │   Job           │
│                 │    │                 │    │                 │
│ 1. User submits │───▶│ 2. API receives │───▶│ 3. Job triggers │
│    URL for scan │    │    scan request │    │    security     │
│                 │    │                 │    │    tools        │
│                 │    │                 │    │                 │
│ 6. Display      │◀───│ 5. Store &      │◀───│ 4. Send results │
│    results in   │    │    process      │    │    via webhook  │
│    dashboard    │    │    results      │    │    callback     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Components

### 1. Frontend (Next.js)

**File**: `frontend/app/api/security-scan/route.ts`
- Handles scan initiation and status polling
- Validates URL format and scan types
- Communicates with FastAPI backend

**File**: `frontend/components/Dashboard/DashboardScanClient.tsx`
- Modern, futuristic UI for scan configuration
- Real-time scan progress monitoring
- Advanced results visualization with:
  - Security score breakdown
  - Vulnerability categorization
  - Interactive charts and metrics
  - Detailed recommendations

### 2. Backend (FastAPI)

**File**: `backend/app/routers/security.py`
- `/api/security-scan/` - POST endpoint to start scans
- `/api/security-scan/{job_id}` - GET endpoint for scan status
- `/api/security-scan/callback/{job_id}` - POST webhook for results
- Supports both Cloud Run Jobs and local scanning
- Comprehensive vulnerability processing

### 3. Cloud Run Job

**File**: `cloud-run/security-scanner/scanner.py`
- Runs nuclei, nmap, and sslscan tools
- Supports quick, comprehensive, and deep scan types
- Sends results back via webhook callback
- Handles SSL/TLS analysis, port scanning, and vulnerability detection

## Features

### Scan Types

1. **Quick Scan** (5-10 minutes)
   - SSL/TLS analysis
   - Security headers check
   - Basic port scanning
   - Common vulnerability detection

2. **Comprehensive Scan** (15-30 minutes)
   - All quick scan features
   - Authentication analysis
   - Input validation testing
   - Directory listing checks

3. **Deep Scan** (30-60 minutes)
   - All comprehensive features
   - Subdomain enumeration
   - Directory brute force
   - Advanced penetration testing

### Security Tools Integration

- **Nuclei**: Vulnerability scanner with 1000+ templates
- **Nmap**: Network port scanner and service detection
- **SSLScan**: SSL/TLS configuration analysis
- **Custom checks**: Security headers, directory listing, robots.txt

### Dashboard Features

- **Real-time Progress**: Live scan status updates
- **Security Score**: 0-100 scoring system
- **Vulnerability Categories**: Critical, High, Medium, Low, Info
- **Interactive Charts**: Visual representation of security metrics
- **Detailed Reports**: Comprehensive vulnerability descriptions
- **Recommendations**: Actionable security advice
- **Scan History**: Previous scan results and trends

## API Endpoints

### Start Security Scan
```http
POST /api/security-scan
Content-Type: application/json

{
  "url": "https://example.com",
  "scanType": "quick",
  "priority": "normal"
}
```

### Get Scan Status
```http
GET /api/security-scan?jobId={job_id}
```

### Webhook Callback (Internal)
```http
POST /api/security-scan/callback/{job_id}
Content-Type: application/json

{
  "vulnerabilities": [...],
  "ports": [...],
  "sslIssues": [...],
  "securityScore": 85,
  "severityBreakdown": {...}
}
```

## Deployment

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Cloud Run Job Deployment
```bash
cd cloud-run
chmod +x deploy-security-scanner.sh
./deploy-security-scanner.sh YOUR_PROJECT_ID us-central1
```

### 3. Environment Variables
```env
# Backend
BACKEND_URL=http://localhost:8000
CLOUD_RUN_JOB_URL=https://your-region-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/your-project/jobs/security-scanner-job

# Frontend
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## Usage

1. **Navigate to Security Scan Page**: `/dashboard/scan`
2. **Enter Target URL**: Input the website or IP to scan
3. **Select Scan Type**: Choose quick, comprehensive, or deep
4. **Start Scan**: Click the scan button to initiate
5. **Monitor Progress**: Watch real-time progress updates
6. **Review Results**: Analyze vulnerabilities and recommendations

## Security Considerations

- **Rate Limiting**: Implement rate limiting for scan requests
- **Authentication**: Ensure only authenticated users can start scans
- **Input Validation**: Strict URL validation and sanitization
- **Resource Limits**: Cloud Run Job timeouts and memory limits
- **Error Handling**: Comprehensive error handling and logging

## Monitoring and Logging

- **Backend Logs**: FastAPI application logs
- **Cloud Run Logs**: Job execution logs
- **Frontend Logs**: Client-side error tracking
- **Metrics**: Scan success rates, duration, and error counts

## Future Enhancements

- **Scheduled Scans**: Automated recurring security scans
- **Custom Templates**: User-defined vulnerability templates
- **Integration APIs**: Third-party security tool integrations
- **Advanced Analytics**: Machine learning-based threat detection
- **Compliance Reporting**: Industry-standard compliance reports

## Troubleshooting

### Common Issues

1. **Scan Timeout**: Increase Cloud Run Job timeout settings
2. **Memory Issues**: Adjust Cloud Run Job memory allocation
3. **Network Errors**: Check firewall and network connectivity
4. **Tool Failures**: Verify security tools are properly installed

### Debug Mode

Enable debug logging by setting:
```env
LOG_LEVEL=DEBUG
```

## Contributing

1. Follow the existing code structure
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure security best practices are followed

## License

This implementation is part of the Thandev project and follows the same licensing terms.


