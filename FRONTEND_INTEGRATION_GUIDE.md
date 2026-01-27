# Frontend Integration Guide

## Overview

This guide shows how to integrate the new real-time scan event system into the frontend.

## New Components Created

### 1. **`useScanEvents` Hook** (`frontend/lib/hooks/useScanEvents.ts`)

WebSocket hook for receiving real-time scan events and tool states.

**Usage:**
```typescript
import { useScanEvents } from '@/lib/hooks/useScanEvents';

function MyComponent({ scanId }: { scanId: string }) {
  const { events, toolStates, isConnected, error } = useScanEvents(scanId);
  
  // events: Array of scan events
  // toolStates: Map of current tool states keyed by "${phase}:${tool}"
  // isConnected: WebSocket connection status
  // error: Error message if connection fails
}
```

### 2. **`PhaseTimeline` Component** (`frontend/components/scan/PhaseTimeline.tsx`)

Displays scan progress organized by phases (Prepare, Enumerate, Scan, Correlate & Score, Finalize) with real-time tool status updates.

**Usage:**
```typescript
import { PhaseTimeline } from '@/components/scan/PhaseTimeline';

<PhaseTimeline
  events={events}
  toolStates={toolStates}
  scanLevel="pro"
  isConnected={isConnected}
/>
```

### 3. **`SeverityBadge` Component** (`frontend/components/scan/SeverityBadge.tsx`)

Standardized severity display for vulnerability findings.

**Usage:**
```typescript
import { SeverityBadge, SeverityCounts } from '@/components/scan/SeverityBadge';

// Single badge
<SeverityBadge severity="critical" size="md" showIcon={true} />

// Severity counts summary
<SeverityCounts
  counts={{
    critical: 5,
    high: 12,
    medium: 23,
    low: 45,
    info: 67,
  }}
  size="md"
/>
```

## Integration into Scan Detail Page

### Step 1: Import the Hook and Components

Add these imports to `/frontend/app/projects/[projectId]/scans/[scanId]/page.tsx`:

```typescript
import { useScanEvents } from '@/lib/hooks/useScanEvents';
import { PhaseTimeline } from '@/components/scan/PhaseTimeline';
import { SeverityBadge } from '@/components/scan/SeverityBadge';
```

### Step 2: Add WebSocket Hook to Component

Inside the `ScanReportPage` component (around line 200), add:

```typescript
// Real-time scan events via WebSocket
const { events, toolStates, isConnected: wsConnected } = useScanEvents(
  scan?.status === 'running' || scan?.status === 'queued' ? scanId : null
);
```

### Step 3: Replace Tool Status Section

Find the "Tool Execution Status" section (around line 1843-1893) and replace it with:

```typescript
{scan && (scan.status === 'running' || scan.status === 'queued') && (
  <div className="mt-8">
    <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>
      Live Scan Progress
    </h3>
    <PhaseTimeline
      events={events}
      toolStates={toolStates}
      scanLevel={scan.scan_level}
      isConnected={wsConnected}
    />
  </div>
)}

{/* Keep the old tool status section for completed scans as fallback */}
{scan && scan.status !== 'running' && scan.status !== 'queued' && scan.tool_statuses && scan.tool_statuses.length > 0 && (
  <div className="mt-8">
    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>
      Tool Execution Status
    </h3>
    {/* Original tool status code here */}
  </div>
)}
```

### Step 4: Update Severity Display in Findings

Find where findings are displayed (look for severity rendering) and replace with:

```typescript
{/* Old severity display */}
<span className="...">
  {finding.severity}
</span>

{/* New standardized severity badge */}
<SeverityBadge severity={finding.severity} size="sm" />
```

### Step 5: Add Severity Counts to Summary

In the scan summary section, replace severity counts with:

