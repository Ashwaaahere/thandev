# How to Set Environment Variables in Vercel - Step by Step Guide

## 📋 What You Need to Do

You need to add environment variables in Vercel so your app can use them. Think of it like setting passwords and configuration that your app needs to work.

---

## 🎯 Step-by-Step Instructions

### Step 1: Open Vercel Dashboard
1. Open your web browser
2. Go to: **https://vercel.com/dashboard**
3. Log in with your account (GitHub, GitLab, or email)

### Step 2: Find Your Project
1. You should see a list of projects
2. Find and click on your project: **`thandev`**
   - If you don't see it, make sure you've connected your GitHub repository to Vercel

### Step 3: Go to Settings
1. At the top of the project page, you'll see tabs like:
   - **Overview** | **Deployments** | **Analytics** | **Settings**
2. Click on **Settings**

### Step 4: Open Environment Variables
1. In the Settings page, look at the left sidebar menu
2. You'll see options like:
   - General
   - **Environment Variables** ← Click this one
   - Git
   - Domains
   - etc.

### Step 5: Add NEXTAUTH_URL
1. Click the button that says **"Add New"** or **"Add"** (usually at the top right)
2. A form will appear with three fields:
   
   **Field 1: Key (or Name)**
   - Type exactly: `NEXTAUTH_URL`
   - Make sure it's all uppercase, no spaces
   
   **Field 2: Value**
   - Type exactly: `https://thandev.vercel.app`
   - Make sure there are no extra spaces
   
   **Field 3: Environment**
   - You'll see checkboxes or dropdown:
     - ☑ Production
     - ☑ Preview  
     - ☑ Development
   - **Check ALL THREE boxes** (or select "All Environments")
   
3. Click **"Save"** or **"Add"**

### Step 6: Add NEXTAUTH_SECRET
1. Click **"Add New"** again
2. Fill in the form:
   
   **Key:** `NEXTAUTH_SECRET`
   
   **Value:** `X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=`
   - Copy this entire string exactly
   
   **Environment:** Check all three (Production, Preview, Development)
   
3. Click **"Save"**

### Step 7: Add Other Required Variables (if needed)
Repeat the process for:
- `GITHUB_ID` = (your GitHub OAuth client ID)
- `GITHUB_SECRET` = (your GitHub OAuth client secret)
- `NEXT_PUBLIC_API_BASE` = `https://thandev-backend.fly.dev`

### Step 8: Verify Your Variables
After adding, you should see a list like this:
```
NEXTAUTH_URL          https://thandev.vercel.app        [Production, Preview, Development]
NEXTAUTH_SECRET       X0c9mJ1goTUTmcs745p0m7W7x/Egkjg... [Production, Preview, Development]
GITHUB_ID             your_github_id                    [Production, Preview, Development]
GITHUB_SECRET         your_github_secret                [Production, Preview, Development]
NEXT_PUBLIC_API_BASE  https://thandev-backend.fly.dev   [Production, Preview, Development]
```

### Step 9: Redeploy Your App
1. Go back to the **Deployments** tab (at the top)
2. Find your latest deployment
3. Click the **three dots (⋯)** next to it
4. Click **"Redeploy"**
5. Or simply push a new commit to GitHub (Vercel will auto-deploy)

---

## 🎨 Visual Guide (What You'll See)

```
Vercel Dashboard
├── Projects
│   └── thandev ← Click here
│       ├── Overview
│       ├── Deployments
│       └── Settings ← Click here
│           ├── General
│           ├── Environment Variables ← Click here
│           │   └── [Add New] ← Click this button
│           │       └── Form:
│           │           Key: NEXTAUTH_URL
│           │           Value: https://thandev.vercel.app
│           │           Environment: ☑ Production ☑ Preview ☑ Development
│           │           [Save]
│           ├── Git
│           └── Domains
```

---

## ✅ Checklist

Before you finish, make sure:
- [ ] You're logged into Vercel
- [ ] You found your `thandev` project
- [ ] You're in Settings → Environment Variables
- [ ] You added `NEXTAUTH_URL` = `https://thandev.vercel.app`
- [ ] You added `NEXTAUTH_SECRET` = `X0c9mJ1goTUTmcs745p0m7W7x/EgkjgK44MjAFtU+DA=`
- [ ] Both variables are set for Production, Preview, AND Development
- [ ] You clicked "Save" for each variable
- [ ] You can see both variables in the list
- [ ] You redeployed your app

---

## 🆘 Troubleshooting

### "I can't find my project"
- Make sure you've connected your GitHub repository to Vercel
- Go to https://vercel.com/new and import your repository

### "I don't see Environment Variables option"
- Make sure you're in the **Settings** tab
- Look in the left sidebar menu
- It should be listed under Settings

### "The Save button doesn't work"
- Make sure all fields are filled
- Check that the Key name is correct (no typos)
- Try refreshing the page

### "I added the variables but it's still not working"
- Make sure you **redeployed** after adding variables
- Check that variables are set for the correct environment (Production/Preview/Development)
- Wait a few minutes for the deployment to complete

---

## 📞 Need More Help?

If you're still stuck:
1. Take a screenshot of what you see
2. Describe what step you're on
3. Check the Vercel documentation: https://vercel.com/docs/concepts/projects/environment-variables

---

**Last Updated:** 2025-01-27

