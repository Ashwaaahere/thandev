# Critical Bugs Fixed

## Bug #1: Missing Zap in Tool Matrix
**Status**: ✅ FIXED
**Issue**: Zap was not included in tool_matrix.py, so it wouldn't run when brain service was disabled.
**Fix**: Added Zap to all scan levels in tool_matrix.py with appropriate modes and timeouts.

## Bug #2: Mode ID Extraction Bug
**Status**: ✅ FIXED
**Issue**: `runner_client.py` only checked for `"mode"` field, but tool_matrix uses:
- `"profile"` for nuclei/nmap
- `"intensity"` for httpx
- No mode specified for sslscan/dalfox/sqlmap

This caused invalid mode_ids like "nuclei-default", "httpx-default" which don't exist in catalog.

**Fix**: Updated `runner_client.py` to properly convert:
- `profile` → `mode_id` for nuclei/nmap
- `intensity` → `mode_id` for httpx
- Default to "standard" for sslscan
- Default to "standard" for dalfox
- Default to "sqli_light" for sqlmap

## Bug #3: Invalid Nmap Mode
**Status**: ✅ FIXED
**Issue**: tool_matrix had `{"key": "nmap", "mode": "comprehensive"}` but catalog only has "top_ports" and "full_ports_scripts".
**Fix**: Changed to `{"key": "nmap", "profile": "full_ports_scripts"}` to match catalog.

## Bug #4: Missing Zap Timeout for Advanced
**Status**: ✅ FIXED
**Issue**: Zap timeout was missing from scan_timeouts.py for advanced scans.
**Fix**: Added Zap timeout (1200s) for advanced scans.

## Bug #5: Missing Zap in Fallback Planner
**Status**: ✅ FIXED
**Issue**: Fallback planner in scan_orchestrator.py didn't include Zap.
**Fix**: Added Zap to fallback planner for all scan levels.

## Files Modified

1. `backend/app/core/tool_matrix.py`
   - Added Zap to all scan levels
   - Fixed nmap mode from "comprehensive" to "full_ports_scripts"

2. `backend/app/core/scan_timeouts.py`
   - Added Zap timeout for advanced scans

3. `backend/app/services/runner_client.py`
   - Fixed mode_id extraction to handle profile/intensity fields
   - Added proper defaults for tools without explicit mode

4. `backend/app/services/scan_orchestrator.py`
   - Added Zap to fallback planner

## Testing Checklist

- [ ] Test basic scan with brain disabled - verify Zap runs
- [ ] Test pro scan with brain disabled - verify Zap runs
- [ ] Test advanced scan with brain disabled - verify Zap runs
- [ ] Verify all tools get correct mode_id (nuclei, httpx, nmap, sslscan, dalfox, sqlmap, zap)
- [ ] Verify findings appear in UI for all tools
- [ ] Check logs for any catalog validation errors


