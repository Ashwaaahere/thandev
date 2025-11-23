# How to Set Environment Variables in Fly.io

## Method 1: Using Fly CLI (Recommended)

### Step 1: Install Fly CLI (if not already installed)

```bash
# On Linux/Mac
curl -L https://fly.io/install.sh | sh

# Or download from: https://fly.io/docs/hands-on/install-flyctl/
```

### Step 2: Login to Fly.io

```bash
fly auth login
```

### Step 3: Set Environment Variables (Secrets)

Fly.io uses "secrets" for environment variables. Set them using:

```bash
# Set Cloud Run Lighthouse URL
fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-697855159499.us-central1.run.app -a thandev-backend

# Set Cloud Run enabled flag
fly secrets set CLOUD_RUN_ENABLED=true -a thandev-backend
```

**Note:** Replace `https://lighthouse-scanner-697855159499.us-central1.run.app` with your actual Cloud Run Service URL if different.

### Step 4: Verify Secrets Are Set

```bash
# List all secrets (values are hidden for security)
fly secrets list -a thandev-backend
```

You should see:
```
CLOUD_RUN_ENABLED
CLOUD_RUN_LIGHTHOUSE_URL
```

### Step 5: Restart the App (if needed)

Secrets are automatically applied, but you may need to restart:

```bash
fly apps restart thandev-backend
```

## Method 2: Using Fly.io Dashboard (Web UI)

### Step 1: Go to Fly.io Dashboard

1. Visit: https://fly.io/dashboard
2. Login to your account

### Step 2: Select Your App

1. Click on **"thandev-backend"** from the list of apps

### Step 3: Navigate to Secrets

1. In the app dashboard, look for **"Secrets"** in the left sidebar
2. Click on **"Secrets"**

### Step 4: Add Secrets

1. Click **"Add Secret"** or **"Set Secret"** button
2. Enter the secret name: `CLOUD_RUN_LIGHTHOUSE_URL`
3. Enter the value: `https://lighthouse-scanner-697855159499.us-central1.run.app`
4. Click **"Set Secret"** or **"Save"**

5. Repeat for the second secret:
   - Name: `CLOUD_RUN_ENABLED`
   - Value: `true`
   - Click **"Set Secret"**

### Step 5: Restart the App

1. Go to **"Overview"** or **"Metrics"** tab
2. Click **"Restart"** button (if available)
3. Or the app will automatically restart when secrets are set

## Method 3: Set Multiple Secrets at Once

You can set multiple secrets in one command:

```bash
fly secrets set \
  CLOUD_RUN_LIGHTHOUSE_URL=https://lighthouse-scanner-697855159499.us-central1.run.app \
  CLOUD_RUN_ENABLED=true \
  -a thandev-backend
```

## Method 4: Using fly.toml (Not Recommended for Secrets)

**⚠️ Warning:** Don't put secrets in `fly.toml` as it's committed to git!

For non-sensitive config, you can add to `fly.toml`:

```toml
[env]
  CLOUD_RUN_ENABLED = "true"
  # CLOUD_RUN_LIGHTHOUSE_URL should be a secret, not here!
```

But for secrets, always use `fly secrets set`.

## Verify Environment Variables Are Working

### Check Logs

```bash
fly logs -a thandev-backend
```

Look for:
- No errors about missing `CLOUD_RUN_LIGHTHOUSE_URL`
- Logs showing Cloud Run Service calls

### Test a Performance Scan

1. Go to your frontend
2. Submit a performance scan
3. Check backend logs:
   ```bash
   fly logs -a thandev-backend
   ```
4. You should see logs like:
   ```
   Started Cloud Run scan for job <job_id>, cloud job ID: <cloud_job_id>
   Cloud Run scan status for job <job_id>: running (poll 1/60)
   ```

## Troubleshooting

### Secret Not Found Error

If you see errors about missing environment variables:

1. **Verify secrets are set:**
   ```bash
   fly secrets list -a thandev-backend
   ```

2. **Check secret names match exactly:**
   - `CLOUD_RUN_LIGHTHOUSE_URL` (not `CLOUD_RUN_LIGHTHOUSE_SERVICE_URL`)
   - `CLOUD_RUN_ENABLED` (not `ENABLE_CLOUD_RUN`)

3. **Restart the app:**
   ```bash
   fly apps restart thandev-backend
   ```

### Wrong Cloud Run URL

If scans fail with connection errors:

1. **Get the correct URL from Google Cloud Console:**
   - Go to: https://console.cloud.google.com/run
   - Click on `lighthouse-scanner` service
   - Copy the URL shown

2. **Update the secret:**
   ```bash
   fly secrets set CLOUD_RUN_LIGHTHOUSE_URL=<correct-url> -a thandev-backend
   ```

### App Not Restarting

If changes don't take effect:

1. **Force restart:**
   ```bash
   fly apps restart thandev-backend
   ```

2. **Or trigger a new deployment:**
   ```bash
   fly deploy -a thandev-backend
   ```

## Quick Reference

```bash
# Set a secret
fly secrets set KEY=value -a thandev-backend

# List all secrets
fly secrets list -a thandev-backend

# Remove a secret
fly secrets unset KEY -a thandev-backend

# View app info
fly status -a thandev-backend

# View logs
fly logs -a thandev-backend
```

## Required Secrets for Performance Scans

| Secret Name | Value | Required |
|------------|-------|----------|
| `CLOUD_RUN_LIGHTHOUSE_URL` | Your Cloud Run Service URL | ✅ Yes |
| `CLOUD_RUN_ENABLED` | `true` or `false` | ✅ Yes (set to `true`) |

## Other Secrets You May Have

Your backend might also need:
- `DATABASE_URL` - PostgreSQL connection string
- `GCP_PROJECT_ID` - Google Cloud Project ID
- `GCP_REGION` - Region (e.g., `us-central1`)
- `BACKEND_URL` - Your backend URL for callbacks
- `CALLBACK_SECRET` - Secret for validating callbacks

Check what you have:
```bash
fly secrets list -a thandev-backend
```

