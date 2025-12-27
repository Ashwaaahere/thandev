#!/bin/bash
# Install all required tools and dependencies for Thandev
# This script installs everything needed to run the Thandev platform

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Installing All Tools for Thandev Platform              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    if [ "$1" = "success" ]; then
        echo -e "${GREEN}✅ $2${NC}"
    elif [ "$1" = "warning" ]; then
        echo -e "${YELLOW}⚠️  $2${NC}"
    elif [ "$1" = "error" ]; then
        echo -e "${RED}❌ $2${NC}"
    else
        echo "ℹ️  $2"
    fi
}

# Step 1: Check and setup Node.js/npm
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1: Setting up Node.js and npm..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if command_exists node && command_exists npm; then
    print_status "success" "Node.js $(node --version) and npm $(npm --version) are installed"
else
    print_status "error" "Node.js/npm not found. Installing nvm..."
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install --lts
    nvm use --lts
    print_status "success" "Node.js and npm installed"
fi

# Step 2: Install Frontend Dependencies
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 2: Installing Frontend Dependencies..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /home/ashwath/thandev/frontend
if [ -f "package.json" ]; then
    print_status "info" "Installing npm packages for frontend..."
    npm install
    print_status "success" "Frontend dependencies installed"
else
    print_status "error" "package.json not found in frontend directory"
fi

# Step 3: Setup Python Virtual Environments
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 3: Setting up Python Virtual Environments..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Backend venv
if [ ! -d "/home/ashwath/thandev/backend/venv" ]; then
    print_status "info" "Creating backend virtual environment..."
    cd /home/ashwath/thandev/backend
    python3 -m venv venv --without-pip 2>/dev/null || python3 -m venv venv
    source venv/bin/activate
    if ! command_exists pip; then
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python get-pip.py
        rm get-pip.py
    fi
    print_status "success" "Backend venv created"
else
    print_status "success" "Backend venv already exists"
fi

# Install backend dependencies
cd /home/ashwath/thandev/backend
source venv/bin/activate
if [ -f "requirements.txt" ]; then
    print_status "info" "Installing backend Python packages..."
    pip install -r requirements.txt
    print_status "success" "Backend dependencies installed"
fi
deactivate

# Thandev-brain venv
if [ ! -d "/home/ashwath/thandev/services/thandev-brain/venv" ]; then
    print_status "info" "Creating thandev-brain virtual environment..."
    cd /home/ashwath/thandev/services/thandev-brain
    python3 -m venv venv --without-pip 2>/dev/null || python3 -m venv venv
    source venv/bin/activate
    if ! command_exists pip; then
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python get-pip.py
        rm get-pip.py
    fi
    print_status "success" "Thandev-brain venv created"
else
    print_status "success" "Thandev-brain venv already exists"
fi

# Install thandev-brain dependencies
cd /home/ashwath/thandev/services/thandev-brain
source venv/bin/activate
if [ -f "requirements.txt" ]; then
    print_status "info" "Installing thandev-brain Python packages..."
    pip install -r requirements.txt
    print_status "success" "Thandev-brain dependencies installed"
fi
deactivate

# Thandev-runner venv
if [ ! -d "/home/ashwath/thandev/services/thandev-runner/venv" ]; then
    print_status "info" "Creating thandev-runner virtual environment..."
    cd /home/ashwath/thandev/services/thandev-runner
    python3 -m venv venv --without-pip 2>/dev/null || python3 -m venv venv
    source venv/bin/activate
    if ! command_exists pip; then
        curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
        python get-pip.py
        rm get-pip.py
    fi
    print_status "success" "Thandev-runner venv created"
else
    print_status "success" "Thandev-runner venv already exists"
fi

# Install thandev-runner dependencies
cd /home/ashwath/thandev/services/thandev-runner
source venv/bin/activate
if [ -f "requirements.txt" ]; then
    print_status "info" "Installing thandev-runner Python packages..."
    pip install -r requirements.txt
    print_status "success" "Thandev-runner dependencies installed"
fi
deactivate

# Step 4: Install Security Scanning Tools
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 4: Installing Security Scanning Tools..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if install_scanning_tools.sh exists and run it
if [ -f "/home/ashwath/thandev/install_scanning_tools.sh" ]; then
    print_status "info" "Running scanning tools installation script..."
    bash /home/ashwath/thandev/install_scanning_tools.sh
