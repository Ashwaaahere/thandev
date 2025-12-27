#!/bin/bash
# Test tool availability and executability

set -e

echo "=========================================="
echo "Thandev Tool Availability Tests"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

check_tool() {
    local tool_name=$1
    local check_cmd=$2
    local install_hint=$3
    
    if eval "$check_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $tool_name available"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $tool_name not found"
        if [ -n "$install_hint" ]; then
            echo "  Install: $install_hint"
        fi
        ((FAILED++))
        return 1
    fi
}

echo ""
echo "1. Testing Security Tools..."

# Nuclei
check_tool "nuclei" "nuclei -version" "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"

# Nmap
check_tool "nmap" "nmap --version" "sudo apt-get install nmap (or brew install nmap)"

# SSLScan
if sslscan --version > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} sslscan available"
    ((PASSED++))
elif openssl version > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠${NC} sslscan not found, but openssl available (fallback will be used)"
    ((PASSED++))
else
    echo -e "${RED}✗${NC} sslscan not found and openssl not available"
    echo "  Install: sudo apt-get install sslscan"
    ((FAILED++))
fi

# HTTPx (ProjectDiscovery, not Python httpx)
if httpx -version > /dev/null 2>&1; then
    # Verify it's ProjectDiscovery httpx (Python httpx doesn't have -version)
    if httpx -u https://example.com -silent -json > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} httpx (ProjectDiscovery) available"
        ((PASSED++))
    else
        echo -e "${YELLOW}⚠${NC} httpx found but may be Python httpx (not ProjectDiscovery)"
        echo "  Install: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"
        ((FAILED++))
    fi
else
    echo -e "${RED}✗${NC} httpx (ProjectDiscovery) not found"
    echo "  Install: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"
    ((FAILED++))
fi

# FFuF
check_tool "ffuf" "ffuf -V" "go install -v github.com/ffuf/ffuf/v2@latest"

# Dalfox
check_tool "dalfox" "dalfox version" "go install github.com/hahwul/dalfox/v2@latest"

# SQLMap (in venv)
cd "$(dirname "$0")/../backend" || exit 1
if [ -d "venv" ] && [ -f "venv/bin/sqlmap" ]; then
    if venv/bin/sqlmap --version > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} sqlmap available (in venv)"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} sqlmap in venv but not executable"
        ((FAILED++))
    fi
else
    echo -e "${YELLOW}⚠${NC} sqlmap not found in venv"
    echo "  Install: cd backend && source venv/bin/activate && pip install sqlmap"
    ((FAILED++))
fi

echo ""
echo "2. Testing Wordlists..."

cd "$(dirname "$0")/../backend" || exit 1
if [ -f "wordlists/ffuf-small.txt" ]; then
    if [ -s "wordlists/ffuf-small.txt" ]; then
        word_count=$(wc -l < wordlists/ffuf-small.txt)
        echo -e "${GREEN}✓${NC} ffuf wordlist exists ($word_count lines)"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC} ffuf wordlist is empty"
        ((FAILED++))
    fi
else
    echo -e "${RED}✗${NC} ffuf wordlist not found: wordlists/ffuf-small.txt"
    echo "  Create wordlist file or set THANDEV_FFUF_WORDLIST environment variable"
    ((FAILED++))
fi

echo ""
echo "3. Testing Tool Detection (Python)..."
cd "$(dirname "$0")/../backend" || exit 1

if python3 -c "
from app.services.tools import ToolExecutor
executor = ToolExecutor()
tool_ids = ['nuclei', 'nmap', 'httpx', 'ffuf', 'dalfox', 'sqlmap']
all_available, missing = executor.check_tool_dependencies(tool_ids)
if all_available:
    print('All tools detected by Python')
    exit(0)
else:
    print(f'Missing tools: {missing}')
    exit(1)
" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} All tools detected by Python ToolExecutor"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠${NC} Some tools not detected by Python ToolExecutor"
    echo "  This may be due to PATH issues or tool location"
    ((FAILED++))
fi

echo ""
echo "=========================================="
echo "Summary: ${GREEN}${PASSED} passed${NC}, ${RED}${FAILED} failed${NC}"
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi

