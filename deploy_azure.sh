#!/bin/bash
# Azure Container Apps Deployment Script
# Builds, tags, and deploys images to Azure Container Registry and Container Apps

set -e  # Exit on error

echo "🚀 Thandev Azure Deployment Script"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

ACR_NAME="acrthandev"
RESOURCE_GROUP="rg-thandev-prod"
BACKEND_APP="thandev-backend"
RUNNER_APP="thandev-runner"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI not found. Please install it first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Azure CLI found${NC}"

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Azure. Please login:${NC}"
    echo -e "${YELLOW}  Run: az login --tenant \"1c31eac1-3f2a-4d4c-be97-1d9dc136c003\"${NC}"
    az login --tenant "1c31eac1-3f2a-4d4c-be97-1d9dc136c003"
fi

echo -e "${GREEN}✅ Logged in to Azure${NC}"

# Login to ACR
echo -e "${YELLOW}📦 Logging in to Azure Container Registry...${NC}"
az acr login --name $ACR_NAME
echo -e "${GREEN}✅ Logged in to ACR${NC}"
echo ""

# Build images
echo -e "${YELLOW}🔨 Building Docker images...${NC}"
docker-compose -f docker-compose.fly-local.yml build backend thandev-runner
echo -e "${GREEN}✅ Images built${NC}"
echo ""

# Tag images for ACR
echo -e "${YELLOW}🏷️  Tagging images for ACR...${NC}"
docker tag thandev-backend:latest $ACR_NAME.azurecr.io/thandev-backend:latest
docker tag thandev-thandev-runner:latest $ACR_NAME.azurecr.io/thandev-runner:latest
echo -e "${GREEN}✅ Images tagged${NC}"
echo ""

# Push images to ACR
echo -e "${YELLOW}📤 Pushing images to ACR...${NC}"
docker push $ACR_NAME.azurecr.io/thandev-backend:latest
docker push $ACR_NAME.azurecr.io/thandev-runner:latest
echo -e "${GREEN}✅ Images pushed to ACR${NC}"
echo ""

# Update Container Apps
echo -e "${YELLOW}🔄 Updating Azure Container Apps...${NC}"

# Update backend (container name: thandev-backend)
echo -e "${YELLOW}  Updating $BACKEND_APP container...${NC}"
az containerapp update \
    --name $BACKEND_APP \
    --resource-group $RESOURCE_GROUP \
    --container-name thandev-backend \
    --image $ACR_NAME.azurecr.io/thandev-backend:latest

BACKEND_STATUS=$(az containerapp show --name $BACKEND_APP --resource-group $RESOURCE_GROUP --query "properties.runningStatus" -o tsv)
echo -e "${GREEN}✅ $BACKEND_APP updated (Status: $BACKEND_STATUS)${NC}"
echo ""

# Update runner (container name: thandev-runner, ZAP sidecar is separate)
echo -e "${YELLOW}  Updating $RUNNER_APP container...${NC}"
az containerapp update \
    --name $RUNNER_APP \
    --resource-group $RESOURCE_GROUP \
    --container-name thandev-runner \
    --image $ACR_NAME.azurecr.io/thandev-runner:latest

RUNNER_STATUS=$(az containerapp show --name $RUNNER_APP --resource-group $RESOURCE_GROUP --query "properties.runningStatus" -o tsv)
echo -e "${GREEN}✅ $RUNNER_APP updated (Status: $RUNNER_STATUS)${NC}"
echo ""

# Wait for deployments to complete
echo -e "${YELLOW}⏳ Waiting for deployments to complete (30 seconds)...${NC}"
sleep 30

# Check health status
echo -e "${YELLOW}🏥 Checking service health...${NC}"
echo ""

# Check backend
echo -e "${YELLOW}  Checking $BACKEND_APP...${NC}"
BACKEND_STATUS=$(az containerapp show --name $BACKEND_APP --resource-group $RESOURCE_GROUP --query "properties.runningStatus" -o tsv)
echo "  Status: $BACKEND_STATUS"
if [ "$BACKEND_STATUS" == "Running" ]; then
    echo -e "  ${GREEN}✅ $BACKEND_APP is healthy${NC}"
else
    echo -e "  ${RED}❌ $BACKEND_APP status: $BACKEND_STATUS${NC}"
fi
echo ""

# Check runner
echo -e "${YELLOW}  Checking $RUNNER_APP...${NC}"
RUNNER_STATUS=$(az containerapp show --name $RUNNER_APP --resource-group $RESOURCE_GROUP --query "properties.runningStatus" -o tsv)
echo "  Status: $RUNNER_STATUS"
if [ "$RUNNER_STATUS" == "Running" ]; then
    echo -e "  ${GREEN}✅ $RUNNER_APP is healthy${NC}"
else
    echo -e "  ${RED}❌ $RUNNER_APP status: $RUNNER_STATUS${NC}"
fi
echo ""

# Show recent logs
echo -e "${YELLOW}📋 Recent logs (last 10 lines)...${NC}"
echo ""
echo -e "${YELLOW}  $BACKEND_APP logs:${NC}"
az containerapp logs show --name $BACKEND_APP --resource-group $RESOURCE_GROUP --tail 10 --type console 2>/dev/null || echo "  No logs available"
echo ""

echo -e "${YELLOW}  $RUNNER_APP logs:${NC}"
az containerapp logs show --name $RUNNER_APP --resource-group $RESOURCE_GROUP --tail 10 --type console 2>/dev/null || echo "  No logs available"
echo ""

echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo "Summary:"
echo "  - Images built and pushed to ACR"
echo "  - Container Apps updated"
echo "  - Health status checked"
echo ""
echo "To view full logs:"
echo "  az containerapp logs show --name $BACKEND_APP --resource-group $RESOURCE_GROUP --tail 50"
echo "  az containerapp logs show --name $RUNNER_APP --resource-group $RESOURCE_GROUP --tail 50"

