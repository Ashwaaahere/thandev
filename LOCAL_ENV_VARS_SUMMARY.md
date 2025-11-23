# Local Environment Variables Summary

## ✅ Found Your Local Setup

Your local `.env.local` file uses these variable names:

### GitHub OAuth (Local)
```
GITHUB_ID=<your_client_id>
GITHUB_SECRET=<your_client_secret>
```

### NextAuth (Local)
```
NEXTAUTH_SECRET=<your_secret>
NEXTAUTH_URL=http://localhost:3000
```

---

## 🔧 For Vercel Deployment

You have **TWO options** (both work because the code supports both):

### Option 1: Use Same Names as Local (Recommended)
```
GITHUB_ID=<same_value_as_local>
GITHUB_SECRET=<same_value_as_local>
NEXTAUTH_SECRET=<same_value_as_local>
NEXTAUTH_URL=https://thandev.vercel.app
```

### Option 2: Use GitHub OAuth App Names
```
GITHUB_CLIENT_ID=0v23L14BVdQ63blK2KaM7
GITHUB_CLIENT_SECRET=<your_secret_from_github>
NEXTAUTH_SECRET=<your_secret>
NEXTAUTH_URL=https://thandev.vercel.app
```

---

## 📋 Quick Copy-Paste for Vercel

Since your local setup uses `GITHUB_ID` and `GITHUB_SECRET`, you can use the **exact same variable names** in Vercel:

| Variable Name | Value |
|--------------|-------|
| `GITHUB_ID` | (copy from your local `.env.local`) |
| `GITHUB_SECRET` | (copy from your local `.env.local`) |
| `NEXTAUTH_SECRET` | (copy from your local `.env.local`) |
| `NEXTAUTH_URL` | `https://thandev.vercel.app` |

---

## ✅ Why This Works

The code in `frontend/lib/auth.ts` supports **both naming conventions**:

```typescript
// Supports both:
const githubClientId = process.env.GITHUB_CLIENT_ID || process.env.GITHUB_ID
const githubClientSecret = process.env.GITHUB_CLIENT_SECRET || process.env.GITHUB_SECRET
```

So you can use:
- ✅ `GITHUB_ID` / `GITHUB_SECRET` (what you're using locally)
- ✅ `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` (alternative)

---

## 🎯 Recommendation

**Use the same variable names as your local setup** (`GITHUB_ID` and `GITHUB_SECRET`) to keep things consistent.

Just copy the values from your local `.env.local` file to Vercel, and change `NEXTAUTH_URL` to `https://thandev.vercel.app`.

---

**Last Updated:** 2025-01-27
**Status:** Ready to copy to Vercel

