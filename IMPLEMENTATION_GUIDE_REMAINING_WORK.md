# Implementation Guide: Remaining Work

This guide provides step-by-step instructions to complete the enumeration and real-time events implementation.

## Quick Start: What's Done vs. What's Left

### ✅ COMPLETED (60%)
- Backend database models and API endpoints
- WebSocket infrastructure
- Database migration
- Runner Dockerfile with new tools (katana, gau, arjun)
- Enumeration module (complete implementation)
- Event emission helpers (batching logic)

### 🚧 REMAINING (40%)
- Tool wrapper event emission (2-3 hours)
- Orchestration integration (1 hour)
- Feed inventory into scanners (2 hours)
- Frontend components (4-6 hours)
- Testing (2 hours)

---

## STEP 1: Fix ZAP OK Bug (5 minutes)

**Priority:** CRITICAL - User-facing bug

**File:** Find ZAP result parsing logic

```bash
cd services/thandev-runner
grep -r "Result.*OK" app/
```

**Fix:**
```python
# In ZAP parser (likely app/findings/parsers.py or app/services/tools.py)

# OLD (BROKEN):
if "error" in result_str or "Error" in result_str:
    stage = "failed"

# NEW (FIXED):
if isinstance(result, dict) and result.get("Result") == "OK":
    # ZAP returns {"Result":"OK"} on success
    stage = "completed"
    message = "ZAP scan completed successfully"
elif "error" in str(result).lower():
    stage = "failed"
    message = f"ZAP scan failed: {result}"
```

---

## STEP 2: Add Event Emission to Tool Wrappers (2-3 hours)

### 2.1 Import Event Emission Helper

**File:** `services/thandev-runner/app/tasks.py`

```python
# Add at top of file
from app.backend_client import emit_scan_event
```

### 2.2 Add Events to Each Tool

**Pattern for each tool:**

```python
async def run_tool_wrapper(scan_id, tool_name, target_url, ...):
    # 1. Queued
    await emit_scan_event(scan_id, "scan", tool_name, "queued", "Queued for execution")
    
    # 2. Starting
    await emit_scan_event(scan_id, "scan", tool_name, "starting", f"Starting {tool_name}...")
    
    # 3. Running (with progress if possible)
    await emit_scan_event(
        scan_id, "scan", tool_name, "running",
        f"Scanning {target_count} targets...",
        progress=0.5,
        meta={"targets": target_count}
    )
    
    # 4. Parsing
    await emit_scan_event(scan_id, "scan", tool_name, "parsing", "Parsing results...")
    
    # 5. Uploading
    await emit_scan_event(scan_id, "scan", tool_name, "uploading", "Uploading findings...")
    
    # 6. Completed or Failed
    if success:
        await emit_scan_event(
            scan_id, "scan", tool_name, "completed",
            f"Found {findings_count} findings",
            progress=1.0,
            meta={"findings": findings_count}
        )
    else:
        await emit_scan_event(
            scan_id, "scan", tool_name, "failed",
            f"Failed: {error_message}",
            meta={"error": error_message}
        )
```

### 2.3 Tools to Update

**Locate tool wrappers:**
```bash
cd services/thandev-runner
grep -r "def.*nuclei" app/
grep -r "def.*zap" app/
grep -r "def.*dalfox" app/
grep -r "def.*sqlmap" app/
```

**Add events to:**
1. `httpx` wrapper (prepare phase)
2. `nuclei` wrapper (scan phase)
3. `zap` wrapper (scan phase) - with stage breakdown
4. `dalfox` wrapper (scan phase)
5. `sqlmap` wrapper (scan phase)
6. `nmap` wrapper (scan phase)
7. `sslscan` wrapper (scan phase)

### 2.4 ZAP Special Handling

```python
# ZAP has multiple stages
await emit_scan_event(scan_id, "scan", "zap", "starting", "Starting ZAP daemon...")
await emit_scan_event(scan_id, "scan", "zap", "daemon_start", "ZAP daemon started")
await emit_scan_event(scan_id, "scan", "zap", "ajax_spider_running", "Running AJAX Spider...")
await emit_scan_event(scan_id, "scan", "zap", "active_scan_running", "Running active scan...")
await emit_scan_event(scan_id, "scan", "zap", "collecting_alerts", "Collecting alerts...")
await emit_scan_event(scan_id, "scan", "zap", "uploading_results", "Uploading results...")
await emit_scan_event(scan_id, "scan", "zap", "completed", f"Found {alerts_count} alerts", progress=1.0)
```

