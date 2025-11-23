# How to Ignore Dependabot Branches in Vercel

## 🎯 Quick Fix Using "Ignored Build Step"

Based on your Vercel Git settings page, here's how to prevent Dependabot branches from triggering builds:

### Step 1: Find "Ignored Build Step" Section
Scroll down on the Git settings page until you see the **"Ignored Build Step"** section.

### Step 2: Add This Command
In the "Ignored Build Step" input field, paste this command:

```bash
git diff HEAD^ HEAD --quiet ./ || echo "dependabot" | grep -q "$(git log -1 --pretty=format:'%an')" && exit 0 || exit 1
```

**OR** (simpler version that skips all Dependabot branches):

```bash
echo "$VERCEL_GIT_COMMIT_REF" | grep -q "^dependabot/" && exit 1 || exit 0
```

This will:
- ✅ Skip builds for branches starting with `dependabot/`
- ✅ Allow builds for `main` and other branches
- ✅ Prevent the Next.js 16 incompatibility issue

### Step 3: Save
Click the **Save** button at the bottom of the section.

---

## 🔍 Alternative: Check Production Branch

If you want to ensure only `main` branch deploys to production:

1. Look for **"Production Branch"** setting (might be in "Build and Deployment" section)
2. Make sure it's set to `main`
3. This ensures only `main` branch creates production deployments

---

## ✅ What This Does

After adding the ignore command:
- ✅ Dependabot branches won't trigger builds
- ✅ Only `main` branch (and other non-Dependabot branches) will build
- ✅ No more Next.js 16 incompatibility errors
- ✅ Your production stays on Next.js 14.2.32 (compatible with next-auth)

---

## 🧪 Test It

After saving:
1. A Dependabot PR is created → Build will be skipped ✅
2. You push to `main` → Build will run ✅
3. You create a feature branch → Build will run ✅

---

**Last Updated:** 2025-01-27
**Status:** Ready to configure in Vercel

