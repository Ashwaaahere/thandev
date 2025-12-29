# How to Check GitHub Actions Deployment

## 1. Check GitHub Actions Status

1. Go to your GitHub repository in a browser
2. Click on the **Actions** tab at the top
3. You should see a workflow run named **"Fly.io Deploy"**
4. Click on the latest run to see its status

## 2. What to Look For

### ✅ Successful Deployment:
- All jobs show green checkmarks (✓)
- Each service deployment shows "Deploy thandev-xxx" with success status
- Logs show "Deployed successfully" messages

### ❌ Failed Deployment:
- Jobs show red X marks
- Click on the failed job to see error logs
- Common issues:
  - Missing `FLY_API_TOKEN` secret → Add it in Settings → Secrets → Actions
  - Authentication failed → Verify token is correct
  - Build errors → Check the build logs for specific errors

## 3. Check Workflow Files

The workflow file should be at:
```
.github/workflows/fly-deploy.yml
```

## 4. Verify Token is Set

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. You should see `FLY_API_TOKEN` listed
3. If it's missing, click **New repository secret** and add it

## 5. Test Manual Deployment

If the workflow didn't trigger automatically:

1. Go to **Actions** tab
2. Select **"Fly.io Deploy"** workflow
3. Click **"Run workflow"** button (top right)
4. Select branch: **main**
5. Click **"Run workflow"**

## 6. Monitor Deployments

Once the workflow runs:
- View real-time logs in the Actions tab
- Each service deploys independently
- Deployments run in parallel when multiple services change

## Expected Behavior

When you push changes:
- **services/thandev-brain/** changes → Deploys brain
- **services/thandev-runner/** changes → Deploys runner  
- **services/qdrant-fly/** changes → Deploys qdrant
- **backend/** changes → Deploys backend

The workflow uses smart detection to only deploy services that changed.

## Troubleshooting

If deployments fail:
1. Check the error logs in GitHub Actions
2. Verify `FLY_API_TOKEN` secret is set correctly
3. Ensure Fly.io apps exist: `thandev-backend`, `thandev-brain`, `thandev-runner`, `thandev-qdrant`
4. Check Fly.io dashboard for app status

