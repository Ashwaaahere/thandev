#!/bin/bash

echo "🚀 Deploying Lighthouse Scanner to Google Cloud Run..."

# Set variables
PROJECT_ID="thandev"
SERVICE_NAME="lighthouse-scanner"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/lighthouse-scanner:professional"

echo "📦 Building Docker image..."
cd lighthouse-scanner

# Build the Docker image
docker build -t $IMAGE_NAME .

echo "📤 Pushing image to Google Container Registry..."
# Configure Docker to use gcloud as a credential helper
gcloud auth configure-docker

# Push the image
docker push $IMAGE_NAME

echo "🚀 Deploying to Cloud Run..."
# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --port 8080 \
  --project $PROJECT_ID

echo "✅ Deployment complete!"
echo "🌐 Service URL: https://$SERVICE_NAME-$(gcloud config get-value project).$REGION.run.app"



