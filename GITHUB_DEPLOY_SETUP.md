# GitHub to Fly.io Deployment Setup

This guide shows how to set up automatic deployment from GitHub to Fly.io using GitHub Actions.

## Prerequisites

1. GitHub repository with your code
2. Fly.io account with apps created:
   - `thandev-backend`
   - `thandev-brain`
   - `thandev-runner`
   - `thandev-qdrant`

## Setup Steps

### 1. Generate Fly.io API Token

Run this command locally (you only need to do this once):

```bash
fly tokens create deploy -x 999999h
```

Copy the token that starts with `FlyV1 ` (include the space and everything after it).

### 2. Add Token to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `FLY_API_TOKEN`
5. Value: Paste the token from step 1 (including `FlyV1 ` prefix)
6. Click **Add secret**

### 3. Push the Workflow

The workflow file `.github/workflows/fly-deploy.yml` is already created. Commit and push:

```bash
git add .github/workflows/fly-deploy.yml
git commit -m "Add GitHub Actions workflow for Fly.io deployment"
git push origin main
```

### 4. How It Works

The workflow will automatically deploy services when you push changes:

- **thandev-brain**: Deploys when `services/thandev-brain/` changes
- **thandev-runner**: Deploys when `services/thandev-runner/` changes
- **thandev-qdrant**: Deploys when `services/qdrant-fly/` changes
- **thandev-backend**: Deploys when `backend/` changes

### 5. Manual Deployment

You can also trigger deployments manually:

1. Go to your GitHub repository
2. Click **Actions** tab
3. Select **Fly.io Deploy** workflow
4. Click **Run workflow**
5. Select branch and click **Run workflow**

## Benefits

- ✅ Faster builds (uses Fly.io's remote builders)
- ✅ Automatic deployments on push
- ✅ No need to run `fly deploy` locally
- ✅ Build logs visible in GitHub Actions

## Notes

- Deployments use `--remote-only` flag for faster builds
- Each service deploys independently based on changed files
- All deployments run in parallel if multiple services change
- Check deployment status in GitHub Actions → Workflows

