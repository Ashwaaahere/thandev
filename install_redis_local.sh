#!/bin/bash
# Install Redis locally without sudo
# This script compiles Redis from source and installs it to ~/.local/redis

set -e

REDIS_VERSION="7.2.4"
INSTALL_DIR="$HOME/.local/redis"
REDIS_DIR="$HOME/redis-$REDIS_VERSION"

echo "Installing Redis $REDIS_VERSION locally to $INSTALL_DIR..."

# Check if Redis is already installed
if [ -f "$INSTALL_DIR/bin/redis-server" ]; then
    echo "Redis is already installed at $INSTALL_DIR"
    echo "To start Redis, run: $INSTALL_DIR/bin/redis-server --daemonize yes"
    exit 0
fi

# Create install directory
mkdir -p "$INSTALL_DIR"

# Download Redis source
echo "Downloading Redis source..."
cd /tmp
wget -q "https://download.redis.io/releases/redis-$REDIS_VERSION.tar.gz" || {
    echo "Failed to download Redis. Trying alternative method..."
    curl -L "https://download.redis.io/releases/redis-$REDIS_VERSION.tar.gz" -o "redis-$REDIS_VERSION.tar.gz" || {
        echo "Error: Failed to download Redis source code"
        exit 1
    }
}

# Extract
echo "Extracting Redis source..."
tar -xzf "redis-$REDIS_VERSION.tar.gz"
cd "/tmp/redis-$REDIS_VERSION"

# Compile Redis
echo "Compiling Redis (this may take a few minutes)..."
make PREFIX="$INSTALL_DIR" -j$(nproc) || {
    echo "Compilation failed. Trying with single core..."
    make PREFIX="$INSTALL_DIR" || {
        echo "Error: Failed to compile Redis"
        exit 1
    }
}

# Install to local directory
echo "Installing Redis to $INSTALL_DIR..."
make PREFIX="$INSTALL_DIR" install

# Cleanup
cd ~
rm -rf "/tmp/redis-$REDIS_VERSION" "/tmp/redis-$REDIS_VERSION.tar.gz"

echo ""
echo "✓ Redis installed successfully!"
echo ""
echo "To start Redis server:"
echo "  $INSTALL_DIR/bin/redis-server --daemonize yes"
echo ""
echo "To stop Redis server:"
echo "  $INSTALL_DIR/bin/redis-cli shutdown"
echo ""
echo "Add to your ~/.bashrc:"
echo "  export PATH=\"\$HOME/.local/redis/bin:\$PATH\""

