#!/bin/bash
# Verify all security tools and orchestration environment

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Verifying Security Tools & Orchestration Setup         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Setup PATH
export PATH="$HOME/.local/bin:$HOME/go/bin:$PATH"
export GOPATH="$HOME/go"

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

# 1. Check all security tools
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Security Tools Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Nuclei
if command_exists nuclei; then
    VERSION=$(nuclei -version 2>&1 | grep -oP 'v[\d.]+' | head -1)
    print_status "success" "Nuclei: $VERSION"
else
    print_status "error" "Nuclei: Not found"
fi

# httpx (ProjectDiscovery)
if [ -f "$HOME/go/bin/httpx" ]; then
    VERSION=$($HOME/go/bin/httpx -version 2>&1 | head -1 || echo "installed")
    print_status "success" "httpx: Installed ($VERSION)"
elif command_exists httpx; then
    VERSION=$(httpx -version 2>&1 | head -1 || echo "installed")
    print_status "success" "httpx: $VERSION"
else
    print_status "error" "httpx: Not found"
fi

# ffuf
if command_exists ffuf; then
    VERSION=$(ffuf -V 2>&1 | head -1)
    print_status "success" "ffuf: $VERSION"
else
    print_status "error" "ffuf: Not found"
fi

# dalfox
if command_exists dalfox; then
    VERSION=$(dalfox version 2>&1 | head -1 || echo "installed")
    print_status "success" "dalfox: Installed"
else
    print_status "error" "dalfox: Not found"
fi

# sqlmap (check in backend venv)
if command_exists sqlmap; then
    VERSION=$(sqlmap --version 2>&1 | head -1)
    print_status "success" "sqlmap: $VERSION"
elif [ -f "/home/ashwath/thandev/backend/venv/bin/sqlmap" ]; then
    VERSION=$(/home/ashwath/thandev/backend/venv/bin/sqlmap --version 2>&1 | head -1)
    print_status "success" "sqlmap: $VERSION (in backend venv)"
else
    print_status "error" "sqlmap: Not found"
fi

# nmap
if command_exists nmap; then
    VERSION=$(nmap --version 2>&1 | head -1)
    print_status "success" "nmap: $VERSION"
else
    print_status "warning" "nmap: Not installed (needs sudo: sudo apt install -y nmap)"
fi

# sslscan
if command_exists sslscan; then
    VERSION=$(sslscan --version 2>&1 | head -1)
    print_status "success" "sslscan: $VERSION"
else
    print_status "warning" "sslscan: Not installed (needs sudo: sudo apt install -y sslscan)"
fi

# Lighthouse
if command_exists lighthouse; then
    VERSION=$(lighthouse --version 2>&1 | head -1)
    print_status "success" "Lighthouse: $VERSION"
else
    print_status "warning" "Lighthouse: Not installed globally (Cloud Run alternative available)"
fi

# 2. Check wordlists
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Wordlist Status"
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

# 3. Check orchestration environment
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Orchestration Environment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Redis
if timeout 1 bash -c "echo > /dev/tcp/localhost/6379" 2>/dev/null; then
    print_status "success" "Redis: Running on port 6379"
else
    print_status "error" "Redis: Not running (start with: ./start_services_with_sudo.sh)"
fi

# Check Qdrant
if curl -s http://localhost:6333/health > /dev/null 2>&1; then
    print_status "success" "Qdrant: Running on port 6333"
else
    print_status "error" "Qdrant: Not running (start with: ./start_services_with_sudo.sh)"
fi

# Check tool_matrix.py
if [ -f "/home/ashwath/thandev/backend/app/core/tool_matrix.py" ]; then
    print_status "success" "Tool Matrix: Configured"
else
    print_status "error" "Tool Matrix: Missing"
fi

# Check WORDLISTS_DIR in runner config
RUNNER_CONFIG="/home/ashwath/thandev/services/thandev-runner/app/config.py"
if grep -q "WORDLISTS_DIR.*thandev/wordlists" "$RUNNER_CONFIG" 2>/dev/null; then
    print_status "success" "Runner Config: WORDLISTS_DIR configured"
else
    print_status "warning" "Runner Config: WORDLISTS_DIR may need update"
fi

# 4. Check virtual environments
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Virtual Environments"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ -d "/home/ashwath/thandev/backend/venv" ] && print_status "success" "Backend venv: Exists" || print_status "error" "Backend venv: Missing"
[ -d "/home/ashwath/thandev/services/thandev-brain/venv" ] && print_status "success" "Thandev-brain venv: Exists" || print_status "error" "Thandev-brain venv: Missing"
[ -d "/home/ashwath/thandev/services/thandev-runner/venv" ] && print_status "success" "Thandev-runner venv: Exists" || print_status "error" "Thandev-runner venv: Missing"

# 5. Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    VERIFICATION SUMMARY                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

echo "📋 Required for Basic Scans:"
echo "   - httpx: $(command_exists httpx && echo '✅' || echo '❌')"
echo "   - nuclei: $(command_exists nuclei && echo '✅' || echo '❌')"
echo ""

echo "📋 Required for Pro Scans:"
echo "   - httpx: $(command_exists httpx && echo '✅' || echo '❌')"
echo "   - nuclei: $(command_exists nuclei && echo '✅' || echo '❌')"
echo "   - ffuf: $(command_exists ffuf && echo '✅' || echo '❌')"
echo "   - nmap: $(command_exists nmap && echo '✅' || echo '❌')"
echo "   - sslscan: $(command_exists sslscan && echo '✅' || echo '❌')"
echo "   - dalfox: $(command_exists dalfox && echo '✅' || echo '❌')"
echo ""

echo "📋 Required for Advanced Scans:"
echo "   - All Pro tools: $(command_exists httpx && command_exists nuclei && command_exists ffuf && command_exists dalfox && echo '✅' || echo '❌')"
echo "   - sqlmap: $([ -f "/home/ashwath/thandev/backend/venv/bin/sqlmap" ] || command_exists sqlmap && echo '✅' || echo '❌')"
echo ""

echo "📋 Infrastructure:"
echo "   - Redis: $(timeout 1 bash -c "echo > /dev/tcp/localhost/6379" 2>/dev/null && echo '✅' || echo '❌')"
echo "   - Qdrant: $(curl -s http://localhost:6333/health > /dev/null 2>&1 && echo '✅' || echo '❌')"
echo "   - Wordlists: $([ -f "$WORDLISTS_DIR/ffuf-pro.txt" ] && echo '✅' || echo '❌')"
echo ""

echo "✅ Verification complete!"

