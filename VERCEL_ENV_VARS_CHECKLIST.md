# Vercel Environment Variables Checklist

## ⚠️ REQUIRED Variables for NextAuth

You MUST set these in Vercel Dashboard → Settings → Environment Variables:

### 1. NEXTAUTH_SECRET
```
Name: NEXTAUTH_SECRET
Value: X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=
Environment: Production, Preview, Development (select all)
```

### 2. NEXTAUTH_URL ⚠️ REQUIRED
```
Name: NEXTAUTH_URL
Value: https://thandev.vercel.app
Environment: Production, Preview, Development (select all)
```

**⚠️ IMPORTANT:** `NEXTAUTH_URL` MUST be set for NextAuth to work correctly in production.

---

## Complete Environment Variables List

### Authentication (NextAuth.js)
```
# GitHub OAuth - Use GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET (matches GitHub OAuth app)
GITHUB_CLIENT_ID=0v23L14BVdQ63blK2KaM7
GITHUB_CLIENT_SECRET=your_github_oauth_app_client_secret
# Alternative (also supported): GITHUB_ID / GITHUB_SECRET

NEXTAUTH_SECRET=X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=
NEXTAUTH_URL=https://thandev.vercel.app
```

### Backend API
```
NEXT_PUBLIC_API_BASE=https://thandev-backend.fly.dev
```

### Optional
```
SENTRY_DSN=your_sentry_dsn (optional)
```

---

## How to Set in Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project: `thandev`
3. Go to **Settings** → **Environment Variables**
4. Click **Add New**
5. Enter each variable:
   - **Name:** (e.g., `NEXTAUTH_URL`)
   - **Value:** (e.g., `https://thandev.vercel.app`)
   - **Environment:** Select Production, Preview, Development (or all)
6. Click **Save**
7. Repeat for each variable
8. **Redeploy** your application after adding variables

---

## Verification

After setting variables, verify:

1. ✅ All variables are listed in Vercel Dashboard
2. ✅ `NEXTAUTH_URL` is set to `https://thandev.vercel.app`
3. ✅ `NEXTAUTH_SECRET` is set
4. ✅ Redeploy completed successfully
5. ✅ Test authentication at: `https://thandev.vercel.app/api/auth/signin`

---

## Quick Copy-Paste for Vercel

When adding variables in Vercel, use these exact values:

| Variable Name | Value |
|--------------|-------|
| `NEXTAUTH_URL` | `https://thandev.vercel.app` |
| `NEXTAUTH_SECRET` | `X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=` |
| `GITHUB_CLIENT_ID` | `0v23L14BVdQ63blK2KaM7` (from your GitHub OAuth app) |
| `GITHUB_CLIENT_SECRET` | (your GitHub OAuth client secret - reveal and copy from GitHub) |
| `NEXT_PUBLIC_API_BASE` | `https://thandev-backend.fly.dev` |

**Note:** The code supports both `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` (recommended) and `GITHUB_ID`/`GITHUB_SECRET` (legacy). Use the `GITHUB_CLIENT_*` names to match your GitHub OAuth app.

---

**Last Updated:** 2025-01-27
**Status:** Ready for Vercel deployment

