# NEXTAUTH_SECRET Setup Guide

## ⚠️ IMPORTANT: Correct Variable Name

The environment variable name is:
```
NEXTAUTH_SECRET
```

**NOT** `NEXT_AUTH_SECRET` (with underscore between NEXT and AUTH)

---

## 🔐 Generate a Secure Secret

### Method 1: Using OpenSSL (Recommended)
```bash
openssl rand -base64 32
```

### Method 2: Using Node.js
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

### Method 3: Online Generator
- Use a secure random string generator (minimum 32 characters)

---

## 📝 Generated Secret (for this project)

```
NEXTAUTH_SECRET=X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=
```

**⚠️ Security Note:** This secret is shown here for reference. In production, keep it secure and never commit it to version control.

---

## 🔧 Where to Set This Variable

### 1. Local Development (`.env.local`)
Create `frontend/.env.local`:
```bash
NEXTAUTH_SECRET=X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=
GITHUB_ID=your_github_oauth_client_id
GITHUB_SECRET=your_github_oauth_client_secret
NEXTAUTH_URL=http://localhost:3000
```

### 2. Vercel Deployment
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project
3. Go to **Settings** → **Environment Variables**
4. Add:
   - **Name:** `NEXTAUTH_SECRET`
   - **Value:** `X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=`
   - **Environment:** Production, Preview, Development (select all)
5. Click **Save**

### 3. Other Platforms
Set the environment variable `NEXTAUTH_SECRET` in your hosting platform's environment variable settings.

---

## ✅ Verification

After setting the variable, verify it's being read:

1. **Check NextAuth is using it:**
   - File: `frontend/lib/auth.ts`
   - Line 45: `secret: process.env.NEXTAUTH_SECRET`

2. **Test locally:**
   ```bash
   cd frontend
   npm run dev
   ```
   - Visit: http://localhost:3000/api/auth/signin
   - Should not show errors about missing secret

3. **Check Vercel build logs:**
   - Should not show warnings about `NEXTAUTH_SECRET`

---

## 🔗 Related Documentation

- [NextAuth.js Configuration](https://next-auth.js.org/configuration/options#secret)
- [NextAuth.js Environment Variables](https://next-auth.js.org/configuration/options#environment-variables)

---

**Last Updated:** 2025-01-27
**Status:** Ready for use

