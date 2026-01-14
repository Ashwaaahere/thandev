#!/bin/bash
# Tool verification script for runner startup
# Logs tool versions, paths, and verifies wordlists directory

set -e

echo "=========================================="
echo "Thandev Runner - Tool Verification"
echo "=========================================="
echo ""

# Check tool versions and paths
echo "Tool Versions:"
echo "----------------------------------------"

check_tool() {
    local tool_name=$1
    local version_cmd=$2
    local which_cmd="which $tool_name"
    
    echo ""
    echo "Checking $tool_name:"
    if command -v "$tool_name" > /dev/null 2>&1; then
        local tool_path=$(command -v "$tool_name")
        echo "  Path: $tool_path"
        if eval "$version_cmd" > /dev/null 2>&1; then
            local version=$(eval "$version_cmd" 2>&1 | head -1)
            echo "  Version: $version"
        else
            echo "  Version: (unable to get version, but binary exists)"
            # Don't exit - binary exists, version check might fail for other reasons
        fi
    else
        echo "  ERROR: $tool_name not found in PATH"
        echo "  Checking common locations..."
        # Check common locations before failing
        if [ "$tool_name" = "nuclei" ]; then
            if [ -f "/usr/local/bin/nuclei" ]; then
                echo "  Found at /usr/local/bin/nuclei"
                /usr/local/bin/nuclei -version 2>&1 | head -1 || echo "  Warning: Binary exists but version check failed"
            else
                echo "  ERROR: nuclei not found in PATH or /usr/local/bin"
                exit 1
            fi
        else
            exit 1
        fi
    fi
}

check_tool "nuclei" "nuclei -version"
check_tool "httpx" "httpx -version"
check_tool "ffuf" "ffuf -V"
check_tool "dalfox" "dalfox version"
check_tool "nmap" "nmap --version"
check_tool "sslscan" "sslscan --version"
check_tool "sqlmap" "sqlmap --version"

echo ""
echo "=========================================="
echo "Wordlists Directory Verification"
echo "=========================================="
echo ""

WORDLISTS_DIR="${WORDLISTS_DIR:-/opt/thandev/wordlists}"

if [ -d "$WORDLISTS_DIR" ]; then
    echo "✓ WORDLISTS_DIR exists: $WORDLISTS_DIR"
    echo ""
    echo "Wordlist files:"
    find "$WORDLISTS_DIR" -type f -name "*.txt" | while read -r file; do
        size=$(du -h "$file" | cut -f1)
        echo "  - $(basename "$file") ($size)"
    done
    file_count=$(find "$WORDLISTS_DIR" -type f | wc -l)
    echo ""
    echo "Total files: $file_count"
else
    echo "ERROR: WORDLISTS_DIR does not exist: $WORDLISTS_DIR"
    exit 1
fi

echo ""
echo "=========================================="
echo "Tool Verification Complete"
echo "=========================================="
echo ""

