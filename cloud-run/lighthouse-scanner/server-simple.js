const express = require('express');
const cors = require('cors');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || 8080;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// In-memory job storage
const jobs = new Map();

// Generate unique job ID
function generateJobId() {
  return `lighthouse_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Enhanced Mock Lighthouse scan function with realistic data and screenshot
async function runMockLighthouseScan(url, device = 'desktop') {
  // Simulate scan delay
  await new Promise(resolve => setTimeout(resolve, 2000));
  
  // Generate more realistic performance data based on URL
  const isGoogle = url.includes('google.com');
  const isExample = url.includes('example.com');
  const isLocal = url.includes('localhost') || url.includes('even.local');
  
  let basePerformance = 60;
  let baseFCP = 1000;
  let baseLCP = 2000;
  let baseCLS = 0.1;
  
  if (isGoogle) {
    basePerformance = 85;
    baseFCP = 600;
    baseLCP = 1500;
    baseCLS = 0.05;
  } else if (isExample) {
    basePerformance = 75;
    baseFCP = 800;
    baseLCP = 1800;
    baseCLS = 0.08;
  } else if (isLocal) {
    basePerformance = 70;
    baseFCP = 1200;
    baseLCP = 2200;
    baseCLS = 0.12;
  }
  
  // Add some realistic variance
  const performance = Math.min(100, Math.max(30, basePerformance + Math.floor(Math.random() * 20) - 10));
  const fcp = Math.max(200, baseFCP + Math.floor(Math.random() * 400) - 200);
  const lcp = Math.max(fcp + 200, baseLCP + Math.floor(Math.random() * 800) - 400);
  const cls = Math.max(0, Math.min(0.3, baseCLS + (Math.random() * 0.1) - 0.05));
  
  // Create a mock screenshot (1x1 pixel PNG in base64)
  const mockScreenshot = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
  
  return {
    success: true,
    url,
    device,
    timestamp: new Date().toISOString(),
    performance,
    metrics: {
      firstContentfulPaint: fcp,
      largestContentfulPaint: lcp,
      firstMeaningfulPaint: Math.floor(fcp + Math.random() * 300),
      speedIndex: Math.floor(lcp + Math.random() * 500),
      cumulativeLayoutShift: Math.round(cls * 1000) / 1000,
      totalBlockingTime: Math.floor(Math.random() * 200) + 50,
      interactive: Math.floor(lcp + Math.random() * 1000) + 500,
    },
    opportunities: [
      {
        id: 'unused-css-rules',
        title: 'Remove unused CSS',
        description: 'Remove unused CSS rules to reduce bytes consumed by network activity.',
        score: Math.random() * 0.3 + 0.7,
        displayValue: `Potential savings of ${Math.floor(Math.random() * 20) + 10} KiB`,
      },
      {
        id: 'unused-javascript',
        title: 'Remove unused JavaScript',
        description: 'Remove unused JavaScript to reduce bytes consumed by network activity.',
        score: Math.random() * 0.4 + 0.6,
        displayValue: `Potential savings of ${Math.floor(Math.random() * 30) + 15} KiB`,
      },
      {
        id: 'render-blocking-resources',
        title: 'Eliminate render-blocking resources',
        description: 'Resources are blocking the first paint of your page.',
        score: Math.random() * 0.4 + 0.6,
        displayValue: `Est. savings of ${Math.floor(Math.random() * 500) + 200} ms`,
      },
    ],
    diagnostics: [
      {
        id: 'render-blocking-resources',
        title: 'Eliminate render-blocking resources',
        description: 'Resources are blocking the first paint of your page.',
        score: Math.random() * 0.5 + 0.5,
        displayValue: `${Math.floor(Math.random() * 5) + 1} resources found`,
      },
      {
        id: 'mainthread-work-breakdown',
        title: 'Minimize main-thread work',
        description: 'Consider reducing the time spent parsing, compiling and executing JS.',
        score: Math.random() * 0.6 + 0.4,
        displayValue: `${Math.floor(Math.random() * 3) + 2} s`,
      },
      {
        id: 'long-tasks',
        title: 'Avoid long main-thread tasks',
        description: 'Lists the longest tasks on the main thread, useful for identifying what contributes to TBT.',
        score: Math.random() * 0.7 + 0.3,
        displayValue: `${Math.floor(Math.random() * 5) + 1} long tasks found`,
      },
    ],
    screenshot: mockScreenshot,
  };
}

// POST /run - Start a new Lighthouse scan
app.post('/run', async (req, res) => {
  try {
    const { url, device = 'desktop', category = 'performance' } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    // Validate URL
    try {
      new URL(url);
    } catch {
      return res.status(400).json({ error: 'Invalid URL format' });
    }

    const jobId = generateJobId();
    
    // Initialize job status
    jobs.set(jobId, {
      id: jobId,
      url,
      device,
      category,
      status: 'running',
      createdAt: new Date().toISOString(),
      progress: 0,
    });

    // Run scan asynchronously
    runMockLighthouseScan(url, device)
      .then(result => {
        jobs.set(jobId, {
          ...jobs.get(jobId),
          status: 'completed',
          progress: 100,
          completedAt: new Date().toISOString(),
          result,
        });
      })
      .catch(error => {
        jobs.set(jobId, {
          ...jobs.get(jobId),
          status: 'failed',
          progress: 100,
          completedAt: new Date().toISOString(),
          error: error.message,
        });
      });

    res.json({
      success: true,
      jobId,
      message: 'Lighthouse scan initiated',
      estimatedDuration: '30-60 seconds',
    });

  } catch (error) {
    console.error('Error starting Lighthouse scan:', error);
    res.status(500).json({
      error: 'Failed to start Lighthouse scan',
      details: error.message,
    });
  }
});

// GET /status/:jobId - Check scan status
app.get('/status/:jobId', (req, res) => {
  try {
    const { jobId } = req.params;
    const job = jobs.get(jobId);

    if (!job) {
      return res.status(404).json({ error: 'Job not found' });
    }

    res.json(job);

  } catch (error) {
    console.error('Error checking job status:', error);
    res.status(500).json({
      error: 'Failed to check job status',
      details: error.message,
    });
  }
});

// GET /health - Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    version: '1.0.0',
  });
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error('Unhandled error:', error);
  res.status(500).json({
    error: 'Internal server error',
    details: error.message,
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Lighthouse scanner running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

