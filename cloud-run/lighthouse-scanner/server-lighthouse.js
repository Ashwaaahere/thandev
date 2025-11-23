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

// In-memory job storage
const jobs = new Map();

// Generate unique job ID
function generateJobId() {
  return `lighthouse_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

// Real Lighthouse scan function with proper error handling
async function runRealLighthouseScan(url, device = 'desktop') {
  let browser;
  
  try {
    console.log(`Starting Lighthouse scan for ${url} (${device})`);
    
    // Launch Puppeteer with optimized settings for Cloud Run
    browser = await puppeteer.launch({
      headless: 'new',
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
        '--disable-extensions',
        '--disable-plugins',
        '--disable-images',
        '--disable-javascript',
        '--disable-default-apps',
        '--disable-sync',
        '--disable-translate',
        '--hide-scrollbars',
        '--mute-audio',
        '--no-default-browser-check',
        '--no-pings',
        '--password-store=basic',
        '--use-mock-keychain',
        '--disable-background-networking',
        '--disable-client-side-phishing-detection',
        '--disable-component-extensions-with-background-pages',
        '--disable-default-apps',
        '--disable-hang-monitor',
        '--disable-prompt-on-repost',
        '--disable-sync-preferences',
        '--metrics-recording-only',
        '--no-first-run',
        '--safebrowsing-disable-auto-update',
        '--enable-automation',
        '--password-store=basic',
        '--use-mock-keychain'
      ],
      ignoreDefaultArgs: ['--disable-extensions'],
      timeout: 60000
    });

    console.log('Browser launched successfully');

    const page = await browser.newPage();
    
    // Set viewport based on device
    if (device === 'mobile') {
      await page.setViewport({ width: 375, height: 667, deviceScaleFactor: 2 });
    } else {
      await page.setViewport({ width: 1280, height: 720, deviceScaleFactor: 1 });
    }

    console.log(`Navigating to ${url}`);
    
    // Navigate to the page with proper error handling
    await page.goto(url, { 
      waitUntil: 'domcontentloaded',
      timeout: 30000 
    });

    console.log('Page loaded, taking screenshot');
    
    // Take screenshot
    const screenshot = await page.screenshot({
      type: 'png',
      fullPage: true,
      encoding: 'base64'
    });

    console.log('Screenshot taken, running Lighthouse');

    // Dynamic import for Lighthouse ES module
    const { default: lighthouse } = await import('lighthouse');
    
    const options = {
      logLevel: 'error',
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

    console.log('Running Lighthouse audit');
    
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
      },
    });

    console.log('Lighthouse audit completed');

    // Extract performance data
    const lhr = runnerResult.lhr;
    const performance = lhr.categories.performance.score * 100;
    
    // Extract Core Web Vitals
    const metrics = {};
    const audits = lhr.audits;
    
    if (audits['first-contentful-paint']) {
      metrics.firstContentfulPaint = audits['first-contentful-paint'].numericValue;
    }
    if (audits['largest-contentful-paint']) {
      metrics.largestContentfulPaint = audits['largest-contentful-paint'].numericValue;
    }
    if (audits['first-meaningful-paint']) {
      metrics.firstMeaningfulPaint = audits['first-meaningful-paint'].numericValue;
    }
    if (audits['speed-index']) {
      metrics.speedIndex = audits['speed-index'].numericValue;
    }
    if (audits['cumulative-layout-shift']) {
      metrics.cumulativeLayoutShift = audits['cumulative-layout-shift'].numericValue;
    }
    if (audits['total-blocking-time']) {
      metrics.totalBlockingTime = audits['total-blocking-time'].numericValue;
    }
    if (audits['interactive']) {
      metrics.interactive = audits['interactive'].numericValue;
    }

    // Extract opportunities
    const opportunities = [];
    const opportunityAudits = [
      'unused-css-rules',
      'unused-javascript',
      'render-blocking-resources',
      'unused-css-rules',
      'efficient-animated-content',
      'preload-lcp-image',
      'uses-responsive-images',
      'offscreen-images',
      'unminified-css',
      'unminified-javascript',
      'uses-optimized-images',
      'uses-webp-images',
      'uses-text-compression',
      'uses-rel-preconnect',
      'uses-rel-preload',
      'font-display',
      'critical-request-chains',
      'uses-long-cache-ttl',
      'total-byte-weight',
      'uses-http2'
    ];

    opportunityAudits.forEach(auditId => {
      const audit = audits[auditId];
      if (audit && audit.score !== null && audit.score < 0.9) {
        opportunities.push({
          id: auditId,
          title: audit.title,
          description: audit.description,
          score: audit.score,
          displayValue: audit.displayValue || audit.details?.overallSavingsMs ? `Est. savings of ${audit.details.overallSavingsMs} ms` : 'Potential savings available'
        });
      }
    });

    // Extract diagnostics
    const diagnostics = [];
    const diagnosticAudits = [
      'render-blocking-resources',
      'mainthread-work-breakdown',
      'long-tasks',
      'dom-size',
      'efficient-animated-content',
      'duplicated-javascript',
      'legacy-javascript',
      'viewport',
      'color-contrast',
      'image-alt',
      'label',
      'link-name',
      'meta-description',
      'document-title',
      'html-has-lang',
      'html-lang-valid',
      'is-crawlable',
      'robots-txt',
      'canonical',
      'hreflang',
      'plugins',
      'deprecations',
      'console-errors',
      'errors-in-console',
      'no-vulnerable-libraries',
      'csp-xss',
      'external-anchors-use-rel-noopener',
      'no-document-write',
      'no-mixed-content',
      'no-unload-listeners',
      'notification-on-start',
      'password-inputs-can-be-pasted-into',
      'image-aspect-ratio',
      'is-on-https',
      'uses-http2',
      'uses-passive-event-listeners'
    ];

    diagnosticAudits.forEach(auditId => {
      const audit = audits[auditId];
      if (audit && audit.score !== null) {
        diagnostics.push({
          id: auditId,
          title: audit.title,
          description: audit.description,
          score: audit.score,
          displayValue: audit.displayValue || 'Check required'
        });
      }
    });

    console.log('Data extraction completed');

    return {
      success: true,
      url: url,
      device: device,
      timestamp: new Date().toISOString(),
      performance: Math.round(performance),
      metrics: metrics,
      opportunities: opportunities.slice(0, 10), // Limit to top 10
      diagnostics: diagnostics.slice(0, 10), // Limit to top 10
      screenshot: `data:image/png;base64,${screenshot}`
    };

  } catch (error) {
    console.error('Lighthouse scan error:', error);
    throw error;
  } finally {
    if (browser) {
      await browser.close();
      console.log('Browser closed');
    }
  }
}

// POST /run - Start a new scan
app.post('/run', async (req, res) => {
  try {
    const { url, device = 'desktop', category = 'performance' } = req.body;

    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    // Validate URL format
    try {
      new URL(url);
    } catch {
      return res.status(400).json({ error: 'Invalid URL format' });
    }

    const jobId = generateJobId();
    
    // Store job in memory
    jobs.set(jobId, {
      id: jobId,
      url: url,
      device: device,
      category: category,
      status: 'running',
      createdAt: new Date().toISOString(),
      progress: 0
    });

    // Start scan in background
    runRealLighthouseScan(url, device)
      .then(result => {
        const job = jobs.get(jobId);
        if (job) {
          job.status = 'completed';
          job.progress = 100;
          job.completedAt = new Date().toISOString();
          job.result = result;
          jobs.set(jobId, job);
        }
      })
      .catch(error => {
        console.error('Scan failed:', error);
        const job = jobs.get(jobId);
        if (job) {
          job.status = 'failed';
          job.error = error.message;
          jobs.set(jobId, job);
        }
      });

    res.json({
      success: true,
      jobId: jobId,
      message: 'Lighthouse scan initiated',
      estimatedDuration: '30-60 seconds'
    });

  } catch (error) {
    console.error('Error starting scan:', error);
    res.status(500).json({ error: 'Failed to start scan' });
  }
});

// GET /status/:jobId - Get scan status
app.get('/status/:jobId', (req, res) => {
  const { jobId } = req.params;
  const job = jobs.get(jobId);

  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }

  res.json(job);
});

// GET /health - Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    version: '3.0.0-real-lighthouse'
  });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Lighthouse scanner running on port ${PORT}`);
  console.log(`Version: 3.0.0-real-lighthouse`);
});

module.exports = app;