---

## STEP 3: Integrate Enumeration into Orchestration (1 hour)

**File:** `services/thandev-runner/app/tasks.py` (or orchestrator file)

**Find:** The main task processing function (likely `process_step_request`)

**Add:**

```python
async def process_step_request(message: Dict[str, Any]) -> None:
    # ... existing code to extract scan_id, tool_id, target_ref, scan_level ...
    
    # NEW: Check if enumeration should run
    # Run enumeration before first tool if Pro/Advanced
    should_enumerate = (
        scan_level in ["pro", "advanced"] and
        tool_id == "httpx"  # First tool
    )
    
    if should_enumerate:
        logger.info(f"[ENUMERATION] Starting for scan {scan_id}")
        
        from app.enumeration import run_enumeration
        from app.backend_client import post_scan_inventory
        
        # Create event emission callback
        async def emit_event(phase, tool, stage, message, progress=None, meta=None):
            await emit_scan_event(scan_id, phase, tool, stage, message, progress, meta)
        
        try:
            # Run enumeration
            inventory = await run_enumeration(
                target_url=target_ref,
                scan_level=scan_level,
                emit_event_callback=emit_event
            )
            
            # Upload inventory to backend
            await post_scan_inventory(scan_id, inventory)
            
            # Store inventory in Redis for tool access
            await store_inventory_in_redis(scan_id, inventory)
            
            logger.info(f"[ENUMERATION] Completed for scan {scan_id}")
        except Exception as e:
            logger.error(f"[ENUMERATION] Failed for scan {scan_id}: {e}", exc_info=True)
            # Don't fail the scan, continue with tools
    
    # ... continue with existing tool execution ...
```

**Add Redis helper:**

```python
async def store_inventory_in_redis(scan_id: str, inventory: Dict[str, Any]):
    """Store inventory in Redis with 24h expiry"""
    from app.queue.streams import get_redis_client
    
    redis = get_redis_client()
    key = f"scan_inventory:{scan_id}"
    redis.setex(key, 86400, json.dumps(inventory))  # 24 hours

async def get_inventory_from_redis(scan_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve inventory from Redis"""
    from app.queue.streams import get_redis_client
    
    redis = get_redis_client()
    key = f"scan_inventory:{scan_id}"
    data = redis.get(key)
    
    if data:
        return json.loads(data)
    return None
```

---

## STEP 4: Feed Inventory into Scanners (2 hours)

### 4.1 Nuclei

**File:** Find nuclei wrapper

```python
async def run_nuclei(scan_id, target_url, ...):
    # Get inventory
    inventory = await get_inventory_from_redis(scan_id)
    
    if inventory and inventory.get("discovery", {}).get("merged", {}).get("all_urls"):
        # Use discovered URLs
        urls = inventory["discovery"]["merged"]["all_urls"][:500]  # Cap at 500
        
        # Create targets file
        targets_file = f"/tmp/nuclei_targets_{scan_id}.txt"
        with open(targets_file, "w") as f:
            for url in urls:
                f.write(f"{url}\n")
        
        # Run nuclei with -l flag
        cmd = ["nuclei", "-l", targets_file, "-json", ...]
    else:
        # Fallback to single target
        cmd = ["nuclei", "-u", target_url, "-json", ...]
    
    # ... rest of nuclei execution ...
```

### 4.2 Dalfox

**File:** Find dalfox wrapper

```python
async def run_dalfox(scan_id, target_url, ...):
    # Get inventory
    inventory = await get_inventory_from_redis(scan_id)
    
    if inventory:
        param_urls = inventory.get("discovery", {}).get("merged", {}).get("param_urls", [])
        
        if param_urls:
            # Run dalfox against parameterized URLs
            all_findings = []
            for url in param_urls[:100]:  # Cap at 100
                findings = await run_dalfox_on_url(url)
                all_findings.extend(findings)
            
            return all_findings
    
    # Fallback to single target
    return await run_dalfox_on_url(target_url)
```

### 4.3 SQLMap (Advanced only)

**File:** Find sqlmap wrapper

