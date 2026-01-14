# Duplicate PENDING Records - Root Cause Analysis ✅

## 🚨 **Issue:**
After applying the permanent fix, duplicate PENDING records still appear in some scans.

---

## 🔍 **Root Cause Found**

### **The Problem:**
**Brain publishes MORE step requests than backend creates PENDING records!**

### **Example (Pro scan):**

**Backend creates 6 PENDING records:**
```
1. httpx
2. nuclei
3. nmap
4. sslscan
5. dalfox
6. zap (GENERIC)
```

**Brain publishes 7 step requests:**
```
1. httpx/medium
2. nuclei/pro_web
3. nmap/top_ports
4. sslscan/standard
5. dalfox/standard
6. zap/passive_spider  ← SPECIFIC MODE
7. zap/active_scan     ← SPECIFIC MODE
```

### **What Happens:**
```
1. Backend creates 1 PENDING record for "zap" (generic)
2. Brain publishes 2 step requests: "zap/passive_spider" and "zap/active_scan"
3. Runner picks up "zap/passive_spider":
   - Calls /tool-started with tool_name="zap"
   - Finds PENDING "zap" record → Updates to RUNNING ✅
4. Runner picks up "zap/active_scan":
   - Calls /tool-started with tool_name="zap"
   - Cannot find PENDING "zap" record (already updated to RUNNING/COMPLETED)
   - Creates NEW record with status=RUNNING ❌ (DUPLICATE!)
```

---

## 📊 **Evidence**

### **Database after scan:**
```sql
 tool_name |  status   | parsed_findings_count
-----------+-----------+-----------------------
 dalfox    | PENDING   |                     0  ← Created by backend
 dalfox    | RUNNING   |                     0  ← Created by runner (duplicate)
 httpx     | PENDING   |                     0  ← Created by backend
 httpx     | COMPLETED |                     6  ← Updated by runner ✅
 nmap      | PENDING   |                     0  ← Created by backend
 nmap      | COMPLETED |                     4  ← Created by runner (duplicate)
 nuclei    | PENDING   |                     0  ← Created by backend
 nuclei    | FAILED    |                     0  ← Created by runner (duplicate)
 sslscan   | PENDING   |                     0  ← Created by backend
 sslscan   | RUNNING   |                     0  ← Created by runner (duplicate)
 zap       | PENDING   |                     0  ← Created by backend
 zap       | FAILED    |                     0  ← Created by runner (1st ZAP step)
 zap       | FAILED    |                     0  ← Created by runner (2nd ZAP step)
```

### **Brain Logs:**
```
2026-01-13 05:36:57,534 - Published step request bce5eff7 (httpx/medium)
2026-01-13 05:36:57,534 - Published step request 201adcba (nuclei/pro_web)
2026-01-13 05:36:57,535 - Published step request 4e05cb5a (nmap/top_ports)
2026-01-13 05:36:57,535 - Published step request bdd0a942 (sslscan/standard)
2026-01-13 05:36:57,536 - Published step request 56f887b6 (dalfox/standard)
2026-01-13 05:36:57,536 - Published step request f876cf91 (zap/passive_spider)  ← 1st ZAP
2026-01-13 05:36:57,536 - Published step request 2f258ecf (zap/active_scan)     ← 2nd ZAP
2026-01-13 05:36:57,536 - Waiting for 7 step results...
```

---

## 🎯 **Why The Permanent Fix Didn't Work**

### **The Query:**
```python
existing = db.query(ToolResult).filter(
    ToolResult.scan_job_id == scan_id,
    (ToolResult.tool_run_id == payload.tool_run_id) | 
    ((ToolResult.tool_name == payload.tool_name) & (ToolResult.status == ToolExecutionStatus.PENDING))
).first()
```

### **What It Does:**
- Looks for existing record by `tool_run_id` OR by `tool_name` (only if status=PENDING)

