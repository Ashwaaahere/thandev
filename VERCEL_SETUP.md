# Vercel Deployment Setup Guide

## ⚠️ IMPORTANT: Root Directory Configuration

Vercel does NOT support `rootDirectory` in `vercel.json`. You must configure it in the Vercel Dashboard.

### Steps to Fix:

1. **Go to Vercel Dashboard**
   - Visit: https://vercel.com/dashboard
   - Select your project: `thandev`

2. **Configure Root Directory**
   - Go to: **Settings** → **General**
   - Scroll to **Root Directory**
   - Click **Edit**
   - Select: `frontend`
   - Click **Save**

3. **Verify Build Settings**
   - **Framework Preset:** Next.js (auto-detected)
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `.next` (default)
   - **Install Command:** `npm install` (default)

4. **Set Environment Variables**
   Go to **Settings** → **Environment Variables** and add:
   ```
   GITHUB_ID=your_github_oauth_client_id
   GITHUB_SECRET=your_github_oauth_client_secret
   NEXTAUTH_SECRET=your_random_secret_32_chars_min
   NEXTAUTH_URL=https://your-app.vercel.app
   NEXT_PUBLIC_API_BASE=https://thandev-backend.fly.dev
   ```

5. **Redeploy**
   - After setting root directory, click **Redeploy** on the latest deployment
   - Or push a new commit to trigger auto-deployment

---

## ✅ Current Configuration

- ✅ `vercel.json` - Valid schema (no rootDirectory)
- ✅ `frontend/vercel.json` - Valid schema
- ✅ `frontend/next.config.mjs` - Webpack aliases configured
- ✅ `frontend/tsconfig.json` - Path aliases configured
- ✅ All required files present

---

## 🔧 Why rootDirectory Was Removed

The `rootDirectory` property is **not valid** in `vercel.json` schema. Vercel validates the JSON schema strictly, and this property causes build failures.

**Solution:** Configure the root directory in Vercel Dashboard (Settings → General → Root Directory) instead of in the JSON file.

---

**Last Updated:** $(date)