```typescript
import { SeverityCounts } from '@/components/scan/SeverityBadge';

<SeverityCounts
  counts={{
    critical: severityCounts.critical || 0,
    high: severityCounts.high || 0,
    medium: severityCounts.medium || 0,
    low: severityCounts.low || 0,
    info: severityCounts.info || 0,
  }}
  size="md"
/>
```

## WebSocket Endpoint Configuration

The WebSocket endpoint is automatically configured based on the current page URL:

- **Development**: `ws://localhost:3000/ws/scans/{scanId}`
- **Production**: `wss://your-domain.com/ws/scans/{scanId}`

The hook handles connection, reconnection, and error handling automatically.

## Backend WebSocket Support

The backend WebSocket endpoint is already implemented at:
- **Endpoint**: `GET /ws/scans/{scan_id}`
- **File**: `backend/app/api/websocket.py`
- **Router**: Already registered in `backend/app/main.py`

## Event Data Structures

### ScanEvent
```typescript
{
  id: string;
  scan_id: string;
  timestamp: string;
  phase: 'prepare' | 'enumerate' | 'scan' | 'correlate_score' | 'finalize';
  tool?: string;  // e.g., 'nuclei', 'zap', 'httpx'
  stage: string;  // e.g., 'queued', 'starting', 'running', 'parsing', 'completed'
  message?: string;
  progress?: number;  // 0-100
  meta?: Record<string, any>;
}
```

### ScanToolState
```typescript
{
  tool: string;
  phase: string;
  stage: string;
  progress?: number;
  last_message?: string;
  meta?: Record<string, any>;
  updated_at: string;
}
```

## Severity Levels

The `SeverityBadge` component normalizes the following severity strings:

- **Critical**: `'critical'`, `'crit'`
- **High**: `'high'`, `'h'`
- **Medium**: `'medium'`, `'med'`, `'moderate'`, `'m'`
- **Low**: `'low'`, `'l'`
- **Info**: `'info'`, `'informational'`, `'i'`
- **Unknown**: Any unrecognized value

## Testing

1. **Start a scan** (Pro or Advanced level for best results)
2. **Open the scan detail page** while the scan is running
3. **Verify**:
   - WebSocket connection indicator shows "connected"
   - Phase timeline displays with active phases
   - Tool cards show real-time status updates
   - Progress bars update smoothly
   - Recent events log shows latest activities
   - Severity badges display with correct colors

## Troubleshooting

### WebSocket Not Connecting

1. Check browser console for WebSocket errors
2. Verify backend WebSocket endpoint is accessible
3. Check that the scan ID is valid
4. Ensure no reverse proxy is blocking WebSocket connections

### Events Not Updating

1. Verify the scan is actually running
2. Check that the runner is emitting events (check runner logs)
3. Verify backend is receiving and broadcasting events
4. Check browser console for parsing errors

### Severity Badges Not Showing

1. Verify the `severity` field exists in the finding object
2. Check that the severity value is being passed correctly
3. Ensure the component is imported from the correct path

## Next Steps

1. **Test with live scans** to verify real-time updates
2. **Customize styling** to match your design system
3. **Add animations** for phase transitions
4. **Implement filters** for tool-specific views
5. **Add export functionality** for event logs

## Component Props Reference

### useScanEvents

```typescript
function useScanEvents(scanId: string | null): {
  events: ScanEvent[];
  toolStates: Map<string, ScanToolState>;
  isConnected: boolean;
  error: string | null;
}
```

### PhaseTimeline

```typescript
interface PhaseTimelineProps {
  events: ScanEvent[];
  toolStates: Map<string, ScanToolState>;
  scanLevel?: string;
  isConnected: boolean;
}
```

### SeverityBadge

```typescript
interface SeverityBadgeProps {
  severity: string | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}
```

### SeverityCounts

```typescript
interface SeverityCountsProps {
  counts: {
    critical?: number;
    high?: number;
    medium?: number;
    low?: number;
    info?: number;
  };
  size?: 'sm' | 'md' | 'lg';
}
```

