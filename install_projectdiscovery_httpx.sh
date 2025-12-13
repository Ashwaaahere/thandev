#!/bin/bash
# Install ProjectDiscovery httpx scanner
# This is different from Python httpx (HTTP client library)

echo "Installing ProjectDiscovery httpx security scanner..."
echo ""

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "❌ Go is not installed. Please install Go first:"
    echo "   https://golang.org/doc/install"
    exit 1
fi

echo "✅ Go found: $(go version)"
echo ""

# Install httpx
echo "Installing httpx via go install..."
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ httpx installed successfully!"
    echo ""
    echo "Binary location: ~/go/bin/httpx"
    echo ""
    echo "To make it available system-wide, add to PATH:"
    echo "  export PATH=\$PATH:~/go/bin"
    echo ""
    echo "Or create a symlink:"
    echo "  sudo ln -s ~/go/bin/httpx /usr/local/bin/httpx-projectdiscovery"
    echo ""
    echo "Testing installation..."
    ~/go/bin/httpx -u https://example.com -json -silent 2>&1 | head -5
else
    echo "❌ Installation failed. Check error messages above."
    exit 1
fi
