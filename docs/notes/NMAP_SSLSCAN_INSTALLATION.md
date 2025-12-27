# Installing nmap and sslscan

## Issue
The system reported that `nmap` and `sslscan` are not available via `apt` on your system. They suggest using `snap` instead.

## Solution

### Option 1: Install via Snap (Recommended)

```bash
# Install nmap
sudo snap install nmap

# Verify installation
nmap --version

# Note: sslscan is not available via snap, see Option 2
```

After installing via snap, nmap will be available at `/snap/bin/nmap`. The installation script will create a symlink to make it accessible in your PATH.

### Option 2: Install sslscan

Since `sslscan` is not available via snap or apt on your system, you have these options:

#### Option 2a: Compile from Source (Recommended)

```bash
# Install build dependencies
sudo apt update
sudo apt install -y libssl-dev git make gcc

# Clone and compile sslscan
cd /tmp
git clone https://github.com/rbsec/sslscan.git
cd sslscan
make static
sudo make install

# Verify
sslscan --version
```

#### Option 2b: Use OpenSSL Fallback (No Installation Needed)

The Thandev system has a built-in fallback that uses `openssl s_client` if `sslscan` is not available. This means:
- ✅ SSL scanning will still work
- ✅ You don't need to install sslscan if you're okay with the fallback
- ⚠️ The fallback may have fewer features than sslscan

The fallback is implemented in `backend/app/services/tools.py` in the `_run_sslscan()` method.

### Option 3: Use the Installation Script

Run the provided script:

```bash
cd /home/ashwath/thandev
./install_nmap_sslscan.sh
```

This script will:
1. Try to install nmap via snap
2. Attempt to compile sslscan from source
3. Provide manual instructions if needed

## Verification

After installation, verify both tools:

```bash
# Check nmap
nmap --version

# Check sslscan (if installed)
sslscan --version

# Or verify via the verification script
cd /home/ashwath/thandev
./verify_security_tools.sh
```

## Impact on Thandev

### Without nmap/sslscan:
- ✅ **Basic scans**: Fully functional (httpx + nuclei)
- ⚠️ **Pro scans**: Will work but without nmap port scanning and sslscan
- ⚠️ **Advanced scans**: Will work but without nmap port scanning and sslscan

### With nmap/sslscan:
- ✅ **Basic scans**: Fully functional
- ✅ **Pro scans**: Fully functional with all tools
- ✅ **Advanced scans**: Fully functional with all tools

## Notes

1. **Snap Installation**: When installed via snap, nmap is available at `/snap/bin/nmap`. The system will find it automatically if it's in your PATH.

2. **SSLScan Fallback**: The system gracefully falls back to OpenSSL if sslscan is not available, so SSL scanning functionality is not completely lost.

3. **Tool Detection**: The Thandev system automatically detects tools in this order:
   - `~/go/bin/` (for Go tools)
   - `~/.local/bin/` (for user-installed tools)
   - `/snap/bin/` (for snap-installed tools)
   - System PATH

4. **WSL Considerations**: If you're using WSL, snap may require additional setup. In that case, compiling from source or using the OpenSSL fallback may be more reliable.

## Quick Commands

```bash
# Install nmap only (quickest)
sudo snap install nmap

# Install both (if you want full functionality)
sudo snap install nmap
sudo apt install -y libssl-dev git make gcc
cd /tmp && git clone https://github.com/rbsec/sslscan.git && cd sslscan && make static && sudo make install

# Or just use the fallback (no installation needed)
# The system will automatically use OpenSSL for SSL scanning
```

