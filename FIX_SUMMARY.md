# Root Cause Fix: Network Error to Backend

## Problem
Frontend showing "Network error: Cannot reach backend at http://localhost:8000" even though:
- Backend is running and accessible via curl
- CORS is properly configured
- All fetch calls use correct API_BASE

## Root Cause
**Content Security Policy (CSP)** in `next.config.mjs` was blocking connections to `http://localhost:8000`.

The `connect-src` directive only allowed:
- `'self'` (localhost:3000)
- Specific HTTPS domains

It did NOT allow `http://localhost:8000`, so the browser blocked all fetch requests.

## Fixes Applied

### 1. Updated CSP in `frontend/next.config.mjs`
**Line 145**: Added `http://localhost:8000` and `http://127.0.0.1:8000` to `connect-src`:
```javascript
"connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 https://thandev-backend.fly.dev ..."
```

### 2. Updated Cross-Origin-Resource-Policy
**Line 185**: Changed from `'same-origin'` to `'cross-origin'`:
```javascript
{
  key: 'Cross-Origin-Resource-Policy',
  value: 'cross-origin', // Allow cross-origin requests to backend
}
```

### 3. Enhanced CORS Configuration
**`backend/app/core/config.py`**: Added 127.0.0.1 variants:
```python
CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,https://thandev.com"
```

## Next Steps

1. **Restart Next.js dev server** (CSP changes require restart):
   ```bash
   # Stop current Next.js server (Ctrl+C)
   cd frontend
   npm run dev
   ```

2. **Restart FastAPI backend** (to pick up CORS changes):
   ```bash
   # Stop current backend (Ctrl+C)
   cd backend
   source .venv/bin/activate
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. **Hard refresh browser**:
   - Press `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
   - Or open DevTools → Right-click refresh → "Empty Cache and Hard Reload"

## Expected Result

After restarting both servers:
- ✅ Browser console shows: `API_BASE: http://localhost:8000`
- ✅ Browser console shows: `DEBUG: backend /health status: 200`
- ✅ Network tab shows successful requests to `http://localhost:8000/api/...`
- ✅ FastAPI logs show incoming requests
- ✅ Page loads project and scan data successfully
