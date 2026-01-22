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
            # Check multiple possible locations
            if [ -f "/usr/local/bin/nuclei" ]; then
                echo "  Found at /usr/local/bin/nuclei"
                if /usr/local/bin/nuclei -version 2>&1 | head -1; then
                    echo "  ✅ Version check passed"
                else
                    echo "  ⚠️  Warning: Binary exists but version check failed (may still work)"
                fi
            elif [ -f "/usr/local/go/bin/nuclei" ]; then
                echo "  Found at /usr/local/go/bin/nuclei"
                if /usr/local/go/bin/nuclei -version 2>&1 | head -1; then
                    echo "  ✅ Version check passed"
                else
                    echo "  ⚠️  Warning: Binary exists but version check failed (may still work)"
                fi
            else
                echo "  ERROR: nuclei not found in PATH, /usr/local/bin, or /usr/local/go/bin"
                echo "  Attempting to list /usr/local/bin contents:"
                ls -la /usr/local/bin/ | grep -E "nuclei|go" || echo "  No nuclei or go binaries found"
                exit 1
            fi
        else
            exit 1
        fi
    fi
}

check_tool "nuclei" "nuclei -version"
check_tool "httpx" "httpx -version"
# ffuf removed - not used in tool_matrix.py (commented out in supported_tools)
check_tool "dalfox" "dalfox version"
check_tool "nmap" "nmap --version"
check_tool "sslscan" "sslscan --version"
check_tool "sqlmap" "sqlmap --version"
check_tool "retire" "retire --version"


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

