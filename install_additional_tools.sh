#!/bin/bash
# Install httpx, ffuf, dalfox, and sqlmap for Thandev
# These are additional scanning tools beyond the core tools

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Installing Additional Scanning Tools for Thandev         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

TOOLS_DIR="$HOME/.local/thandev-tools"
mkdir -p "$TOOLS_DIR/bin"

# Load Go environment
export PATH="$HOME/.local/go/bin:$PATH"
export GOPATH="$HOME/go"

# Function to add to PATH
add_to_path() {
    local bin_path="$1"
    if ! echo "$PATH" | grep -q "$bin_path"; then
        echo "export PATH=\"$bin_path:\$PATH\"" >> ~/.bashrc
        export PATH="$bin_path:$PATH"
        echo "✓ Added $bin_path to PATH"
    fi
}

# 1. Install httpx (ProjectDiscovery)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1: Installing httpx (ProjectDiscovery HTTP probe)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v httpx &> /dev/null; then
    # Test if it's ProjectDiscovery httpx (not Python httpx)
    if httpx -u https://example.com -silent 2>&1 | grep -q "No such option\|required dependencies"; then
        echo "⚠️  Python httpx detected (not ProjectDiscovery httpx)"
        echo "Installing ProjectDiscovery httpx..."
    else
        echo "✅ ProjectDiscovery httpx already installed: $(httpx -version 2>&1 | head -1)"
        INSTALL_HTTPX=false
    fi
else
    INSTALL_HTTPX=true
fi

if [ "$INSTALL_HTTPX" = true ]; then
    go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
    
    if [ -f "$HOME/go/bin/httpx" ]; then
        ln -sf "$HOME/go/bin/httpx" "$TOOLS_DIR/bin/httpx"
        add_to_path "$TOOLS_DIR/bin"
        echo "✅ httpx installed successfully"
    else
        echo "❌ Failed to install httpx"
    fi
fi

# 2. Install ffuf
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 2: Installing ffuf (content discovery)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v ffuf &> /dev/null; then
    echo "✅ ffuf already installed: $(ffuf -V 2>&1 | head -1)"
else
    go install -v github.com/ffuf/ffuf/v2@latest
    
    if [ -f "$HOME/go/bin/ffuf" ]; then
        ln -sf "$HOME/go/bin/ffuf" "$TOOLS_DIR/bin/ffuf"
        add_to_path "$TOOLS_DIR/bin"
        echo "✅ ffuf installed successfully"
    else
        echo "❌ Failed to install ffuf"
        exit 1
    fi
fi

# 3. Install dalfox
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 3: Installing dalfox (XSS scanner)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v dalfox &> /dev/null; then
    echo "✅ dalfox already installed: $(dalfox version 2>&1 | head -1)"
else
    go install github.com/hahwul/dalfox/v2@latest
    
    if [ -f "$HOME/go/bin/dalfox" ]; then
        ln -sf "$HOME/go/bin/dalfox" "$TOOLS_DIR/bin/dalfox"
        add_to_path "$TOOLS_DIR/bin"
        echo "✅ dalfox installed successfully"
    else
        echo "❌ Failed to install dalfox"
        exit 1
    fi
fi

# 4. Install sqlmap
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 4: Installing sqlmap (SQL injection scanner)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v sqlmap &> /dev/null; then
    echo "✅ sqlmap already installed: $(sqlmap --version 2>&1 | head -1)"
else
    cd /home/shree/ashwath/thandev/backend
    source .venv/bin/activate
    pip install sqlmap
    
    # Check if it's now in PATH
    if command -v sqlmap &> /dev/null; then
        echo "✅ sqlmap installed successfully"
    else
        echo "⚠️  sqlmap installed but may not be in PATH"
        echo "   Location: $(which sqlmap || echo 'Check .venv/bin')"
    fi
fi

# 5. Check wordlists
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 5: Checking wordlists for ffuf..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

WORDLISTS_DIR="/home/shree/ashwath/thandev/wordlists"
REQUIRED_WORDLISTS=("ffuf-pro.txt" "ffuf-advanced.txt")
MISSING_WORDLISTS=()

for wl in "${REQUIRED_WORDLISTS[@]}"; do
    if [ -f "$WORDLISTS_DIR/$wl" ]; then
        echo "✅ $wl exists ($(wc -l < "$WORDLISTS_DIR/$wl" | xargs) lines)"
    else
        echo "❌ $wl MISSING"
        MISSING_WORDLISTS+=("$wl")
    fi
done

if [ ${#MISSING_WORDLISTS[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  Missing wordlists detected!"
    echo "   The following wordlists are required for full functionality:"
    for wl in "${MISSING_WORDLISTS[@]}"; do
        echo "   - $wl"
    done
    echo ""
    echo "   You can:"
    echo "   1. Download wordlists from SecLists: https://github.com/danielmiessler/SecLists"
    echo "   2. Use existing wordlists (common.txt, ffuf-small.txt) as base"
    echo "   3. Create custom wordlists for your needs"
    echo ""
    echo "   Example to create from existing:"
    echo "   cp $WORDLISTS_DIR/ffuf-small.txt $WORDLISTS_DIR/ffuf-pro.txt"
    echo "   cp $WORDLISTS_DIR/ffuf-small.txt $WORDLISTS_DIR/ffuf-advanced.txt"
fi

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    INSTALLATION SUMMARY                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Installed Tools:"
export PATH="$TOOLS_DIR/bin:$HOME/go/bin:$PATH"
command -v httpx > /dev/null && echo "  ✓ httpx: $(httpx -version 2>&1 | head -1)" || echo "  ✗ httpx"
command -v ffuf > /dev/null && echo "  ✓ ffuf: $(ffuf -V 2>&1 | head -1)" || echo "  ✗ ffuf"
command -v dalfox > /dev/null && echo "  ✓ dalfox: $(dalfox version 2>&1 | head -1)" || echo "  ✗ dalfox"
command -v sqlmap > /dev/null && echo "  ✓ sqlmap: $(sqlmap --version 2>&1 | head -1)" || echo "  ✗ sqlmap"

echo ""
echo "📋 Wordlist Status:"
for wl in "ffuf-small.txt" "ffuf-pro.txt" "ffuf-advanced.txt"; do
    if [ -f "$WORDLISTS_DIR/$wl" ]; then
        lines=$(wc -l < "$WORDLISTS_DIR/$wl" | xargs)
        size=$(du -h "$WORDLISTS_DIR/$wl" | cut -f1)
        echo "  ✓ $wl ($lines lines, $size)"
    else
        echo "  ✗ $wl (MISSING)"
    fi
done

echo ""
echo "📝 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. Reload your shell: source ~/.bashrc"
echo "2. Test tools: httpx -version, ffuf -V, dalfox version, sqlmap --version"
if [ ${#MISSING_WORDLISTS[@]} -gt 0 ]; then
    echo "3. ⚠️  Add missing wordlists for full functionality"
fi
echo ""









