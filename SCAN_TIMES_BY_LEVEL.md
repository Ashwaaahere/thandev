# Scan Times by Level

This document provides a comprehensive overview of scan times for each scan level (Basic, Pro, Advanced).

## Scan Level Overview

### BASIC Level
**Total Scan Time:** ~8-10 minutes  
**Max Total Timeout:** 10 minutes (600 seconds)

**Tools & Timeouts:**
- **httpx**: 30 seconds
- **nuclei**: 3 minutes (180 seconds)
- **zap** (passive_spider): 5 minutes (300 seconds)

**Expected Behavior:**
- Fast, lightweight scan
- Tools run in parallel (up to 5 concurrent)
- Typically completes in 8-10 minutes
- Best for quick security checks

---

### PRO Level
**Total Scan Time:** ~30-60 minutes  
**Max Total Timeout:** 60 minutes (3600 seconds)

**Tools & Timeouts:**
- **httpx**: 30 seconds
- **nuclei**: 30 minutes (1800 seconds)
- **nmap**: 10 minutes (600 seconds)
- **sslscan**: 5 minutes (300 seconds)
- **dalfox**: 25 minutes (1500 seconds)
- **zap** (active_scan): 30 minutes (1800 seconds)

**Expected Behavior:**
- Comprehensive scan for medium-sized web apps
- Tools run in parallel (up to 10 concurrent)
- Longest tools: nuclei (30min) or zap (30min)
- Typically completes in 30-60 minutes
- Best for thorough security assessments

---

### ADVANCED Level
**Total Scan Time:** ~40-90 minutes  
**Max Total Timeout:** 1.5 hours (5400 seconds)

**Tools & Timeouts:**
- **httpx**: 30 seconds
- **nuclei**: 30 minutes (1800 seconds)
- **nmap**: 30 minutes (1800 seconds)
- **sslscan**: 3 minutes (180 seconds)
- **dalfox**: 40 minutes (2400 seconds)
- **sqlmap**: 40 minutes (2400 seconds)
- **zap** (ajax_spider): 10 minutes (600 seconds) - runs first
- **zap** (active_scan): 30 minutes (1800 seconds) - runs after ajax_spider
- **Total ZAP time**: 45 minutes (2700 seconds) - accounts for both modes + passive scanning

**Expected Behavior:**
- Deep security assessment for complex targets
- Tools run in parallel (up to 8 concurrent)
- Longest tools: dalfox (40min), sqlmap (40min), zap (45min total)
- Typically completes in 40-90 minutes
- Best for comprehensive security audits

---

## ZAP Timeout Details

### Why ZAP Needs More Time in Advanced Scans

Advanced scans run ZAP in **two sequential modes**:

1. **AJAX Spider** (10 minutes / 600 seconds)
   - Crawls JavaScript-heavy applications
   - Discovers dynamic content
   - Builds scan tree

2. **Active Scan** (30 minutes / 1800 seconds)
   - Performs active vulnerability testing
   - Tests for various security issues
   - Generates security alerts

**Plus passive scanning** throughout the process.

**Total ZAP Time:** Up to 45 minutes (2700 seconds) to allow for:
- AJAX spider completion
- Active scan completion
- Passive scanning processing
- Alert generation and retrieval

### Previous Issue
- ZAP was timing out after ~25 minutes (1534 seconds)
- This was because the timeout was set to 20 minutes (1200 seconds)
- Advanced scans need more time for both ZAP modes

### Fix Applied
- Increased ZAP timeout for advanced scans from 20 minutes to **45 minutes (2700 seconds)**
- This ensures ZAP has enough time to complete both ajax_spider and active_scan modes
- Matches the actual time needed for comprehensive ZAP testing

---

## Summary Table

| Scan Level | Total Timeout | Typical Duration | Longest Tool | Tools Count |
|------------|---------------|------------------|--------------|-------------|
| **Basic**  | 10 minutes    | 8-10 minutes     | zap (5 min)  | 3 tools     |
| **Pro**    | 60 minutes   | 30-60 minutes    | nuclei/zap (30 min) | 6 tools |
| **Advanced** | 90 minutes | 40-90 minutes | dalfox/sqlmap/zap (40-45 min) | 8 tools |

---

## Notes

- **Actual scan times** may vary based on:
  - Target application size and complexity
  - Network latency
  - Number of endpoints discovered
  - Tool execution speed

- **Timeouts are safety limits** - scans typically complete before hitting timeouts

- **Parallel execution** means total scan time is determined by the longest-running tool, not the sum of all tool times

- **ZAP in advanced scans** requires the most time due to running multiple modes sequentially
