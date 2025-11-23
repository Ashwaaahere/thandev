# ESLint Version Compatibility Fix

## ⚠️ Issue

Dependabot attempted to upgrade `eslint-config-next` from `14.2.5` to `16.0.0`, which requires ESLint 9. However, Next.js 14.x uses ESLint 8, causing a dependency conflict.

## ✅ Solution Applied

Pinned `eslint-config-next` to version `^14.2.5` to ensure compatibility with ESLint 8.57.0.

## 📋 Current Versions (Compatible)

```json
{
  "eslint": "8.57.0",
  "eslint-config-next": "^14.2.5"
}
```

## 🚫 Why Not Upgrade to ESLint 9?

- Next.js 14.x is not officially aligned with ESLint 9
- `eslint-config-next@16.x` requires ESLint 9, which can break linting rules
- ESLint 9 support in Next.js 14 is not fully stable

## 🔒 Protection

The `^14.2.5` version constraint will:
- Allow patch and minor updates within v14.x
- Prevent automatic upgrades to v15.x or v16.x
- Maintain compatibility with ESLint 8

## 📝 If You Need to Upgrade Later

When you upgrade to Next.js 15+ or 16+, you can then upgrade ESLint and eslint-config-next together:

```bash
npm install eslint@latest eslint-config-next@latest --save-dev
```

But for now, staying on v14.x is the safest option.

---

**Last Updated:** 2025-01-27
**Status:** Fixed - ESLint 8 + eslint-config-next 14.x

