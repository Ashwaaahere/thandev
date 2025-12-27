#!/bin/bash
# Install ALL required security tools for Thandev orchestration
# Based on tool_matrix.py requirements

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Installing ALL Security Tools for Thandev              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
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

# Setup Go environment
export PATH="$HOME/.local/go/bin:$HOME/go/bin:$PATH"
export GOPATH="$HOME/go"
mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/go/bin"

# Ensure Go is installed
if ! command_exists go; then
    print_status "error" "Go is not installed. Installing Go..."
    GO_VERSION="1.22.0"
    cd /tmp
    wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" || \
    curl -L "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o "go${GO_VERSION}.linux-amd64.tar.gz"
    rm -rf "$HOME/.local/go"
    tar -C "$HOME/.local" -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
    rm "go${GO_VERSION}.linux-amd64.tar.gz"
    export PATH="$HOME/.local/go/bin:$PATH"
    export GOPATH="$HOME/go"
    echo 'export PATH="$HOME/.local/go/bin:$HOME/go/bin:$PATH"' >> ~/.bashrc
    echo 'export GOPATH="$HOME/go"' >> ~/.bashrc
    print_status "success" "Go installed"
else
    print_status "success" "Go already installed: $(go version)"
fi

# 1. Install httpx (ProjectDiscovery)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing httpx (ProjectDiscovery)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists httpx; then
    print_status "success" "httpx already installed: $(httpx -version 2>&1 | head -1)"
else
    print_status "info" "Installing httpx..."
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
    if [ -f "$HOME/go/bin/httpx" ]; then
        ln -sf "$HOME/go/bin/httpx" "$HOME/.local/bin/httpx"
        print_status "success" "httpx installed"
    else
        print_status "error" "httpx installation failed"
    fi
fi

# 2. Install ffuf
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing ffuf..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists ffuf; then
    print_status "success" "ffuf already installed: $(ffuf -V 2>&1 | head -1)"
else
    print_status "info" "Installing ffuf..."
    go install -v github.com/ffuf/ffuf/v2@latest
    if [ -f "$HOME/go/bin/ffuf" ]; then
        ln -sf "$HOME/go/bin/ffuf" "$HOME/.local/bin/ffuf"
        print_status "success" "ffuf installed"
    else
        print_status "error" "ffuf installation failed"
    fi
fi

# 3. Install dalfox
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing dalfox..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists dalfox; then
    print_status "success" "dalfox already installed: $(dalfox version 2>&1 | head -1)"
else
    print_status "info" "Installing dalfox..."
    go install github.com/hahwul/dalfox/v2@latest
    if [ -f "$HOME/go/bin/dalfox" ]; then
        ln -sf "$HOME/go/bin/dalfox" "$HOME/.local/bin/dalfox"
        print_status "success" "dalfox installed"
    else
        print_status "error" "dalfox installation failed"
    fi
fi

# 4. Install sqlmap (Python)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing sqlmap..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists sqlmap; then
    print_status "success" "sqlmap already installed: $(sqlmap --version 2>&1 | head -1)"
else
    print_status "info" "Installing sqlmap in backend venv..."
    cd /home/ashwath/thandev/backend
    source venv/bin/activate
    pip install sqlmap
    deactivate
    print_status "success" "sqlmap installed"
fi

# 5. Install Lighthouse (npm)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Installing Lighthouse..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if command_exists lighthouse; then
    print_status "success" "Lighthouse already installed: $(lighthouse --version 2>&1 | head -1)"
else
    print_status "info" "Installing Lighthouse globally..."
    npm install -g lighthouse
    print_status "success" "Lighthouse installed"
fi

# 6. Check nmap and sslscan (require sudo)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Checking nmap and sslscan..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command_exists nmap; then
    print_status "success" "nmap already installed: $(nmap --version 2>&1 | head -1)"
else
    print_status "warning" "nmap requires sudo. Install with: sudo apt install -y nmap"
fi

if command_exists sslscan; then
    print_status "success" "sslscan already installed: $(sslscan --version 2>&1 | head -1)"
else
    print_status "warning" "sslscan requires sudo. Install with: sudo apt install -y sslscan"
fi

# 7. Verify wordlists
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Verifying Wordlists..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WORDLISTS_DIR="/home/ashwath/thandev/wordlists"
REQUIRED_WORDLISTS=("ffuf-small.txt" "ffuf-pro.txt" "ffuf-advanced.txt" "common.txt")

for wl in "${REQUIRED_WORDLISTS[@]}"; do
    if [ -f "$WORDLISTS_DIR/$wl" ]; then
        lines=$(wc -l < "$WORDLISTS_DIR/$wl" 2>/dev/null | xargs)
        size=$(du -h "$WORDLISTS_DIR/$wl" 2>/dev/null | cut -f1)
        print_status "success" "$wl: $lines lines, $size"
    else
        print_status "error" "$wl: MISSING"
    fi
done

# 8. Update PATH in .bashrc
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Updating PATH..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! grep -q 'export PATH="$HOME/.local/bin:$HOME/go/bin:$PATH"' ~/.bashrc; then
    echo 'export PATH="$HOME/.local/bin:$HOME/go/bin:$PATH"' >> ~/.bashrc
    print_status "success" "Added tools to PATH in .bashrc"
else
    print_status "success" "PATH already configured"
fi

# Final verification
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    INSTALLATION SUMMARY                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

export PATH="$HOME/.local/bin:$HOME/go/bin:$PATH"

echo "📋 Installed Tools:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

command_exists nuclei && print_status "success" "Nuclei: $(nuclei -version 2>&1 | head -1)" || print_status "error" "Nuclei: Not installed"
command_exists httpx && print_status "success" "httpx: $(httpx -version 2>&1 | head -1)" || print_status "error" "httpx: Not installed"
command_exists ffuf && print_status "success" "ffuf: $(ffuf -V 2>&1 | head -1)" || print_status "error" "ffuf: Not installed"
command_exists dalfox && print_status "success" "dalfox: $(dalfox version 2>&1 | head -1)" || print_status "error" "dalfox: Not installed"
command_exists sqlmap && print_status "success" "sqlmap: $(sqlmap --version 2>&1 | head -1)" || print_status "error" "sqlmap: Not installed"
command_exists nmap && print_status "success" "nmap: $(nmap --version 2>&1 | head -1)" || print_status "warning" "nmap: Not installed (needs sudo)"
command_exists sslscan && print_status "success" "sslscan: $(sslscan --version 2>&1 | head -1)" || print_status "warning" "sslscan: Not installed (needs sudo)"
command_exists lighthouse && print_status "success" "Lighthouse: $(lighthouse --version 2>&1 | head -1)" || print_status "warning" "Lighthouse: Not installed"

echo ""
echo "📝 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Reload shell: source ~/.bashrc"
echo "2. Install nmap/sslscan (if needed): sudo apt install -y nmap sslscan"
echo "3. Test tools: httpx -version, ffuf -V, dalfox version"
echo ""
echo "✅ Security tools installation complete!"

