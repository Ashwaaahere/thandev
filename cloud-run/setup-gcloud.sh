#!/bin/bash

# Google Cloud Setup Script for Thandev Lighthouse Scanner
# Run this script after installing gcloud CLI

set -e

echo "🔧 Setting up Google Cloud for Thandev Lighthouse Scanner..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud CLI not found. Please install it first:"
    echo "   sudo snap install google-cloud-cli --classic"
    exit 1
fi

echo "✅ Google Cloud CLI found"

# Initialize gcloud
echo "🔐 Initializing Google Cloud..."
gcloud init

# Enable required APIs
echo "🚀 Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Get current project
PROJECT_ID=$(gcloud config get-value project)
echo "📋 Current project: $PROJECT_ID"

# Create service account for Cloud Run
echo "👤 Creating service account..."
gcloud iam service-accounts create lighthouse-scanner-sa \
    --display-name="Lighthouse Scanner Service Account" \
    --description="Service account for Thandev Lighthouse Scanner"

# Grant necessary permissions
echo "🔑 Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:lighthouse-scanner-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Create and download service account key
echo "📄 Creating service account key..."
gcloud iam service-accounts keys create lighthouse-scanner-key.json \
    --iam-account=lighthouse-scanner-sa@$PROJECT_ID.iam.gserviceaccount.com

echo "✅ Google Cloud setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Update your frontend .env.local with:"
echo "   PROJECT_ID=$PROJECT_ID"
echo "   CLOUD_RUN_TOKEN=\$(cat lighthouse-scanner-key.json | base64 -w 0)"
echo ""
echo "2. Deploy the Lighthouse scanner:"
echo "   ./deploy.sh $PROJECT_ID us-central1"
echo ""
echo "3. Test the deployment:"
echo "   curl https://lighthouse-scanner-xxxxx-uc.a.run.app/health"







