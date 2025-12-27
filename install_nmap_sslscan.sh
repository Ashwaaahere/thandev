#!/bin/bash
# Install nmap and sslscan using snap or alternative methods

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Installing nmap and sslscan                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if already installed
if command_exists nmap && command_exists sslscan; then
    print_status "success" "Both nmap and sslscan are already installed"
    nmap --version 2>&1 | head -1
    sslscan --version 2>&1 | head -1
    exit 0
fi

# Method 1: Try snap (recommended for WSL/Ubuntu)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Method 1: Installing via snap..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists snap; then
    print_status "info" "Snap is available. Installing nmap..."
    
    # Install nmap via snap
    if ! command_exists nmap; then
        echo "Running: sudo snap install nmap"
        print_status "warning" "You'll need to enter your sudo password"
        sudo snap install nmap
        
        # Create symlink to make it available in PATH
        if [ -f "/snap/bin/nmap" ]; then
            mkdir -p "$HOME/.local/bin"
            ln -sf /snap/bin/nmap "$HOME/.local/bin/nmap" 2>/dev/null || true
            print_status "success" "nmap installed via snap"
        fi
    else
        print_status "success" "nmap already installed"
    fi
    
    # sslscan is not available via snap, will try other methods
else
    print_status "warning" "Snap not available"
fi

# Method 2: Try compiling from source (for sslscan)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Method 2: Installing sslscan..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! command_exists sslscan; then
    print_status "info" "sslscan not found. Checking installation options..."
    
    # Check if we can install build dependencies
    if command_exists git && command_exists make && command_exists gcc; then
        print_status "info" "Build tools available. Compiling sslscan from source..."
        
        cd /tmp
        if [ -d "sslscan" ]; then
            rm -rf sslscan
        fi
        
        git clone https://github.com/rbsec/sslscan.git
        cd sslscan
        
        # Check for required libraries
        if pkg-config --exists openssl 2>/dev/null; then
            make static
            sudo make install
            print_status "success" "sslscan compiled and installed"
        else
            print_status "error" "OpenSSL development libraries not found"
            print_status "info" "Install with: sudo apt install -y libssl-dev"
        fi
    else
        print_status "warning" "Build tools not available"
        print_status "info" "Note: sslscan has a fallback using OpenSSL (openssl s_client)"
        print_status "info" "The system will use OpenSSL if sslscan is not available"
    fi
else
    print_status "success" "sslscan already installed"
fi

# Method 3: Check for alternative package managers
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Method 3: Checking alternative package managers..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if we can use apt with universe repository
if command_exists apt && [ -f "/etc/apt/sources.list" ]; then
    print_status "info" "Checking if universe repository is enabled..."
    
    if grep -q "universe" /etc/apt/sources.list 2>/dev/null || \
       grep -q "universe" /etc/apt/sources.list.d/*.list 2>/dev/null 2>/dev/null; then
        print_status "info" "Universe repository found. Trying apt update..."
        print_status "warning" "Run manually: sudo apt update && sudo apt install -y nmap sslscan"
    else
        print_status "info" "You may need to enable universe repository:"
        print_status "info" "  sudo add-apt-repository universe"
        print_status "info" "  sudo apt update"
        print_status "info" "  sudo apt install -y nmap sslscan"
    fi
fi

# Final verification
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    INSTALLATION SUMMARY                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

if command_exists nmap; then
    print_status "success" "nmap: $(nmap --version 2>&1 | head -1)"
else
    print_status "error" "nmap: Not installed"
    print_status "info" "Install with: sudo snap install nmap"
fi

if command_exists sslscan; then
    print_status "success" "sslscan: $(sslscan --version 2>&1 | head -1)"
else
    print_status "warning" "sslscan: Not installed"
    print_status "info" "Note: The system has OpenSSL fallback for SSL scanning"
    print_status "info" "Install with: sudo apt install -y sslscan (if available)"
    print_status "info" "Or compile from source: https://github.com/rbsec/sslscan"
fi

echo ""
echo "📝 Manual Installation Instructions:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Install nmap via snap:"
echo "   sudo snap install nmap"
echo ""
echo "2. Install sslscan (choose one method):"
echo "   a) Via apt (if available):"
echo "      sudo apt update"
echo "      sudo apt install -y sslscan"
echo ""
echo "   b) Compile from source:"
echo "      sudo apt install -y libssl-dev git make gcc"
echo "      cd /tmp"
echo "      git clone https://github.com/rbsec/sslscan.git"
echo "      cd sslscan"
echo "      make static"
echo "      sudo make install"
echo ""
echo "3. Note: The Thandev system has OpenSSL fallback for SSL scanning"
echo "   if sslscan is not available, so scans will still work."
echo ""