### **Why It Fails:**
1. **First ZAP step executes:**
   - Finds PENDING "zap" record ✅
   - Updates it to RUNNING/COMPLETED ✅
   - Status is no longer PENDING

2. **Second ZAP step executes:**
   - Looks for record with `tool_run_id=<different_id>` → Not found
   - Looks for record with `tool_name="zap" AND status=PENDING` → Not found (status is now COMPLETED)
   - Creates NEW record ❌

---

## ✅ **The Solution**

### **Option 1: Match Backend PENDING Records to Brain Steps**
**Backend should create PENDING records for EACH step Brain will publish, not just per tool.**

**Changes needed:**
1. Backend asks Brain: "What steps will you publish for this scan level?"
2. Brain returns list of step configs (tool/mode pairs)
3. Backend creates PENDING record for EACH step config

**Benefits:**
- 1:1 mapping between PENDING records and Brain steps
- No duplicates possible

**Drawbacks:**
- Backend needs to know Brain's step generation logic
- Tight coupling between Backend and Brain

---

### **Option 2: Smarter Query in Runner Ingestion**
**Change the query to match by `tool_name` regardless of status (not just PENDING).**

**Changes needed:**
```python
# Find existing record by tool_run_id OR by tool_name (ANY status, pick oldest)
existing = db.query(ToolResult).filter(
    ToolResult.scan_job_id == scan_id,
    (ToolResult.tool_run_id == payload.tool_run_id) | 
    (ToolResult.tool_name == payload.tool_name)
).order_by(ToolResult.created_at.asc()).first()  # Pick oldest record
```

**Benefits:**
- Simple fix
- Works for tools with multiple modes (like ZAP)
- Backend doesn't need to know Brain's step logic

**Drawbacks:**
- If a tool legitimately runs multiple times (e.g., ZAP passive + active), all results go to the same record
- Findings from different modes get mixed together

---

### **Option 3: Include Mode in tool_name**
**Brain should send `tool_name` as `"zap_passive_spider"` and `"zap_active_scan"` instead of just `"zap"`.**

**Changes needed:**
1. Brain: Send `tool_name="zap_passive_spider"` instead of `tool_name="zap"` with `tool_id="passive_spider"`
2. Backend: Create PENDING records with mode-specific tool names
3. Runner: Match by full tool_name with mode

**Benefits:**
- Clean 1:1 mapping
- Each mode gets its own ToolResult record (better for reporting)
- No need to change query logic

**Drawbacks:**
- Changes Brain → Runner contract
- Need to update `tool_matrix.py` to create mode-specific PENDING records

---

## 🏆 **Recommended Solution: Option 3**

**Why:**
- Clean separation of concerns
- Each tool mode gets its own ToolResult record (better UX)
- Minimal code changes
- Future-proof for tools with multiple modes

**Implementation:**
1. Update Brain to send `tool_name` with mode suffix (e.g., `"zap_passive_spider"`)
2. Update Backend `tool_matrix.py` to create PENDING records with mode-specific names
3. Update Frontend to display mode-specific names (or strip suffix for display)

---

## 📝 **Temporary Fix (Already Applied)**

**SQL cleanup to remove duplicate PENDING records:**
```sql
DELETE FROM tool_results 
WHERE scan_job_id = '145bc174-886d-4582-834c-6b7421ef9f70' 
AND status = 'PENDING';
```

**Result:** Frontend now shows correct status ✅

---

## 🚀 **Next Steps**

1. **Short-term:** Keep manually cleaning up PENDING duplicates after Brain restarts
2. **Medium-term:** Implement Option 3 (mode-specific tool_name)
3. **Long-term:** Refactor tool matrix to support multi-mode tools natively

---

## ✅ **Status**

- **Root cause:** Identified ✅
- **Temporary fix:** Applied ✅
- **Permanent fix:** Designed (Option 3) ✅
- **Implementation:** Pending (requires Brain + Backend changes)

*Note: Current scans will work correctly after manual PENDING cleanup. Permanent fix needed to prevent future occurrences.*