```python
async def run_sqlmap(scan_id, target_url, scan_level, ...):
    if scan_level != "advanced":
        return []
    
    # Get inventory
    inventory = await get_inventory_from_redis(scan_id)
    
    if inventory:
        # Curate high-value targets
        param_urls = inventory.get("discovery", {}).get("merged", {}).get("param_urls", [])
        api_urls = inventory.get("discovery", {}).get("merged", {}).get("interesting", {}).get("api", [])
        
        # Prioritize likely DB endpoints
        targets = []
        for url in param_urls + api_urls:
            url_lower = url.lower()
            if any(pattern in url_lower for pattern in ["api", "search", "product", "id=", "user"]):
                targets.append(url)
        
        # Limit to 10-20 targets
        targets = targets[:20]
        
        if targets:
            all_findings = []
            for url in targets:
                findings = await run_sqlmap_on_url(url)
                all_findings.extend(findings)
            
            return all_findings
    
    # Fallback to single target
    return await run_sqlmap_on_url(target_url)
```

### 4.4 ZAP Seeding

**File:** Find ZAP wrapper

```python
async def run_zap(scan_id, target_url, ...):
    # Start ZAP daemon
    zap = start_zap_daemon()
    
    # Get inventory
    inventory = await get_inventory_from_redis(scan_id)
    
    if inventory:
        urls = inventory.get("discovery", {}).get("merged", {}).get("all_urls", [])
        
        # Seed ZAP with discovered URLs
        logger.info(f"[ZAP] Seeding with {len(urls[:200])} URLs")
        for url in urls[:200]:  # Cap at 200
            try:
                zap.urlopen(url)
            except:
                pass
    
    # Continue with spider and scan
    # ... rest of ZAP execution ...
```

---

## STEP 5: Build Frontend Components (4-6 hours)

### 5.1 WebSocket Hook

**File:** `frontend/lib/useWebSocket.ts` (NEW)

```typescript
import { useState, useEffect } from 'react';

export interface ToolState {
  tool: string;
  phase: string;
  stage: string;
  message: string;
  progress?: number;
  meta?: Record<string, any>;
}

export interface ScanEvent {
  phase: string;
  tool?: string;
  stage: string;
  message: string;
  progress?: number;
  meta?: Record<string, any>;
  created_at: string;
}

export function useScanWebSocket(scanId: string) {
  const [toolStates, setToolStates] = useState<ToolState[]>([]);
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [connected, setConnected] = useState(false);
  
  useEffect(() => {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const wsUrl = backendUrl.replace('http', 'ws') + `/ws/scans/${scanId}`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('[WS] Connected to scan', scanId);
      setConnected(true);
    };
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'initial_state') {
        setToolStates(message.data.tool_states || []);
      } else if (message.type === 'event') {
        setEvents(prev => [message.data, ...prev].slice(0, 100));
      } else if (message.type === 'tool_state') {
        setToolStates(prev => {
          const existing = prev.find(
            ts => ts.tool === message.data.tool && ts.phase === message.data.phase
          );
          if (existing) {
            return prev.map(ts =>
              ts.tool === message.data.tool && ts.phase === message.data.phase
                ? message.data
                : ts
            );
          } else {
            return [...prev, message.data];
          }
        });
      } else if (message.type === 'ping') {
        ws.send('pong');
      }
    };
    
    ws.onclose = () => {
      console.log('[WS] Disconnected from scan', scanId);
      setConnected(false);
    };
    
    ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
    
    // Keepalive ping every 20 seconds
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 20000);
    
    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [scanId]);
  
  return { toolStates, events, connected };
}
```

### 5.2 Severity Badge Component

**File:** `frontend/components/Scans/SeverityBadge.tsx` (NEW)

```typescript
interface SeverityBadgeProps {
  severity: string;
  size?: 'sm' | 'md' | 'lg';
}

export function SeverityBadge({ severity, size = 'md' }: SeverityBadgeProps) {
  const severityLower = severity.toLowerCase();
  
  const colors = {
    critical: 'bg-red-100 text-red-800 border-red-300',
    high: 'bg-orange-100 text-orange-800 border-orange-300',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    low: 'bg-blue-100 text-blue-800 border-blue-300',
    info: 'bg-gray-100 text-gray-800 border-gray-300',
  };
  
  const sizes = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-2.5 py-1',
    lg: 'text-base px-3 py-1.5',
  };
  
  const colorClass = colors[severityLower as keyof typeof colors] || colors.info;
  const sizeClass = sizes[size];
  
  return (
    <span className={`inline-flex items-center rounded-md border font-medium ${colorClass} ${sizeClass}`}>
      {severity.toUpperCase()}
    </span>
  );
}
```

