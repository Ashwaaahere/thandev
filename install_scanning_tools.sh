#!/bin/bash
# Install all required scanning tools for Thandev
# This script installs tools without sudo when possible

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Installing Scanning Tools for Thandev                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

TOOLS_DIR="$HOME/.local/thandev-tools"
mkdir -p "$TOOLS_DIR/bin"

# Function to add to PATH
add_to_path() {
    local bin_path="$1"
    if ! echo "$PATH" | grep -q "$bin_path"; then
        echo "export PATH=\"$bin_path:\$PATH\"" >> ~/.bashrc
        export PATH="$bin_path:$PATH"
        echo "✓ Added $bin_path to PATH"
    fi
}

# 1. Install Go (required for Nuclei)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1: Installing Go (required for Nuclei)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v go &> /dev/null; then
    echo "✅ Go already installed: $(go version)"
else
    GO_VERSION="1.22.0"
    echo "Downloading Go ${GO_VERSION}..."
    cd /tmp
    wget -q "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" || {
        echo "❌ Failed to download Go. Trying alternative method..."
        curl -L "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz" -o "go${GO_VERSION}.linux-amd64.tar.gz" || {
            echo "❌ Error: Failed to download Go"
            exit 1
        }
    }
    
    echo "Installing Go to $HOME/.local/go..."
    rm -rf "$HOME/.local/go"
    tar -C "$HOME/.local" -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
    rm "/tmp/go${GO_VERSION}.linux-amd64.tar.gz"
    
    export PATH="$HOME/.local/go/bin:$PATH"
    export GOPATH="$HOME/go"
    echo 'export PATH="$HOME/.local/go/bin:$PATH"' >> ~/.bashrc
    echo 'export GOPATH="$HOME/go"' >> ~/.bashrc
    
    echo "✅ Go installed: $(go version)"
fi

# 2. Install Nuclei
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 2: Installing Nuclei (vulnerability scanner)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v nuclei &> /dev/null; then
    echo "✅ Nuclei already installed: $(nuclei -version 2>&1 | head -1)"
else
    export PATH="$HOME/.local/go/bin:$PATH"
    export GOPATH="$HOME/go"
    
    echo "Installing Nuclei via go install..."
    go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
    
    if [ -f "$HOME/go/bin/nuclei" ]; then
        ln -sf "$HOME/go/bin/nuclei" "$TOOLS_DIR/bin/nuclei"
        add_to_path "$TOOLS_DIR/bin"
        echo "✅ Nuclei installed successfully"
    else
        echo "❌ Failed to install Nuclei"
        exit 1
    fi
fi

# 3. Install Nmap
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 3: Installing Nmap (port scanner)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v nmap &> /dev/null; then
    echo "✅ Nmap already installed: $(nmap --version 2>&1 | head -1)"
else
    echo "⚠️  Nmap requires sudo to install via apt."
    echo "   You'll need to fix your sudo password first."
    echo ""
    echo "   To install Nmap after fixing sudo:"
    echo "   sudo apt update && sudo apt install -y nmap"
    echo ""
    echo "   Or try compiling from source (slower but no sudo needed)..."
    
    # Alternative: Try to compile from source
    read -p "Attempt to compile Nmap from source? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Downloading Nmap source..."
        cd /tmp
        wget -q "https://nmap.org/dist/nmap-7.95.tar.bz2" || {
            curl -L "https://nmap.org/dist/nmap-7.95.tar.bz2" -o "nmap-7.95.tar.bz2" || {
                echo "❌ Failed to download Nmap source"
                exit 1
            }
        }
        
        tar -xjf "nmap-7.95.tar.bz2"
        cd "nmap-7.95"
        
        echo "Configuring Nmap..."
        ./configure --prefix="$TOOLS_DIR" --without-zenmap --without-nmap-update
        
        echo "Compiling Nmap (this may take 10-20 minutes)..."
        make -j$(nproc)
        
        echo "Installing Nmap..."
        make install
        
        cd ~
        rm -rf "/tmp/nmap-7.95" "/tmp/nmap-7.95.tar.bz2"
        
        add_to_path "$TOOLS_DIR/bin"
        echo "✅ Nmap installed successfully"
    else
        echo "⏭️  Skipping Nmap installation. Install manually when sudo is available."
    fi
fi

# 4. Install SSLScan
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 4: Installing SSLScan (TLS/SSL analyzer)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v sslscan &> /dev/null; then
    echo "✅ SSLScan already installed: $(sslscan --version 2>&1 | head -1)"
else
    echo "⚠️  SSLScan requires sudo to install via apt."
    echo "   Note: OpenSSL is already installed and can be used as fallback."
    echo ""
    echo "   To install SSLScan after fixing sudo:"
    echo "   sudo apt update && sudo apt install -y sslscan"
    echo ""
    echo "   The system will use OpenSSL as a fallback if SSLScan is not available."
fi

# 5. Install Lighthouse (optional)
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 5: Installing Lighthouse (performance scanner)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

if command -v lighthouse &> /dev/null || npm list -g lighthouse 2>&1 | grep -q lighthouse; then
    echo "✅ Lighthouse already installed"
else
    echo "Installing Lighthouse globally via npm..."
    npm install -g lighthouse
    
    if command -v lighthouse &> /dev/null; then
        echo "✅ Lighthouse installed successfully"
    else
        echo "⚠️  Lighthouse installation completed but may not be in PATH"
        echo "   Note: Lighthouse can also run via Cloud Run service"
    fi
fi

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    INSTALLATION SUMMARY                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Installed:"
command -v nuclei > /dev/null && echo "  ✓ Nuclei: $(nuclei -version 2>&1 | head -1)" || echo "  ✗ Nuclei"
command -v nmap > /dev/null && echo "  ✓ Nmap: $(nmap --version 2>&1 | head -1)" || echo "  ✗ Nmap"
command -v sslscan > /dev/null && echo "  ✓ SSLScan: $(sslscan --version 2>&1 | head -1)" || echo "  ✗ SSLScan (OpenSSL fallback available)"
command -v lighthouse > /dev/null && echo "  ✓ Lighthouse: $(lighthouse --version 2>&1 | head -1)" || (npm list -g lighthouse 2>&1 | grep -q lighthouse && echo "  ✓ Lighthouse: Installed (via npm)" || echo "  ✗ Lighthouse (Cloud Run alternative available)")

echo ""
echo "📝 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Reload your shell configuration:"
echo "   source ~/.bashrc"
echo ""
echo "2. For Nmap/SSLScan (if not installed):"
echo "   - Fix sudo password: wsl -u root passwd shree"
echo "   - Then run: sudo apt update && sudo apt install -y nmap sslscan"
echo ""
echo "3. Test your tools:"
echo "   nuclei -version"
echo "   nmap --version"
echo "   lighthouse --version"
echo ""












