# Where to Find Root Directory in Vercel

## Location: Build and Deployment Settings

The **Root Directory** setting is NOT in the General tab. It's in:

### Steps:
1. **Go to:** Vercel Dashboard → Your Project (thandev)
2. **Click:** Settings (gear icon)
3. **Click:** **"Build and Deployment"** (in the left sidebar)
4. **Scroll down** to find **"Root Directory"** section
5. **Click:** Edit button
6. **Enter:** `frontend`
7. **Click:** Save

---

## Alternative: If Not Visible

If you don't see "Root Directory" in Build and Deployment:

### Option 1: Check General Tab (Scroll Down)
- Sometimes it's at the bottom of the General tab
- Scroll all the way down on the General page
- Look for "Root Directory" section

### Option 2: Use Vercel CLI
```bash
# Install Vercel CLI if not installed
npm i -g vercel

# Login
vercel login

# Link project
vercel link

# Set root directory
vercel --cwd frontend
```

### Option 3: Check Project Configuration
- The root directory might be set at the team/project level
- Check if there's a "Configuration" or "Project Configuration" section

---

## Quick Visual Guide

**Settings Page Structure:**
```
Settings
├── General (you're here)
│   ├── Project Name
│   ├── Project ID
│   └── ... (scroll down for Root Directory - if present)
│
├── Build and Deployment ⭐ (ROOT DIRECTORY IS HERE)
│   ├── Build Command
│   ├── Output Directory
│   ├── Install Command
│   └── Root Directory ← LOOK HERE
│
├── Domains
├── Environments
└── ...
```

---

## If Still Can't Find It

1. **Check Vercel Documentation:**
   - https://vercel.com/docs/projects/overview/root-directory

2. **Try Creating New Project:**
   - Sometimes it's easier to see during project creation
   - You can set root directory when importing from GitHub

3. **Contact Vercel Support:**
   - They can help locate the setting

---

**Most Likely Location:** Settings → **Build and Deployment** → Root Directory