### 5.3 Phase Timeline Component

**File:** `frontend/components/Scans/PhaseTimeline.tsx` (NEW)

```typescript
interface Phase {
  id: string;
  name: string;
  status: 'pending' | 'active' | 'completed';
}

export function PhaseTimeline({ toolStates }: { toolStates: ToolState[] }) {
  const phases: Phase[] = [
    { id: 'prepare', name: 'Prepare', status: 'pending' },
    { id: 'enumerate', name: 'Enumerate', status: 'pending' },
    { id: 'scan', name: 'Scan', status: 'pending' },
    { id: 'correlate', name: 'Correlate', status: 'pending' },
    { id: 'finalize', name: 'Finalize', status: 'pending' },
  ];
  
  // Determine phase status from tool states
  const phaseStatus = phases.map(phase => {
    const phaseTools = toolStates.filter(ts => ts.phase === phase.id);
    
    if (phaseTools.length === 0) return 'pending';
    
    const allCompleted = phaseTools.every(ts => 
      ['completed', 'failed', 'skipped'].includes(ts.stage)
    );
    
    if (allCompleted) return 'completed';
    
    const anyRunning = phaseTools.some(ts => 
      ['starting', 'running', 'parsing', 'uploading'].includes(ts.stage)
    );
    
    if (anyRunning) return 'active';
    
    return 'pending';
  });
  
  return (
    <div className="flex items-center justify-between">
      {phases.map((phase, idx) => (
        <div key={phase.id} className="flex items-center">
          <div className="flex flex-col items-center">
            <div className={`
              w-10 h-10 rounded-full flex items-center justify-center border-2
              ${phaseStatus[idx] === 'completed' ? 'bg-green-500 border-green-500 text-white' : ''}
              ${phaseStatus[idx] === 'active' ? 'bg-blue-500 border-blue-500 text-white' : ''}
              ${phaseStatus[idx] === 'pending' ? 'bg-gray-200 border-gray-300 text-gray-500' : ''}
            `}>
              {phaseStatus[idx] === 'completed' ? '✓' : idx + 1}
            </div>
            <span className="text-sm mt-2">{phase.name}</span>
          </div>
          
          {idx < phases.length - 1 && (
            <div className={`
              w-24 h-0.5 mx-2
              ${phaseStatus[idx] === 'completed' ? 'bg-green-500' : 'bg-gray-300'}
            `} />
          )}
        </div>
      ))}
    </div>
  );
}
```

### 5.4 Tool Card Component

**File:** `frontend/components/Scans/ToolCard.tsx` (NEW)

```typescript
export function ToolCard({ toolState }: { toolState: ToolState }) {
  const stageColors = {
    queued: 'bg-gray-100 text-gray-800',
    starting: 'bg-blue-100 text-blue-800',
    running: 'bg-blue-500 text-white',
    parsing: 'bg-purple-100 text-purple-800',
    uploading: 'bg-indigo-100 text-indigo-800',
    completed: 'bg-green-500 text-white',
    failed: 'bg-red-500 text-white',
    skipped: 'bg-gray-300 text-gray-700',
  };
  
  const stageColor = stageColors[toolState.stage as keyof typeof stageColors] || stageColors.queued;
  
  return (
    <div className="border rounded-lg p-4 bg-white shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-lg">{toolState.tool.toUpperCase()}</h3>
        <span className={`px-2 py-1 rounded text-xs font-medium ${stageColor}`}>
          {toolState.stage}
        </span>
      </div>
      
      <p className="text-sm text-gray-700 mb-2">{toolState.message}</p>
      
      {toolState.progress !== undefined && (
        <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
          <div
            className="bg-blue-500 h-2 rounded-full transition-all"
            style={{ width: `${toolState.progress * 100}%` }}
          />
        </div>
      )}
      
      {toolState.meta && Object.keys(toolState.meta).length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {Object.entries(toolState.meta).map(([key, value]) => (
            <span key={key} className="text-xs bg-gray-100 px-2 py-1 rounded">
              {key}: {value}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
```

