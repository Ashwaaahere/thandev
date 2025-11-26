#!/bin/bash

# Deploy Security Scanner to Google Cloud Run Service (not Job)
# SECURE: Requires authentication (no --allow-unauthenticated)
# Make sure you have gcloud CLI installed and authenticated

set -e

PROJECT_ID=${1:-"your-project-id"}
REGION=${2:-"us-central1"}
SERVICE_NAME="security-scanner"

echo "🚀 Deploying Security Scanner to Google Cloud Run Service..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "🔒 SECURE: Service requires authentication"

# Set the project
gcloud config set project $PROJECT_ID

# Build and push the container
echo "📦 Building and pushing container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/security-scanner:latest ./security-scanner

# Deploy to Cloud Run Service (NOT Job)
echo "🚀 Deploying to Cloud Run Service..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/security-scanner:latest \
  --platform managed \
  --region $REGION \
  --no-allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 1800 \
  --concurrency 5 \
  --max-instances 10

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')

echo "✅ Deployment complete!"
echo "🔒 Service URL: $SERVICE_URL"
echo ""
echo "📝 Update your backend environment variables:"
echo "CLOUD_RUN_SECURITY_URL=$SERVICE_URL"
echo ""
echo "🔐 To allow backend to call this service:"
echo "1. Get your backend's service account email (if on GCP)"
echo "2. Or create a service account and grant 'Cloud Run Invoker' role:"
echo "   gcloud run services add-iam-policy-binding $SERVICE_NAME \\"
echo "     --region=$REGION \\"
echo "     --member='serviceAccount:YOUR_SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com' \\"
echo "     --role='roles/run.invoker'"
