# Vercel Deployment Checklist

## ✅ Pre-Deployment Verification

### 1. Build Configuration
- ✅ `package.json` - Valid with build script
- ✅ `next.config.mjs` - Webpack aliases configured
- ✅ `tsconfig.json` - Path aliases configured (`@/*`)
- ✅ `vercel.json` - Framework configuration present

### 2. Required Files
- ✅ `lib/auth.ts` - NextAuth configuration
- ✅ `lib/cloud-run.ts` - Cloud Run utilities
- ✅ All API routes using `@/lib/*` imports

### 3. Build Status
- ✅ Local build: **SUCCESSFUL**
- ✅ No module resolution errors
- ✅ All pages generated correctly

### 4. Configuration Files
- ✅ `next.config.mjs` - Webpack aliases for `@/lib`, `@/components`, `@/app`
- ✅ `tsconfig.json` - TypeScript path mapping configured
- ✅ `vercel.json` - Framework detection configured

---

## 🔧 Required Environment Variables for Vercel

### Authentication (NextAuth.js)
```
GITHUB_ID=your_github_oauth_app_client_id
GITHUB_SECRET=your_github_oauth_app_client_secret
NEXTAUTH_SECRET=your_random_secret_key_min_32_chars
NEXTAUTH_URL=https://your-app.vercel.app
```

### Backend API
```
NEXT_PUBLIC_API_BASE=https://thandev-backend.fly.dev
# Or your backend URL
```

### Google Cloud (if using Cloud Run)
```
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_REGION=us-central1
GCS_BUCKET=your-bucket-name
```

### Optional
```
SENTRY_DSN=your_sentry_dsn (optional)
```

---

## 📋 Vercel Deployment Steps

### 1. Connect Repository
- Go to [Vercel Dashboard](https://vercel.com/dashboard)
- Click "Add New Project"
- Import from GitHub: `Ashwaaahere/thandev`
- Select the `frontend` folder as root directory

### 2. Configure Build Settings
- **Framework Preset:** Next.js (auto-detected)
- **Root Directory:** `frontend` (if deploying from monorepo)
- **Build Command:** `npm run build` (default)
- **Output Directory:** `.next` (default)
- **Install Command:** `npm install` (default)

### 3. Set Environment Variables
Add all required environment variables in Vercel dashboard:
- Go to Project Settings → Environment Variables
- Add each variable for Production, Preview, and Development

### 4. Deploy
- Click "Deploy"
- Monitor build logs
- Check for any errors

---

## 🔍 Build Verification

### Expected Build Output
```
✓ Compiled successfully
✓ Linting and checking validity of types
✓ Collecting page data
✓ Generating static pages
✓ Build completed
```

### Common Issues & Solutions

#### Issue: Module not found `@/lib/auth`
**Solution:** ✅ Fixed - Webpack aliases configured in `next.config.mjs`

#### Issue: Dynamic server usage warnings
**Status:** ✅ Expected - API routes are dynamic by design

#### Issue: Environment variables missing
**Solution:** Add all required env vars in Vercel dashboard

---

## ✅ Post-Deployment Checks

1. **Health Check**
   - Visit: `https://your-app.vercel.app`
   - Should load without errors

2. **API Routes**
   - Test: `https://your-app.vercel.app/api/auth/[...nextauth]`
   - Should not return 500 errors

3. **Authentication**
   - Test GitHub OAuth login
   - Verify session creation

4. **Build Logs**
   - Check Vercel dashboard for build success
   - Verify no module resolution errors

---

## 📝 Current Status

### ✅ Ready for Deployment
- Build configuration: **CORRECT**
- File structure: **COMPLETE**
- Dependencies: **INSTALLED**
- Local build: **SUCCESSFUL**

### ⚠️ Action Required
1. Set environment variables in Vercel dashboard
2. Configure GitHub OAuth app
3. Set `NEXTAUTH_URL` to your Vercel domain

---

## 🔗 Useful Links

- [Vercel Dashboard](https://vercel.com/dashboard)
- [Next.js Deployment Docs](https://nextjs.org/docs/deployment)
- [NextAuth.js Configuration](https://next-auth.js.org/configuration/options)
- [GitHub OAuth App Setup](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)

---

**Last Updated:** $(date)
**Status:** Ready for Vercel Deployment

