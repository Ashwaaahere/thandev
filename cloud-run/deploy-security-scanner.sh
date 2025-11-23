#!/bin/bash

# Deploy Security Scanner to Google Cloud Run Jobs
# Make sure you have gcloud CLI installed and authenticated

set -e

PROJECT_ID=${1:-"your-project-id"}
REGION=${2:-"us-central1"}
JOB_NAME="security-scanner-job"

echo "🚀 Deploying Security Scanner to Google Cloud Run Jobs..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Job: $JOB_NAME"

# Set the project
gcloud config set project $PROJECT_ID

# Build and push the container
echo "📦 Building and pushing container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/security-scanner:latest ./security-scanner

# Create or update the Cloud Run Job
echo "🚀 Creating/updating Cloud Run Job..."

# Check if job exists and delete it first
if gcloud run jobs describe $JOB_NAME --region=$REGION --quiet 2>/dev/null; then
  echo "Deleting existing job..."
  gcloud run jobs delete $JOB_NAME --region=$REGION --quiet
fi

# Create the new job
gcloud run jobs create $JOB_NAME \
  --image gcr.io/$PROJECT_ID/security-scanner:latest \
  --region $REGION \
  --cpu 2 \
  --memory 4Gi \
  --max-retries 1 \
  --task-timeout 1800s \
  --parallelism 1

echo "✅ Deployment complete!"
echo ""
echo "🔧 Test the job with:"
echo "gcloud run jobs execute $JOB_NAME --region $REGION --args '--env-vars=URL=https://example.com,SCAN_TYPE=quick,CALLBACK_URL=https://your-api.com/api/security-scan/callback/test-123'"
echo ""
echo "📝 Update your backend environment variables:"
echo "CLOUD_RUN_JOB_URL=https://$REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$PROJECT_ID/jobs/$JOB_NAME"
