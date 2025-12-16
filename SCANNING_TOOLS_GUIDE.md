# Scanning Tools Guide for Thandev

This document describes the additional scanning tools used in Thandev and how they execute.

## Tool Overview

### 1. **httpx** (ProjectDiscovery) - HTTP Probe/Reconnaissance
- **Purpose**: HTTP probing, technology detection, title extraction, TLS probing
- **Wordlist Required**: ❌ No
- **How it executes**:
  ```bash
  httpx -u <target_url> -json -follow-redirects -status-code -title -tech-detect -tls-probe -silent
  ```
- **Installation**: 
  ```bash
  go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
  ```
- **Important**: This is **NOT** the Python `httpx` HTTP client library. We need ProjectDiscovery's `httpx` security scanner.
- **Used in**: Basic, Pro, Advanced scans (with different intensity levels)

### 2. **ffuf** - Content Discovery/Brute-Forcer
- **Purpose**: Directory and file brute-forcing, finding hidden endpoints
- **Wordlist Required**: ✅ **YES** - Required
- **Required Wordlists**:
  - `ffuf-pro.txt` - For Pro level scans (900 second timeout)
  - `ffuf-advanced.txt` - For Advanced level scans (1800 second timeout)
  - Default fallback: `ffuf-small.txt` (exists)
- **How it executes**:
  ```bash
  ffuf -u <target_url>/FUZZ -w <wordlist_path> -mc 200,204,301,302,307,401,403 -json
  ```
- **Installation**:
  ```bash
  go install -v github.com/ffuf/ffuf/v2@latest
  ```
- **Wordlist Location**: `wordlists/` directory in project root
- **Used in**: Pro, Advanced scans

### 3. **dalfox** - XSS (Cross-Site Scripting) Scanner
- **Purpose**: XSS vulnerability detection, DOM XSS analysis, parameter mining
- **Wordlist Required**: ❌ No (has built-in parameter mining dictionary)
- **How it executes**:
  ```bash
  dalfox url <target_url> --silence --format json --mining-dict --follow-redirects --deep-domxss --detailed-analysis
  ```
- **Installation**:
  ```bash
  go install github.com/hahwul/dalfox/v2@latest
  ```
- **Used in**: Pro, Advanced scans

### 4. **sqlmap** - SQL Injection Scanner
- **Purpose**: SQL injection detection and exploitation, database fingerprinting
- **Wordlist Required**: ❌ No
- **How it executes**:
  ```bash
  sqlmap -u <target_url> --batch --risk=1 --level=1 --timeout=10 --time-sec=5 --random-agent -v 0 --output-dir <output_dir>
  ```
- **Installation**:
  ```bash
  pip install sqlmap
  # OR download from: https://github.com/sqlmapproject/sqlmap
  ```
- **Used in**: Advanced scans only

## Tool Execution Flow

### Basic Scan Level
- httpx (low intensity)
- nuclei (basic_web profile)

### Pro Scan Level
- httpx (medium intensity)
- nuclei (pro_web profile)
- **ffuf** (with `ffuf-pro.txt` wordlist, 15 min timeout)
- nmap (top ports)
- sslscan
- **dalfox** (15 min timeout)

### Advanced Scan Level
- httpx (high intensity)
- nuclei (advanced_web profile)
- **ffuf** (with `ffuf-advanced.txt` wordlist, 30 min timeout)
- nmap (full ports with scripts)
- sslscan
- **dalfox** (30 min timeout)
- **sqlmap** (15 min timeout)

## Wordlist Requirements

### Current Status
- ✅ `ffuf-small.txt` - EXISTS (87,664 lines, 709KB)
- ❌ `ffuf-pro.txt` - MISSING (needed for Pro scans)
- ❌ `ffuf-advanced.txt` - MISSING (needed for Advanced scans)

### Wordlist Sources
Common wordlist sources:
- SecLists: https://github.com/danielmiessler/SecLists
- DirBuster/OWASP wordlists
- Custom wordlists for specific technologies

### Creating Wordlists
You can:
1. Use existing wordlists from SecLists
2. Combine multiple wordlists
3. Create custom wordlists for your needs

## Installation Summary

All tools are installed via Go (except sqlmap which uses pip):

```bash
# Ensure Go is in PATH (already installed)
export PATH="$HOME/.local/go/bin:$HOME/go/bin:$PATH"

# Install tools
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
go install -v github.com/ffuf/ffuf/v2@latest
go install github.com/hahwul/dalfox/v2@latest

# Install sqlmap (Python)
pip install sqlmap
```

## Tool Detection

The system automatically detects tools in this order:
1. `~/go/bin/` (most common for Go tools)
2. `/usr/local/bin/`
3. System PATH

Tools are verified before execution to ensure the correct binaries are found.









