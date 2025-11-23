#!/bin/bash

# Deploy Locust Runner to Google Cloud Run Jobs
# Make sure you have gcloud CLI installed and authenticated

set -e

PROJECT_ID=${1:-"your-project-id"}
REGION=${2:-"us-central1"}
JOB_NAME="locust-job"
GCS_BUCKET=${3:-"thandev-reports"}

echo "🚀 Deploying Locust Runner to Google Cloud Run Jobs..."
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Job: $JOB_NAME"
echo "GCS Bucket: $GCS_BUCKET"

# Set the project
gcloud config set project $PROJECT_ID

# Build and push the container
echo "📦 Building and pushing container..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/locust-runner:latest ./locust-runner

# Create or update the Cloud Run Job
echo "🚀 Creating/updating Cloud Run Job..."
gcloud run jobs create $JOB_NAME \
  --image gcr.io/$PROJECT_ID/locust-runner:latest \
  --region $REGION \
  --cpu 1 \
  --memory 1024Mi \
  --set-env-vars GCS_BUCKET=$GCS_BUCKET \
  --max-retries 0 \
  --task-timeout 900s \
  --parallelism 2 \
  --task-count 1 \
  --replace

echo "✅ Deployment complete!"
echo ""
echo "🔧 Test the job with:"
echo "gcloud run jobs execute $JOB_NAME --region $REGION --args '--env-vars=DOMAIN=example.com,VUS=50,DURATION=120,SPAWN=10,SCAN_ID=test-123,CALLBACK_URL=https://your-api.com/api/backend/callback'"


