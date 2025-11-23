require('dotenv').config();
const express = require('express');
const puppeteer = require('puppeteer');
const cors = require('cors');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || 8080;

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json({ limit: '10mb' }));

// In-memory job storage (in production, use Redis or database)
const jobs = new Map();

// Generate unique job ID
function generateJobId() {
  return `lighthouse_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Professional Lighthouse scan function with real data
async function runProfessionalLighthouseScan(url, device = 'desktop') {
  let browser;
  
  try {
    // Launch Puppeteer with the pre-installed Chromium
    browser = await puppeteer.launch({
      headless: true,
      executablePath: '/usr/bin/chromium-browser',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--single-process',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
      ],
    });

    const page = await browser.newPage();
    
    // Set viewport based on device
    if (device === 'mobile') {
      await page.setViewport({ width: 375, height: 667, deviceScaleFactor: 2 });
    } else {
      await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
    }

    // Navigate to the page
    await page.goto(url, { 
      waitUntil: 'networkidle0',
      timeout: 30000 
    });

    // Take screenshot
    const screenshot = await page.screenshot({
      type: 'png',
      fullPage: true,
      encoding: 'base64'
    });

    // Dynamic import for Lighthouse ES module
    const { default: lighthouse } = await import('lighthouse');
    
    const options = {
      logLevel: 'info',
      output: 'json',
      onlyCategories: ['performance'],
      port: new URL(browser.wsEndpoint()).port,
      emulatedFormFactor: device,
      throttling: {
        rttMs: 40,
        throughputKbps: 10240,
        cpuSlowdownMultiplier: 1,
        requestLatencyMs: 0,
        downloadThroughputKbps: 0,
        uploadThroughputKbps: 0,
      },
    };

    const runnerResult = await lighthouse(url, options, {
      extends: 'lighthouse:default',
      settings: {
        formFactor: device,
        screenEmulation: {
          mobile: device === 'mobile',
          width: device === 'mobile' ? 375 : 1280,
          height: device === 'mobile' ? 667 : 720,
          deviceScaleFactor: device === 'mobile' ? 2 : 1,
          disabled: false,
        },
        throttlingMethod: 'simulate',
        throttling: device === 'mobile' ? 
          { rttMs: 150, throughputKbps: 1638.4, cpuSlowdownMultiplier: 4 } :
          { rttMs: 40, throughputKbps: 10240, cpuSlowdownMultiplier: 1 },
        onlyCategories: ['performance'],
      },
    });

    if (!runnerResult) {
      throw new Error('Lighthouse scan failed to generate results');
    }

    // Extract performance data
    const performanceScore = runnerResult.lhr.categories.performance ? 
      Math.round(runnerResult.lhr.categories.performance.score * 100) : 0;
    
    const metrics = {};
    const opportunities = [];
    const diagnostics = [];

    if (runnerResult.lhr.audits) {
      // Core Web Vitals and other key metrics
      const metricAudits = [
        'first-contentful-paint', 'largest-contentful-paint', 'first-meaningful-paint',
        'speed-index', 'cumulative-layout-shift', 'total-blocking-time', 'interactive'
      ];
      
      metricAudits.forEach(id => {
        if (runnerResult.lhr.audits[id]) {
          const audit = runnerResult.lhr.audits[id];
          const key = id.replace(/-/g, '');
          metrics[key] = audit.numericValue || 0;
        }
      });

      // Opportunities
      const opportunityAudits = [
        'unused-css-rules', 'unused-javascript', 'render-blocking-resources',
        'efficient-animated-content', 'uses-responsive-images', 'uses-optimized-images'
      ];
      
      opportunityAudits.forEach(id => {
        const audit = runnerResult.lhr.audits[id];
        if (audit && audit.score !== 1 && audit.details && audit.details.type === 'opportunity') {
          opportunities.push({
            id: audit.id,
            title: audit.title,
            description: audit.description,
            score: audit.score,
            displayValue: audit.displayValue || 'Potential savings available',
          });
        }
      });

      // Diagnostics
      const diagnosticAudits = [
        'mainthread-work-breakdown', 'long-tasks', 'dom-size',
        'critical-request-chains', 'user-timings'
      ];
      
      diagnosticAudits.forEach(id => {
        const audit = runnerResult.lhr.audits[id];
        if (audit && audit.score !== 1) {
          diagnostics.push({
            id: audit.id,
            title: audit.title,
            description: audit.description,
            score: audit.score,
            displayValue: audit.displayValue || 'Analysis available',
          });
        }
      });
    }

    return {
      success: true,
      url,
      device,
      timestamp: new Date().toISOString(),
      performance: performanceScore,
      metrics: {
        firstContentfulPaint: metrics.firstcontentfulpaint || 0,
        largestContentfulPaint: metrics.largestcontentfulpaint || 0,
        firstMeaningfulPaint: metrics.firstmeaningfulpaint || 0,
        speedIndex: metrics.speedindex || 0,
        cumulativeLayoutShift: metrics.cumulativelayoutshift || 0,
        totalBlockingTime: metrics.totalblockingtime || 0,
        interactive: metrics.interactive || 0,
      },
      opportunities,
      diagnostics,
      screenshot: `data:image/png;base64,${screenshot}`,
    };

  } catch (error) {
    console.error('Lighthouse scan error:', error);
    throw error;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
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
    runProfessionalLighthouseScan(url, device)
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
        console.error('Scan error:', error);
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
      message: 'Professional Lighthouse scan initiated',
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
    version: '3.0.0-professional',
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
  console.log(`Professional Lighthouse scanner running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});






