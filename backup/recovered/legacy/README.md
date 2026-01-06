# LEGACY - v1 Security Scan Pipeline

**⚠️ LEGACY CODE - NOT USED IN v2 ARCHITECTURE ⚠️**

This folder contains documentation and remnants of the old v1 security scan pipeline that has been replaced by the Cloud Run-based v2 architecture.

## What Was Removed

The following functions were removed from `backend/app/routers/security.py` as part of the v2 migration:

- `run_local_scan_sync()` - Synchronous local scan execution
- `run_local_scan()` - Asynchronous wrapper for local scans
- `run_nuclei_scan()` - Direct Nuclei subprocess execution from API router
- `run_nmap_scan()` - Direct Nmap subprocess execution from API router
- `run_ssl_scan()` - Direct SSL scan subprocess execution from API router
- `run_ffuf_scan()` - Direct ffuf subprocess execution from API router
- `run_nikto_scan()` - Direct Nikto subprocess execution from API router
- Any PDF report generation functions (if they existed)

## v1 Architecture (Removed)

The old v1 architecture had these characteristics:
- **Single-tool scans**: Direct subprocess calls from FastAPI router
- **Local execution**: All scanning happened in the backend process
- **Synchronous blocking**: Scans blocked the API request thread
- **No separation**: Scanning logic mixed with API routing logic

## v2 Architecture (Current)

The new v2 architecture:
- **Cloud Run Services**: All scanning happens in separate Cloud Run services
- **Async orchestration**: Backend only orchestrates via HTTP calls
- **Separation of concerns**: Scanning logic in `cloud-run/security-scanner/`
- **Scalable**: Can handle multiple concurrent scans without blocking

## Migration Notes

- All scanning now happens in `cloud-run/security-scanner/scanner.py`
- Backend router (`app/routers/security.py`) only manages job state and calls Cloud Run
- Preset configurations moved to `backend/presets/*.yaml`
- No local subprocess execution in backend routers

## Files in This Legacy Folder

- `README.md` (this file) - Documentation of removed v1 code
- `v1_security_scan_patterns.py` - Placeholder documenting old patterns



