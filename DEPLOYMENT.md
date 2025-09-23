# 🚀 Deployment Guide - Vercel + Fly.io

This guide will help you deploy your Thandev security intelligence platform to Vercel (frontend) and Fly.io (backend).

## 📋 Prerequisites

- GitHub account with your code pushed
- Vercel account (free tier available)
- Fly.io account (free tier available)
- PostgreSQL database (we'll use Fly.io's managed PostgreSQL)

## 🌐 Frontend Deployment (Vercel)

### Step 1: Deploy to Vercel

1. **Go to [Vercel Dashboard](https://vercel.com/dashboard)**
2. **Click "New Project"**
3. **Import your GitHub repository** (`Ashwaaahere/thandev`)
4. **Configure the project:**
   - Framework Preset: `Next.js`
   - Root Directory: `frontend`
   - Build Command: `npm run build`
   - Output Directory: `.next`

### Step 2: Set Environment Variables

In Vercel dashboard, go to your project → Settings → Environment Variables:

```
NEXT_PUBLIC_API_BASE = https://your-fly-app-name.fly.dev
```

### Step 3: Deploy

Click "Deploy" and wait for the build to complete. Your frontend will be available at `https://your-project.vercel.app`

## 🚀 Backend Deployment (Fly.io)

### Step 1: Install Fly.io CLI

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
fly auth login
```

### Step 2: Create PostgreSQL Database

```bash
# Create a PostgreSQL database
fly postgres create --name thandev-db --region iad

# Get the connection string
fly postgres connect -a thandev-db
```

### Step 3: Deploy Backend

```bash
# Navigate to project root
cd /path/to/thandev

# Initialize Fly.io app
fly launch --no-deploy

# Set environment variables
fly secrets set DATABASE_URL="postgresql://username:password@host:port/database"
fly secrets set REDIS_URL="redis://localhost:6379/0"
fly secrets set NVD_API_KEY="your_nvd_api_key_optional"

# Deploy
fly deploy
```

### Step 4: Set up Data Ingestion

```bash
# Deploy the scheduler
fly deploy --config fly-scheduler.toml
```

## 🔧 Environment Variables

### Frontend (Vercel)
- `NEXT_PUBLIC_API_BASE`: Your Fly.io backend URL

### Backend (Fly.io)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string (optional)
- `NVD_API_KEY`: NVD API key for higher rate limits (optional)

## 📊 Database Setup

### Option 1: Fly.io Managed PostgreSQL (Recommended)
```bash
# Create database
fly postgres create --name thandev-db --region iad

# Get connection details
fly postgres connect -a thandev-db
```

### Option 2: External Database
- Use services like Supabase, PlanetScale, or Railway
- Update `DATABASE_URL` in Fly.io secrets

## 🔄 Data Ingestion Setup

### Automatic Ingestion
The system will automatically fetch CVE data every 6 hours.

### Manual Ingestion
```bash
# Trigger manual data fetch
curl -X POST https://your-app.fly.dev/api/ingest
```

## 🌍 Custom Domains

### Vercel (Frontend)
1. Go to your project → Settings → Domains
2. Add your custom domain
3. Update DNS records as instructed

### Fly.io (Backend)
```bash
# Add custom domain
fly certs add your-domain.com
```

## 📈 Monitoring

### Vercel
- Built-in analytics and performance monitoring
- Real-time logs in dashboard

### Fly.io
```bash
# View logs
fly logs

# Monitor metrics
fly metrics

# Check app status
fly status
```

## 🔒 Security

### CORS Configuration
The backend is configured to allow requests from your Vercel domain.

### Environment Variables
- Never commit `.env` files
- Use Vercel and Fly.io secrets for sensitive data
- Rotate API keys regularly

## 🚨 Troubleshooting

### Common Issues

1. **CORS Errors**
   - Check `CORS_ALLOW_ORIGINS` in backend
   - Ensure frontend URL is whitelisted

2. **Database Connection**
   - Verify `DATABASE_URL` is correct
   - Check database is accessible from Fly.io

3. **Build Failures**
   - Check Node.js version compatibility
   - Verify all dependencies are installed

### Debug Commands

```bash
# Check Fly.io app status
fly status

# View recent logs
fly logs --tail

# SSH into container
fly ssh console

# Check Vercel deployment logs
# Go to Vercel dashboard → Functions → View Function Logs
```

## 📞 Support

- **Vercel**: [Vercel Support](https://vercel.com/support)
- **Fly.io**: [Fly.io Community](https://community.fly.io)
- **Project Issues**: [GitHub Issues](https://github.com/Ashwaaahere/thandev/issues)

## 🎯 Next Steps

After deployment:
1. Test all endpoints
2. Set up monitoring alerts
3. Configure custom domains
4. Set up CI/CD for automatic deployments
5. Add SSL certificates
6. Set up backup strategies

---

**Your security intelligence platform is now live! 🎉**