else
    print_status "warning" "install_scanning_tools.sh not found, installing tools manually..."
    
    # Install Go (for Nuclei)
    if ! command_exists go; then
        print_status "info" "Installing Go..."
        GO_VERSION="1.22.0"
        cd /tmp
        wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" || \
        curl -L "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o "go${GO_VERSION}.linux-amd64.tar.gz"
        rm -rf "$HOME/.local/go"
        tar -C "$HOME/.local" -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
        rm "go${GO_VERSION}.linux-amd64.tar.gz"
        export PATH="$HOME/.local/go/bin:$PATH"
        export GOPATH="$HOME/go"
        echo 'export PATH="$HOME/.local/go/bin:$PATH"' >> ~/.bashrc
        echo 'export GOPATH="$HOME/go"' >> ~/.bashrc
        print_status "success" "Go installed"
    else
        print_status "success" "Go already installed: $(go version)"
    fi
    
    # Install Nuclei
    if ! command_exists nuclei; then
        print_status "info" "Installing Nuclei..."
        export PATH="$HOME/.local/go/bin:$PATH"
        export GOPATH="$HOME/go"
        go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
        if [ -f "$HOME/go/bin/nuclei" ]; then
            mkdir -p "$HOME/.local/bin"
            ln -sf "$HOME/go/bin/nuclei" "$HOME/.local/bin/nuclei"
            export PATH="$HOME/.local/bin:$PATH"
            print_status "success" "Nuclei installed"
        fi
    else
        print_status "success" "Nuclei already installed"
    fi
    
    # Install Lighthouse
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    if ! command_exists lighthouse; then
        print_status "info" "Installing Lighthouse..."
        npm install -g lighthouse
        print_status "success" "Lighthouse installed"
    else
        print_status "success" "Lighthouse already installed"
    fi
fi

# Step 5: Setup Prisma (Frontend Database)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 5: Setting up Prisma Database..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /home/ashwath/thandev/frontend
if [ -d "prisma" ] && [ -f "prisma/schema.prisma" ]; then
    print_status "info" "Generating Prisma client..."
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    npx prisma generate
    print_status "success" "Prisma client generated"
else
    print_status "warning" "Prisma schema not found, skipping Prisma setup"
fi

# Step 6: Check Docker Services
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 6: Checking Docker Services (Redis & Qdrant)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists docker || command_exists sudo; then
    print_status "info" "Docker is available. Starting services..."
    cd /home/ashwath/thandev
    if [ -f "start_services_with_sudo.sh" ]; then
        bash start_services_with_sudo.sh
    else
        print_status "warning" "start_services_with_sudo.sh not found"
    fi
else
    print_status "warning" "Docker not available. Install Docker to run Redis and Qdrant."
fi

# Step 7: Verify Installations
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    INSTALLATION SUMMARY                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

echo "📋 Installed Tools:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Node.js
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
if command_exists node; then
    print_status "success" "Node.js: $(node --version)"
else
    print_status "error" "Node.js: Not installed"
fi

# npm
if command_exists npm; then
    print_status "success" "npm: $(npm --version)"
else
    print_status "error" "npm: Not installed"
fi

# Python
if command_exists python3; then
    print_status "success" "Python: $(python3 --version)"
else
    print_status "error" "Python: Not installed"
fi

# Docker
if command_exists docker; then
    print_status "success" "Docker: $(docker --version 2>/dev/null || echo 'installed')"
else
    print_status "warning" "Docker: Not installed (required for Redis/Qdrant)"
fi

# Security Tools
if command_exists nuclei; then
    print_status "success" "Nuclei: $(nuclei -version 2>&1 | head -1)"
else
    print_status "warning" "Nuclei: Not installed"
fi

if command_exists lighthouse; then
    print_status "success" "Lighthouse: $(lighthouse --version 2>&1 | head -1)"
else
    print_status "warning" "Lighthouse: Not installed (Cloud Run alternative available)"
fi

# Services
echo ""
echo "📋 Service Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Redis
if timeout 1 bash -c "echo > /dev/tcp/localhost/6379" 2>/dev/null; then
    print_status "success" "Redis: Running on port 6379"
else
    print_status "warning" "Redis: Not running (start with: ./start_services_with_sudo.sh)"
fi

# Check Qdrant
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    print_status "success" "Qdrant: Running on port 6333"
else
    print_status "warning" "Qdrant: Not running (start with: ./start_services_with_sudo.sh)"
fi

echo ""
echo "📝 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Reload your shell: source ~/.bashrc"
echo "2. Start services: cd /home/ashwath/thandev && ./start_services_with_sudo.sh"
echo "3. Start frontend: cd frontend && npm run dev"
echo "4. Start backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo ""
echo "✅ Installation complete!"

TV and Mar nice wait for one week absolutely set up a saw late Moving on Atlanta Brave