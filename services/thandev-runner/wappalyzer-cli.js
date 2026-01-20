#!/usr/bin/env node
/**
 * Wappalyzer CLI wrapper - tries to use wappalyzer v6.x driver.js
 * Falls back to basic tech detection if wappalyzer is not available
 */
const url = process.argv[2];
const format = process.argv.includes('--json') ? 'json' : 'text';

if (!url) {
  console.error('Usage: wappalyzer-cli.js <url> [--json]');
  process.exit(1);
}

(async () => {
  try {
    // Try to use wappalyzer v6.x driver
    // Try multiple locations for the module
    let Wappalyzer;
    const modulePaths = [
      'wappalyzer',  // Try global require first
      '/usr/lib/node_modules/wappalyzer',
      '/usr/local/lib/node_modules/wappalyzer',
    ];
    
    let moduleFound = false;
    let moduleError = null;
    for (const modulePath of modulePaths) {
      try {
        // Clear require cache to avoid stale modules
        delete require.cache[require.resolve(modulePath)];
        Wappalyzer = require(modulePath);
        moduleFound = true;
        break;
    } catch (e) {
        moduleError = e.message;
        // Continue to next path
        continue;
      }
    }
    
    if (!moduleFound) {
      // wappalyzer not available, return empty result
      const errorMsg = moduleError || 'wappalyzer library not found in any expected location';
      console.log(JSON.stringify({
        url: url,
        technologies: [],
        error: errorMsg,
      }));
      process.exit(0);
    }

    const options = {
      debug: false,
      delay: 500,
      headers: {},
      maxDepth: 1,
      maxUrls: 1,
      maxWait: 10000,  // Increased wait time for JS-rendered content
      recursive: false,
      probe: true,
      proxy: false,
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
      htmlMaxCols: 2000,
      htmlMaxRows: 2000,
      noScripts: false,
      noRedirect: false,
    };

    const wappalyzer = new Wappalyzer(options);
    await wappalyzer.init();

    const site = await wappalyzer.open(url, options);
    const results = await site.analyze();
    await wappalyzer.destroy();

    if (format === 'json') {
      console.log(JSON.stringify({
        url: results.url || url,
        technologies: results.technologies || [],
      }, null, 2));
    } else {
      // Text format
      if (results.technologies && results.technologies.length > 0) {
        results.technologies.forEach(tech => {
          console.log(`${tech.name}${tech.version ? ' ' + tech.version : ''}`);
        });
      }
    }

    process.exit(0);
  } catch (error) {
    // Log error to stderr for debugging, but return empty result to stdout
    console.error(`Wappalyzer error: ${error.message}`, error.stack);
    // Return empty result instead of failing
    console.log(JSON.stringify({
      url: url,
      technologies: [],
      error: error.message,
    }));
    process.exit(0); // Exit 0 so dependency scanner can continue
  }
})();
