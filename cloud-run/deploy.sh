#!/bin/bash

# Deploy Lighthouse Scanner to Google Cloud Run
# Make sure you have gcloud CLI installed and authenticated

set -e

PROJECT_ID=${1:-"your-project-id"}
REGION=${2:-"us-central1"}
SERVICE_NAME="lighthouse-scanner"

echo "🚀 Deploying Lighthouse Scanner to Google Cloud Run..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"

# Set the project
gcloud config set project $PROJECT_ID

# Build and push the container
echo "📦 Building and pushing container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME ./lighthouse-scanner

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 10 \
  --max-instances 100 \
  --set-env-vars NODE_ENV=production

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo "✅ Deployment complete!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "🔧 Update your frontend environment variables:"
echo "CLOUD_RUN_JOB_URL=$SERVICE_URL"
echo "CLOUD_RUN_TOKEN=your-service-account-token"







