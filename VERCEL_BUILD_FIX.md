# ⚠️ Vercel Build Error Fix

## 🔴 Problem

Vercel is building from a **Dependabot branch** (`dependabot/npm_and_yarn/frontend/next-16.0.0`) that upgraded Next.js to version 16.0.3.

However, `next-auth@4.24.11` only supports Next.js versions:
- `^12.2.5 || ^13 || ^14 || ^15`

**Next.js 16 is NOT supported by next-auth v4**, causing a peer dependency conflict.

---

## ✅ Solution

### Option 1: Configure Vercel to Build from `main` Branch (Recommended)

1. Go to **Vercel Dashboard** → Your Project → **Settings** → **Git**
2. Under **Production Branch**, make sure it's set to `main` (not `dependabot/...`)
3. Under **Ignored Build Step**, you can add:
   ```
   git diff HEAD^ HEAD --quiet ./
   ```
   This will skip builds if only Dependabot branches change.

### Option 2: Close/Dismiss the Dependabot PR

1. Go to GitHub → Pull Requests
2. Find the PR: `Bump next from 14.2.32 to 16.0.0`
3. Click **Close** or **Dismiss**
4. Add a comment: "Next.js 16 is not compatible with next-auth@4.24.11"

### Option 3: Upgrade next-auth (If Available)

Check if there's a newer version of next-auth that supports Next.js 16:
```bash
npm view next-auth versions --json
```

However, as of now, next-auth v4 does not support Next.js 16. You would need to:
- Wait for next-auth v5 (which may support Next.js 16)
- OR downgrade Next.js back to 14.x

---

## 🎯 Immediate Fix

**The quickest fix is to ensure Vercel builds from `main` branch, not Dependabot branches.**

### Steps:

1. **Vercel Dashboard** → Your Project → **Settings** → **Git**
2. **Production Branch**: Set to `main`
3. **Preview Deployments**: 
   - Option A: Disable preview deployments for Dependabot branches
   - Option B: Add to **Ignored Build Step**:
     ```
     git diff HEAD^ HEAD --quiet ./
     ```
4. **Save** and **Redeploy** from main branch

---

## 📋 Current State

- **Main branch**: Next.js 14.2.32 ✅ (compatible with next-auth@4.24.11)
- **Dependabot branch**: Next.js 16.0.3 ❌ (NOT compatible)

---

## 🔧 Alternative: Pin Next.js Version

To prevent future Dependabot upgrades, you can pin Next.js in `package.json`:

```json
{
  "dependencies": {
    "next": "^14.2.32"
  }
}
```

Or use an exact version:
```json
{
  "dependencies": {
    "next": "14.2.32"
  }
}
```

---

## ✅ Verification

After fixing, verify:

1. Vercel builds from `main` branch
2. Build succeeds without peer dependency errors
3. No more "ERESOLVE could not resolve" errors

---

**Last Updated:** 2025-01-27
**Status:** Action Required - Configure Vercel to build from main branch

