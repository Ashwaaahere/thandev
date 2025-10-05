# Performance Scan Feature

This document describes the performance scan feature that has been added to the Thandev platform.

## Overview

The performance scan feature allows users to analyze website performance using Google Lighthouse technology. It provides comprehensive performance metrics, Core Web Vitals, optimization opportunities, and diagnostic information similar to PageSpeed Insights.

## Architecture

### Frontend (Next.js)
- **Performance Scanner Page**: `/dashboard/performance` - Main interface for initiating scans
- **Performance Report Page**: `/dashboard/performance-report/[jobId]` - Detailed results display
- **API Endpoint**: `/api/performance-scan` - Communicates with FastAPI backend

### Backend (FastAPI)
- **Performance Router**: `/api/performance-scan/` - Handles scan requests and status
- **Lighthouse Integration**: Uses Google Lighthouse CLI for performance analysis
- **Background Processing**: Scans run asynchronously with status polling

## Features

### Performance Scanner Interface
- URL input with validation
- Device selection (Desktop/Mobile)
- Real-time scan progress
- Scan history management
- Beautiful, modern UI with PageSpeed Insights-like design

### Performance Report
- **Overview Tab**: Performance score, Core Web Vitals, additional metrics
- **Opportunities Tab**: Optimization recommendations with detailed analysis
- **Diagnostics Tab**: Technical diagnostics and best practices
- **Interactive Elements**: Expandable sections, detailed metrics

### Core Web Vitals
- **Largest Contentful Paint (LCP)**: Loading performance
- **First Input Delay (FID)**: Interactivity
- **Cumulative Layout Shift (CLS)**: Visual stability

### Additional Metrics
- First Contentful Paint (FCP)
- Speed Index
- Total Blocking Time (TBT)
- Time to Interactive (TTI)
- First Meaningful Paint (FMP)

## API Endpoints

### Start Performance Scan
```http
POST /api/performance-scan/
Content-Type: application/json

{
  "url": "https://example.com",
  "device": "desktop",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**Response:**
```json
{
  "jobId": "uuid-string",
  "status": "started",
  "message": "Performance scan initiated"
}
```

### Get Scan Status
```http
GET /api/performance-scan/{jobId}
```

**Response:**
```json
{
  "jobId": "uuid-string",
  "status": "completed",
  "result": {
    "categories": {
      "performance": 85,
      "accessibility": 92,
      "bestPractices": 78,
      "seo": 90
    },
    "metrics": {
      "firstContentfulPaint": 1200,
      "largestContentfulPaint": 2100,
      "cumulativeLayoutShift": 0.05
    },
    "opportunities": [...],
    "diagnostics": [...]
  },
  "createdAt": "2024-01-01T00:00:00Z",
  "completedAt": "2024-01-01T00:01:30Z"
}
```

## Setup Instructions

### Backend Setup
1. Install Node.js and Lighthouse:
```bash
# Install Node.js (if not already installed)
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo bash -
sudo apt-get install -y nodejs

# Install Lighthouse globally
npm install -g lighthouse
```

2. Install Python dependencies:
```bash
cd backend
pip install -r requirements.txt
```

3. Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Access the performance scanner at: `http://localhost:3000/dashboard/performance`

## Docker Setup

The backend Dockerfile has been updated to include Node.js and Lighthouse:

```dockerfile
# Install Node.js and Lighthouse
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g lighthouse
```

## Testing

Run the test script to verify the functionality:

```bash
python test_performance_scan.py
```

This will:
1. Start a performance scan for example.com
2. Poll for results
3. Display the performance metrics and recommendations

## File Structure

```
frontend/
├── app/
│   ├── dashboard/
│   │   ├── performance/
│   │   │   └── page.tsx
│   │   └── performance-report/
│   │       └── [jobId]/
│   │           └── page.tsx
│   └── api/
│       └── performance-scan/
│           └── route.ts
├── components/
│   └── Dashboard/
│       ├── PerformanceScanClient.tsx
│       └── PerformanceReportClient.tsx
└── ...

backend/
├── app/
│   ├── routers/
│   │   └── performance.py
│   └── main.py
├── Dockerfile
└── requirements.txt
```

## Environment Variables

Set the backend URL in your frontend environment:

```bash
# .env.local
BACKEND_URL=http://localhost:8000
```

## Performance Considerations

- Scans run asynchronously to avoid blocking the API
- Results are cached in memory (use Redis for production)
- Lighthouse runs with optimized flags for faster execution
- Timeout set to 5 minutes for long-running scans

## Security Notes

- URL validation prevents malicious requests
- Scans run in isolated processes
- No persistent storage of sensitive data
- Rate limiting should be implemented for production

## Future Enhancements

- [ ] Screenshot capture and display
- [ ] Historical performance tracking
- [ ] Performance regression detection
- [ ] Custom performance budgets
- [ ] Integration with CI/CD pipelines
- [ ] Performance monitoring alerts
- [ ] Multi-page scanning
- [ ] Performance comparison tools
