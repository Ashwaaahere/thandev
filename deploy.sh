#!/bin/bash
# Quick deployment script for Thandev

echo "🚀 Deploying Thandev Security Intelligence Platform"
echo "=================================================="

# Check if flyctl is installed
if ! command -v fly &> /dev/null; then
    echo "❌ Fly.io CLI not found. Installing..."
    curl -L https://fly.io/install.sh | sh
    export PATH="$HOME/.fly/bin:$PATH"
fi

# Check if user is logged in to Fly.io
if ! fly auth whoami &> /dev/null; then
    echo "🔐 Please login to Fly.io:"
    fly auth login
fi

echo "📦 Deploying Backend to Fly.io..."
cd backend
fly deploy

echo "✅ Backend deployed! Your API will be available at:"
echo "   https://$(fly info --json | jq -r '.Hostname')"

echo ""
echo "🌐 Next steps for Vercel deployment:"
echo "1. Go to https://vercel.com/dashboard"
echo "2. Import your GitHub repository"
echo "3. Set Root Directory to 'frontend'"
echo "4. Add environment variable:"
echo "   NEXT_PUBLIC_API_BASE = https://$(fly info --json | jq -r '.Hostname')"
echo "5. Deploy!"

echo ""
echo "🎉 Deployment complete!"
