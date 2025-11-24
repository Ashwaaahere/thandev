# Fix: "Failed to initiate security scan" Error

## Problem
The security scan is failing with "Failed to initiate security scan" because the frontend cannot connect to the backend.

## Root Cause
The `NEXT_PUBLIC_API_BASE` environment variable is not set in Vercel, so the frontend is trying to connect to `http://localhost:8000` which doesn't work in production.

## Solution: Set Backend URL in Vercel

### Step 1: Find Your Backend URL

Your backend is deployed on Fly.io. Find your backend URL:

```bash
# If you have fly CLI
fly status -a thandev-backend

# Or check in Fly.io dashboard
# The URL will be: https://thandev-backend.fly.dev (or your app name)
```

### Step 2: Set Environment Variable in Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project (`thandev`)
3. Go to **Settings** → **Environment Variables**
4. Add a new environment variable:
   - **Name**: `NEXT_PUBLIC_API_BASE`
   - **Value**: `https://thandev-backend.fly.dev` (replace with your actual backend URL)
   - **Environment**: Select all (Production, Preview, Development)
5. Click **Save**

### Step 3: Redeploy

After setting the environment variable, you need to redeploy:

1. Go to **Deployments** tab
2. Click the **⋯** menu on the latest deployment
3. Click **Redeploy**

Or trigger a new deployment:
```bash
# If you have Vercel CLI
vercel --prod
```

### Step 4: Verify

After redeployment:
1. Open your app: `https://thandev.vercel.app`
2. Try starting a security scan
3. Check browser console (F12) for any errors
4. The error should now show more details if there are other issues

## Alternative: Quick Test

To verify the backend URL is correct, test it directly:

```bash
# Test backend health
curl https://thandev-backend.fly.dev/health

# Test security scan endpoint (should return an error about missing URL, not connection error)
curl -X POST https://thandev-backend.fly.dev/api/security-scan \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "tier": "level1"}'
```

If these commands work, your backend is accessible and the issue is just the frontend configuration.

## Troubleshooting

### Error: "Cannot connect to backend"
- **Check**: Is `NEXT_PUBLIC_API_BASE` set in Vercel?
- **Check**: Did you redeploy after setting the variable?
- **Check**: Is the backend URL correct? (no trailing slash)

### Error: "Backend request timed out"
- **Check**: Is the backend running?
- **Check**: Can you access the backend URL directly in a browser?
- **Check**: Are there any firewall rules blocking access?

### Error: "Backend returned 500"
- This means the frontend can connect, but the backend has an error
- Check backend logs: `fly logs -a thandev-backend`
- See `SECURITY_SCAN_TROUBLESHOOTING.md` for backend issues

## Environment Variables Checklist

Make sure these are set in Vercel:

- [ ] `NEXT_PUBLIC_API_BASE` = `https://thandev-backend.fly.dev` (your backend URL)
- [ ] `NEXTAUTH_SECRET` = (your NextAuth secret)
- [ ] `NEXTAUTH_URL` = `https://thandev.vercel.app`
- [ ] `GITHUB_CLIENT_ID` = (if using GitHub auth)
- [ ] `GITHUB_CLIENT_SECRET` = (if using GitHub auth)

## After Fixing

Once `NEXT_PUBLIC_API_BASE` is set correctly:
1. The frontend will be able to connect to the backend
2. Security scans should start successfully
3. If there are still errors, they will be more specific (e.g., Cloud Run configuration issues)
4. Check `SECURITY_SCAN_TROUBLESHOOTING.md` for backend-specific issues

