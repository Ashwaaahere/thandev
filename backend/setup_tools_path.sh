#!/bin/bash
# Setup script to ensure scanning tools are in PATH for backend processes
# This should be sourced before running the backend

# Add Go tools to PATH
export PATH="$HOME/.local/thandev-tools/bin:$HOME/go/bin:$HOME/.local/go/bin:$PATH"

# Export for subprocesses
export GOPATH="$HOME/go"

# Verify tools are accessible
echo "🔧 Setting up tool paths for backend..."
echo "PATH updated to include scanning tools"
echo ""
echo "Verifying tools:"
which nuclei > /dev/null && echo "  ✅ nuclei: $(nuclei -version 2>&1 | head -1 | grep -o 'v[0-9.]*' || echo 'found')" || echo "  ❌ nuclei: not found"
which ffuf > /dev/null && echo "  ✅ ffuf: $(ffuf -V 2>&1 | head -1)" || echo "  ❌ ffuf: not found"
which dalfox > /dev/null && echo "  ✅ dalfox: found" || echo "  ❌ dalfox: not found"
which sqlmap > /dev/null && echo "  ✅ sqlmap: $(sqlmap --version 2>&1 | head -1)" || echo "  ❌ sqlmap: not found"
which httpx > /dev/null && echo "  ✅ httpx: found" || echo "  ❌ httpx: not found"

echo ""
echo "💡 To use in backend, source this script:"
echo "   source backend/setup_tools_path.sh"
echo ""
echo "Or add to your shell startup:"
echo "   echo 'source $HOME/ashwath/thandev/backend/setup_tools_path.sh' >> ~/.bashrc"












