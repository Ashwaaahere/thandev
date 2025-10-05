#!/bin/bash

echo "🚀 Deploying Lighthouse Scanner to Google Cloud Run..."

# Set variables
PROJECT_ID="thandev"
SERVICE_NAME="lighthouse-scanner"
REGION="us-central1"

echo "📦 Building and deploying with Cloud Build..."
cd lighthouse-scanner

# Build and deploy in one command
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --port 8080 \
  --project $PROJECT_ID

echo "✅ Deployment complete!"
echo "🌐 Service URL: https://$SERVICE_NAME-$(gcloud config get-value project).$REGION.run.app"

