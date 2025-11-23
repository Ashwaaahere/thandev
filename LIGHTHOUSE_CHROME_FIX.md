# Lighthouse Chrome Path Fix

## 🔴 Problem

Performance scans were failing with:
```
Lighthouse failed: Runtime error encountered: The CHROME_PATH environment variable must be set to a Chrome/Chromium executable no older than Chrome stable.
```

## 🔍 Root Cause

1. **Lighthouse installed but Chrome missing**: The Dockerfile installed Lighthouse via npm, but didn't install Chrome/Chromium
2. **CHROME_PATH not set**: Lighthouse couldn't find Chrome because the environment variable wasn't set
3. **Chrome dependencies missing**: Even if Chrome was installed, required system libraries were missing

## ✅ Fix Applied

### 1. Updated `Dockerfile`
- **Added Chrome installation**: Installed Google Chrome Stable via official repository
- **Added Chrome dependencies**: Installed all required system libraries (libgbm1, libnss3, etc.)
- **Set CHROME_PATH environment variable**: `ENV CHROME_PATH=/usr/bin/google-chrome-stable`

### 2. Updated `performance.py`
- **Explicit Chrome path**: Get `CHROME_PATH` from environment or use default
- **Pass environment to subprocess**: Set `CHROME_PATH` in subprocess environment
- **Added Chrome flags**: `--no-sandbox --disable-gpu` for headless operation in containers

## 📋 Changes Made

### Dockerfile
```dockerfile
# Install Chrome and dependencies
RUN apt-get update && apt-get install -y \
    ... (all Chrome dependencies) ...
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Set Chrome path for Lighthouse
ENV CHROME_PATH=/usr/bin/google-chrome-stable
```

### performance.py
```python
# Get Chrome path from environment
chrome_path = os.getenv("CHROME_PATH", "/usr/bin/google-chrome-stable")

# Set CHROME_PATH in subprocess environment
env = os.environ.copy()
env["CHROME_PATH"] = chrome_path

# Run Lighthouse with environment
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
```

## 🚀 Next Steps

1. **Redeploy backend on Fly.io:**
   ```bash
   cd backend
   fly deploy
   ```

2. **Verify Chrome is installed:**
   - Check logs: `fly logs -a thandev-backend`
   - Look for successful startup (no Chrome errors)

3. **Test performance scan:**
   - Try initiating a performance scan from the frontend
   - Should no longer get "CHROME_PATH" error
   - Scan should complete successfully

## 🔍 Verification

After deployment, you can verify Chrome is available by:

```bash
# SSH into the container (if possible)
fly ssh console -a thandev-backend

# Check Chrome installation
which google-chrome-stable
google-chrome-stable --version

# Check environment variable
echo $CHROME_PATH
```

---

**Status:** Fixed - Ready for deployment
**Date:** 2025-01-27

