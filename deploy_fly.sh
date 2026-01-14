#!/bin/bash
# Fly.io Manual Deployment Script
# Deploys all services using Fly CLI with Docker containers

set -e  # Exit on error

echo "🚀 Thandev Fly.io Deployment Script"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if fly CLI is installed
if ! command -v fly &> /dev/null; then
    echo -e "${RED}❌ Fly CLI not found. Please install it first:${NC}"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

echo -e "${GREEN}✅ Fly CLI found${NC}"
echo ""

# Check if logged in
if ! fly auth whoami &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to Fly.io. Please login:${NC}"
    echo "   fly auth login"
    exit 1
fi

echo -e "${GREEN}✅ Logged in to Fly.io${NC}"
echo ""

# Function to deploy a service
deploy_service() {
    local service_name=$1
    local service_dir=$2
    local description=$3
    
    echo -e "${YELLOW}📦 Deploying ${description}...${NC}"
    echo "   Service: ${service_name}"
    echo "   Directory: ${service_dir}"
    echo ""
    
    cd "${service_dir}"
    
    # Deploy using Fly CLI (builds Docker container automatically)
    if fly deploy --remote-only --app "${service_name}"; then
        echo -e "${GREEN}✅ ${description} deployed successfully!${NC}"
    else
        echo -e "${RED}❌ ${description} deployment failed!${NC}"
        cd - > /dev/null
        exit 1
    fi
    
    cd - > /dev/null
    echo ""
}

# Function to check service status
check_status() {
    local service_name=$1
    echo -e "${YELLOW}📊 Checking ${service_name} status...${NC}"
    fly status --app "${service_name}" | head -10
    echo ""
}

# Main deployment flow
echo "Starting deployment..."
echo ""

# Get deployment order from user or use default
DEPLOY_ORDER="${1:-all}"

case "${DEPLOY_ORDER}" in
    backend)
        deploy_service "thandev-backend" "backend" "Backend Service"
        check_status "thandev-backend"
        ;;
    brain)
        deploy_service "thandev-brain" "services/thandev-brain" "Brain Service"
        check_status "thandev-brain"
        ;;
    runner)
        deploy_service "thandev-runner" "services/thandev-runner" "Runner Service"
        check_status "thandev-runner"
        ;;
    qdrant)
        deploy_service "thandev-qdrant" "services/qdrant-fly" "Qdrant Service"
        check_status "thandev-qdrant"
        ;;
    all|*)
        echo -e "${YELLOW}Deploying all services in order...${NC}"
        echo ""
        
        # Deploy in order: Backend -> Brain -> Runner -> Qdrant
        deploy_service "thandev-backend" "backend" "Backend Service"
        sleep 5  # Brief pause between deployments
        
        deploy_service "thandev-brain" "services/thandev-brain" "Brain Service"
        sleep 5
        
        deploy_service "thandev-runner" "services/thandev-runner" "Runner Service"
        sleep 5
        
        deploy_service "thandev-qdrant" "services/qdrant-fly" "Qdrant Service"
        
        echo ""
        echo -e "${GREEN}🎉 All services deployed!${NC}"
        echo ""
        echo "Checking status of all services..."
        echo ""
        
        check_status "thandev-backend"
        check_status "thandev-brain"
        check_status "thandev-runner"
        check_status "thandev-qdrant"
        ;;
esac

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Verify services: fly status -a <app-name>"
echo "2. Check logs: fly logs -a <app-name>"
echo "3. Test health: curl https://thandev-backend.fly.dev/healthz"
echo ""