### 5.5 Update Scan Detail Page

**File:** `frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`

```typescript
// Add imports
import { useScanWebSocket } from '@/lib/useWebSocket';
import { PhaseTimeline } from '@/components/Scans/PhaseTimeline';
import { ToolCard } from '@/components/Scans/ToolCard';
import { SeverityBadge } from '@/components/Scans/SeverityBadge';

// In component
export default function ScanDetailPage() {
  const params = useParams();
  const scanId = params.scanId as string;
  
  // Add WebSocket hook
  const { toolStates, events, connected } = useScanWebSocket(scanId);
  
  // ... existing code ...
  
  return (
    <div>
      {/* Connection indicator */}
      {connected && (
        <div className="text-sm text-green-600 mb-4">
          ● Live updates connected
        </div>
      )}
      
      {/* Phase Timeline */}
      <PhaseTimeline toolStates={toolStates} />
      
      {/* Tool Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mt-6">
        {toolStates.map((ts, idx) => (
          <ToolCard key={`${ts.tool}-${ts.phase}-${idx}`} toolState={ts} />
        ))}
      </div>
      
      {/* Findings with Severity Badges */}
      {findings.map(finding => (
        <div key={finding.id}>
          <SeverityBadge severity={finding.severity} />
          {/* ... rest of finding display ... */}
        </div>
      ))}
    </div>
  );
}
```

---

## STEP 6: Test End-to-End (2 hours)

### 6.1 Run Migration

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

### 6.2 Start Services

```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2: Runner
cd services/thandev-runner
docker-compose up --build

# Terminal 3: Frontend
cd frontend
npm run dev
```

### 6.3 Test Basic Scan (No Breaking Changes)

```bash
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: test-user" \
  -H "X-Thandev-Tenant-Id: test-tenant" \
  -d '{
    "project_id": "test-project",
    "target_url": "https://example.com",
    "scan_level": "basic"
  }'
```

**Expected:** Scan runs as before, no errors

### 6.4 Test Pro Scan (With Enumeration)

```bash
curl -X POST http://localhost:8000/api/scans \
  -H "Content-Type: application/json" \
  -H "X-Thandev-User-Id: test-user" \
  -H "X-Thandev-Tenant-Id: test-tenant" \
  -d '{
    "project_id": "test-project",
    "target_url": "https://demo.owasp-juice.shop",
    "scan_level": "pro"
  }'
```

**Expected:**
- Enumeration phase runs (katana, gau, arjun)
- Events visible in WebSocket
- Inventory stored
- Nuclei/Dalfox use discovered URLs

### 6.5 Test WebSocket

```bash
# In browser console
const ws = new WebSocket('ws://localhost:8000/ws/scans/SCAN_ID');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

**Expected:** Real-time events streaming

### 6.6 Test ZAP (No OK Bug)

**Expected:** ZAP shows correct stages, no "Failed: OK" message

---

## DEPLOYMENT CHECKLIST

- [ ] Run migration: `alembic upgrade head`
- [ ] Rebuild runner Docker image
- [ ] Verify tools installed: `katana -h`, `gau -h`, `arjun -h`
- [ ] Test Basic scan (no regression)
- [ ] Test Pro scan (enumeration works)
- [ ] Test Advanced scan (sqlmap limited)
- [ ] Test WebSocket connection
- [ ] Test ZAP (no OK bug)
- [ ] Test severity badges (consistent)
- [ ] Update user documentation

---

## TROUBLESHOOTING

### Events not appearing
- Check runner logs for event emission
- Check backend logs for event ingestion
- Verify RUNNER_API_TOKEN is set
- Check WebSocket connection in browser console

### Enumeration not running
- Check scan level is Pro/Advanced
- Check orchestration integration
- Check runner logs for enumeration errors

### Tools not using inventory
- Check inventory stored in Redis
- Check tool wrappers fetch inventory
- Check Redis connection

### WebSocket not connecting
- Check CORS settings
- Check WebSocket URL (ws:// not http://)
- Check firewall/proxy settings

---

**Estimated Total Time:** 12-15 hours
**Priority:** ZAP bug (5 min) → Tool events (2-3 hrs) → Orchestration (1 hr) → Inventory feeding (2 hrs) → Frontend (4-6 hrs) → Testing (2 hrs)

