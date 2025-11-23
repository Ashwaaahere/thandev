# 🔍 Scan Troubleshooting Guide

## ✅ Fixed Issues

### 1. Backend URL Configuration
- **Problem:** Frontend API routes were using `BACKEND_URL` (not set)
- **Fix:** Changed to `NEXT_PUBLIC_API_BASE` (already configured)
- **Files:** 
  - `frontend/app/api/security-scan/route.ts`
  - `frontend/app/api/performance-scan/route.ts`

---

## 🔧 Required Environment Variables

### Vercel (Frontend)
Make sure these are set in Vercel Dashboard → Settings → Environment Variables:

```
NEXT_PUBLIC_API_BASE=https://thandev-backend.fly.dev
NEXTAUTH_SECRET=<your_secret>
NEXTAUTH_URL=https://thandev.vercel.app
GITHUB_ID=<your_github_client_id>
GITHUB_SECRET=<your_github_client_secret>
```

### Fly.io (Backend)
Make sure these are set in Fly.io Dashboard → Secrets:

```
DATABASE_URL=<your_postgresql_url>
GCP_PROJECT_ID=<your_gcp_project_id>
GCP_REGION=us-central1
CLOUD_RUN_ENABLED=true
BACKEND_URL=https://thandev-backend.fly.dev
CALLBACK_SECRET=<your_callback_secret>
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "Failed to initiate security scan"
**Symptoms:**
- Error message when clicking scan button
- Network error in browser console

**Check:**
1. Is `NEXT_PUBLIC_API_BASE` set in Vercel?
2. Is backend accessible? Test: `curl https://thandev-backend.fly.dev/api/health`
3. Check browser console for CORS errors
4. Check Vercel function logs for errors

**Solution:**
- Verify `NEXT_PUBLIC_API_BASE` is set correctly
- Ensure backend is running and accessible
- Check CORS configuration in backend

---

### Issue 2: "Backend API failed"
**Symptoms:**
- Scan starts but immediately fails
- Error: "Backend API failed: ..."

**Check:**
1. Backend logs on Fly.io
2. Is backend endpoint `/api/security-scan` working?
3. Test backend directly: `curl -X POST https://thandev-backend.fly.dev/api/security-scan -H "Content-Type: application/json" -d '{"url":"https://example.com","tier":"level1"}'`

**Solution:**
- Check backend is running: `flyctl status`
- Check backend logs: `flyctl logs`
- Verify backend endpoints are working

---

### Issue 3: Scan starts but never completes
**Symptoms:**
- Scan shows "scanning" status
- Progress bar stuck
- No results after waiting

**Check:**
1. Is Cloud Run Job configured?
2. Is `CLOUD_RUN_ENABLED=true` in backend?
3. Are Cloud Run Jobs deployed?
4. Check backend logs for Cloud Run execution errors

**Solution:**
- Verify Cloud Run Jobs are deployed
- Check `GCP_PROJECT_ID` and `GCP_REGION` are set
- Verify `gcloud` CLI is available in backend container
- Check Cloud Run Job execution logs

---

### Issue 4: "ModuleNotFoundError: No module named 'psycopg2'"
**Symptoms:**
- Backend fails to start
- Database connection errors

**Fix:** ✅ Already fixed - `psycopg2-binary` added to requirements.txt

---

## 🧪 Testing Steps

### 1. Test Backend Health
```bash
curl https://thandev-backend.fly.dev/api/health
```
Should return: `{"status":"ok"}`

### 2. Test Security Scan Endpoint
```bash
curl -X POST https://thandev-backend.fly.dev/api/security-scan \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","tier":"level1","user_id":"test"}'
```
Should return: `{"jobId":"...","status":"queued",...}`

### 3. Test Frontend API Route
In browser console on Vercel app:
```javascript
fetch('/api/security-scan', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({url: 'https://example.com', tier: 'level1'})
}).then(r => r.json()).then(console.log)
```

### 4. Check Environment Variables
In Vercel Dashboard:
- Settings → Environment Variables
- Verify `NEXT_PUBLIC_API_BASE` is set
- Verify all NextAuth variables are set

---

## 📋 Debug Checklist

- [ ] `NEXT_PUBLIC_API_BASE` set in Vercel
- [ ] Backend is running on Fly.io
- [ ] Backend health endpoint responds
- [ ] Backend `/api/security-scan` endpoint works
- [ ] No CORS errors in browser console
- [ ] No network errors in browser console
- [ ] Backend logs show scan requests
- [ ] Cloud Run Jobs are deployed (if using)
- [ ] `CLOUD_RUN_ENABLED` is set correctly
- [ ] Database connection works

---

## 🔍 How to Check Logs

### Vercel (Frontend)
1. Go to Vercel Dashboard
2. Select your project
3. Go to **Deployments** → Click on latest deployment
4. Click **Functions** tab
5. Check function logs for errors

### Fly.io (Backend)
```bash
flyctl logs -a thandev-backend
```

Or in Fly.io Dashboard:
1. Go to your app
2. Click **Monitoring** → **Logs**

---

## 🎯 Next Steps After Fix

After fixing the backend URL:
1. ✅ Redeploy frontend (automatic after git push)
2. ✅ Verify `NEXT_PUBLIC_API_BASE` is set in Vercel
3. ✅ Test a scan from the UI
4. ✅ Check browser console for errors
5. ✅ Check backend logs for scan requests

---

**Last Updated:** 2025-01-27
**Status:** Backend URL fixed - verify environment variables

