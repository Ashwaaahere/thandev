# Security Scan Presets

This directory contains YAML configuration files for the three security scan levels supported by Thandev.

## Scan Levels

### Level 0 - Surface (Quick)
- **Purpose**: Very fast, low-noise footprinting and tech checks
- **Duration**: 3-8 minutes
- **Tools**: nuclei (info, technologies), sslscan/sslyze/openssl, nmap (--top-ports 100 -sV -Pn)
- **Cloud Run Job**: thandev-surface

### Level 1 - Discovery (Buzz)
- **Purpose**: Broaden surface, find hidden endpoints and subdomains
- **Duration**: 10-25 minutes
- **Tools**: Everything in Level 0 plus:
  - subfinder/amass (passive enumeration)
  - crt.sh/certificate-transparency lookups
  - ffuf/gobuster (directory discovery with small tuned wordlist)
  - nuclei medium templates (misconfig/exposures)
- **Cloud Run Job**: thandev-buzz

### Level 2 - Active (Non-destructive)
- **Purpose**: More aggressive detection (non-exploitative) and CVE checks
- **Duration**: 20-45 minutes
- **Tools**: Everything in Level 1 plus:
  - nuclei (CVE/exposure templates at medium severity)
  - nikto (HTTP server checks)
  - nmap with safe NSE scripts and service detection (-sC -sV)
- **Cloud Run Job**: thandev-active

## Preset Structure

Each preset YAML file contains:
- `name`: Human-readable name
- `version`: Preset version for tracking
- `description`: Brief description of the scan level
- `tier`: Internal tier identifier (level0, level1, level2)
- `preset_name`: Preset name for Cloud Run Job mapping
- `cloud_run_job`: Cloud Run Job name to execute
- `estimated_duration`: Expected scan duration
- `tools`: List of tools with configurations
- `steps`: Ordered execution steps
- `outputs`: Expected output files

## Tool Fallbacks

Tools may have fallback options if the primary tool is unavailable:
- sslscan → sslyze → openssl s_client
- subfinder → amass
- ffuf → gobuster

## Notes

- Levels 0-2 do NOT require DNS TXT verification
- Level 3+ (not in scope) will have different gating requirements
- All scans are non-destructive and safe for production environments
