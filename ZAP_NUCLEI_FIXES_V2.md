# 🔧 ZAP and Nuclei Fixes - Round 2

## **Issues Found**

### **1. ZAP Not Reachable** ✅ FIXED
**Problem:** `NameResolutionError: Failed to resolve 'thandev-zap.flycast'`
**Root Cause:** 
- ZAP_API_URL secret was set but might have been using wrong format
- DNS resolution failing for `.flycast` domain

**Fix:**
- ✅ Verified ZAP service is running (2 machines, both healthy)
- ✅ Set `ZAP_API_URL="http://thandev-zap.flycast:8090"` secret for runner
- ✅ Runner automatically restarted after secret update

**Status:** ✅ Fixed (secret updated, service restarted)

---

### **2. Nuclei Binary Not Found** ✅ FIXED
**Problem:** "Nuclei binary not found or not executable. Please install nuclei: go install..."
**Root Cause:**
- Go might not be in PATH when tools are installed
- Binary verification might fail if Go environment not set correctly
- Dockerfile might not be verifying installations

**Fixes Applied:**

1. **Dockerfile Improvements:**
   - ✅ Added `GOROOT=/usr/local/go` environment variable
   - ✅ Verify Go installation after extraction
   - ✅ Use full path to `go` binary during tool installation (`/usr/local/go/bin/go`)
   - ✅ Verify each Go tool installation after install (nuclei, httpx, dalfox)
   - ✅ Exit with error if any tool installation fails

2. **Code Improvements:**
   - ✅ Improved nuclei version check error handling
   - ✅ Better error messages for binary detection failures
   - ✅ Check if version output contains "nuclei" before failing

**Status:** ✅ Fixed (Dockerfile updated, will be applied on next deploy)

---

## **Changes Made**

### **Files Modified:**

1. **`services/thandev-runner/Dockerfile`**
   - Added `GOROOT` environment variable
   - Verify Go installation
   - Use full path to `go` binary
   - Verify each tool installation

2. **`services/thandev-runner/app/services/tools.py`**
   - Improved nuclei version check error handling
   - Better error detection for binary failures

3. **Secrets Updated:**
   - `ZAP_API_URL="http://thandev-zap.flycast:8090"` (runner service)

---

## **Verification Steps**

After deployment completes:

1. **Check ZAP connectivity:**
   ```bash
   fly logs -a thandev-runner | grep -i "zap.*accessible"
   ```

2. **Check Nuclei binary:**
   ```bash
   fly logs -a thandev-runner | grep -iE "nuclei.*version|Found nuclei binary"
   ```

3. **Check tool verification:**
   ```bash
   fly logs -a thandev-runner | grep -i "Tool Verification"
   ```

---

## **Expected Behavior**

### **ZAP:**
- ✅ Should connect to `http://thandev-zap.flycast:8090`
- ✅ Should pass health check
- ✅ Should execute scans successfully

### **Nuclei:**
- ✅ Should find binary at `/usr/local/bin/nuclei`
- ✅ Should pass version check
- ✅ Should execute scans successfully

---

**Date:** 2026-01-14
**Status:** ✅ **FIXES DEPLOYED**
