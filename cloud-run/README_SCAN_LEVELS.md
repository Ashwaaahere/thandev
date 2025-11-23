# Security Scan Levels - Cloud Run Deployment

This document describes the Cloud Run Job mappings and deployment for the new scan levels system.

## Scan Levels Overview

The security scanner now supports three distinct scan levels, each with specific tool configurations and Cloud Run Job mappings:

### Level 0 — Surface (Quick)
- **Purpose**: Very fast, low-noise footprinting and tech checks
- **Duration**: 3-8 minutes
- **Cloud Run Job**: `thandev-surface`
- **Tools**: nuclei (info, technologies), sslscan/sslyze/openssl, nmap (--top-ports 100 -sV -Pn)

### Level 1 — Discovery (Buzz)
- **Purpose**: Broaden surface, find hidden endpoints and subdomains
- **Duration**: 10-25 minutes
- **Cloud Run Job**: `thandev-buzz`
- **Tools**: Everything in Level 0 plus: subfinder/amass, crt.sh lookups, ffuf/gobuster, nuclei medium templates

### Level 2 — Active (Non-destructive)
- **Purpose**: More aggressive detection (non-exploitative) and CVE checks
- **Duration**: 20-45 minutes
- **Cloud Run Job**: `thandev-active`
- **Tools**: Everything in Level 1 plus: nuclei CVE templates, nikto, nmap with NSE scripts

## Cloud Run Job Configuration

### Environment Variables

Each Cloud Run Job expects the following environment variables:

```bash
URL=<target_url>
TIER=<level0|level1|level2>
JOB_ID=<unique_job_identifier>
CALLBACK_URL=<backend_callback_url>
CALLBACK_SECRET=<hmac_secret>
PRESET_NAME=<preset_name>
```

### Job Execution Commands

#### Level 0 (Surface)
```bash
gcloud run jobs execute thandev-surface \
  --region us-central1 \
  --project thandev \
  --update-env-vars URL=https://example.com,TIER=level0,JOB_ID=job123,CALLBACK_URL=https://backend.com/api/security-scan/callback/job123,CALLBACK_SECRET=secret,PRESET_NAME=normal
```

#### Level 1 (Discovery)
```bash
gcloud run jobs execute thandev-buzz \
  --region us-central1 \
  --project thandev \
  --update-env-vars URL=https://example.com,TIER=level1,JOB_ID=job123,CALLBACK_URL=https://backend.com/api/security-scan/callback/job123,CALLBACK_SECRET=secret,PRESET_NAME=buzz
```

#### Level 2 (Active)
```bash
gcloud run jobs execute thandev-active \
  --region us-central1 \
  --project thandev \
  --update-env-vars URL=https://example.com,TIER=level2,JOB_ID=job123,CALLBACK_URL=https://backend.com/api/security-scan/callback/job123,CALLBACK_SECRET=secret,PRESET_NAME=active
```

## IAM Permissions

### Backend Service Account
The backend service account needs the following permissions to trigger Cloud Run Jobs:

```yaml
- roles/run.invoker
- roles/run.developer
```

### Cloud Run Job Service Account
The Cloud Run Job service account needs the following permissions to write artifacts:

```yaml
- roles/storage.objectCreator
- roles/storage.objectViewer
```

## Artifact Storage

Scan artifacts are stored in Google Cloud Storage with the following structure:

```
gs://thandev-scan-artifacts/
├── {job_id}/
│   ├── nuclei.json
│   ├── ssl_scan.txt
│   ├── nmap.xml
│   ├── subdomains.txt
│   ├── ffuf_results.json
│   └── nikto_results.json
```

## Callback Format

The Cloud Run Job sends results back to the backend via POST to the callback URL:

```json
{
  "summary": {
    "url": "https://example.com",
    "tier": "level1",
    "timestamp": "2024-01-01T00:00:00Z",
    "vulnerabilities": [...],
    "totalVulnerabilities": 5,
    "severityBreakdown": {
      "critical": 0,
      "high": 1,
      "medium": 2,
      "low": 2,
      "info": 0
    },
    "securityScore": 75,
    "openPorts": 3,
    "sslIssuesCount": 1,
    "scanMetadata": {
      "toolsUsed": ["nuclei", "nmap", "sslscan", "subfinder", "ffuf"],
      "scanTime": "2024-01-01T00:00:00Z"
    }
  },
  "artifact_urls": [
    "gs://thandev-scan-artifacts/job123/nuclei.json",
    "gs://thandev-scan-artifacts/job123/nmap.xml"
  ]
}
```

## Deployment Steps

1. **Build and push Docker images** for each scan level:
   ```bash
   # Build the scanner image
   docker build -t gcr.io/thandev/security-scanner:latest ./cloud-run/security-scanner/
   docker push gcr.io/thandev/security-scanner:latest
   ```

2. **Deploy Cloud Run Jobs**:
   ```bash
   # Deploy Level 0 job
   gcloud run jobs replace cloud-run/jobs/level0-surface.yaml --region us-central1
   
   # Deploy Level 1 job
   gcloud run jobs replace cloud-run/jobs/level1-buzz.yaml --region us-central1
   
   # Deploy Level 2 job
   gcloud run jobs replace cloud-run/jobs/level2-active.yaml --region us-central1
   ```

3. **Update backend configuration** to use the new job names and tier system.

## Monitoring and Logging

- Cloud Run Job logs are available in Google Cloud Logging
- Scan duration and resource usage can be monitored via Cloud Run metrics
- Failed scans are automatically retried with exponential backoff

## Security Considerations

- All scans are non-destructive and safe for production environments
- Rate limiting prevents abuse (max 3 concurrent scans per user)
- HMAC signature verification ensures callback authenticity
- Artifacts are automatically cleaned up after 30 days

## Troubleshooting

### Common Issues

1. **Job execution fails**: Check IAM permissions and environment variables
2. **Callback not received**: Verify CALLBACK_URL and CALLBACK_SECRET
3. **Artifacts not uploaded**: Check storage permissions and bucket configuration
4. **Scan timeout**: Increase job timeout in Cloud Run configuration

### Debug Commands

```bash
# Check job status
gcloud run jobs executions list --job=thandev-surface --region=us-central1

# View job logs
gcloud run jobs executions describe <execution-id> --region=us-central1

# Test job execution
gcloud run jobs execute thandev-surface --region=us-central1 --args="--help"
```




