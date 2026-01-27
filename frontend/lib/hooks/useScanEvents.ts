/**
 * WebSocket hook for real-time scan events
 */
import { useEffect, useState, useRef } from 'react';

export interface ScanEvent {
  id: string;
  scan_id: string;
  timestamp: string;
  created_at?: string;
  phase: 'prepare' | 'enumerate' | 'scan' | 'correlate_score' | 'finalize';
  tool?: string;
  stage: string;
  message?: string;
  progress?: number;
  meta?: Record<string, any>;
}

export interface ScanToolState {
  tool: string;
  phase: string;
  stage: string;
  progress?: number;
  last_message?: string;
  meta?: Record<string, any>;
  updated_at: string;
}

interface UseScanEventsReturn {
  events: ScanEvent[];
  toolStates: Map<string, ScanToolState>;
  isConnected: boolean;
  error: string | null;
}

export function useScanEvents(scanId: string | null): UseScanEventsReturn {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [toolStates, setToolStates] = useState<Map<string, ScanToolState>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  useEffect(() => {
    if (!scanId) {
      return;
    }

    const connect = () => {
      try {
        // Determine WebSocket URL based on environment
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/ws/scans/${scanId}`;

        console.log(`[WebSocket] Connecting to ${wsUrl}`);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log(`[WebSocket] Connected to scan ${scanId}`);
          setIsConnected(true);
          setError(null);
          reconnectAttemptsRef.current = 0;
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('[WebSocket] Received:', data);

            if (data.type === 'initial_events' && Array.isArray(data.events)) {
              // Initial batch of events
              setEvents(data.events);
            } else if (data.type === 'initial_tool_states' && Array.isArray(data.tool_states)) {
              // Initial tool states
              const statesMap = new Map<string, ScanToolState>();
              data.tool_states.forEach((state: ScanToolState) => {
                const key = `${state.phase}:${state.tool}`;
                statesMap.set(key, state);
              });
              setToolStates(statesMap);
            } else if (data.type === 'event') {
              // Single new event
              setEvents((prev) => [...prev, data.event]);
            } else if (data.type === 'tool_state_update') {
              // Tool state update
              setToolStates((prev) => {
                const newMap = new Map(prev);
                const key = `${data.state.phase}:${data.state.tool}`;
                newMap.set(key, data.state);
                return newMap;
              });
            }
          } catch (err) {
            console.error('[WebSocket] Failed to parse message:', err);
          }
        };

        ws.onerror = (err) => {
          console.error('[WebSocket] Error:', err);
          setError('WebSocket connection error');
        };

        ws.onclose = () => {
          console.log('[WebSocket] Connection closed');
          setIsConnected(false);
          wsRef.current = null;

          // Attempt to reconnect with exponential backoff
          if (reconnectAttemptsRef.current < 5) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
            console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`);
            
            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current += 1;
              connect();
            }, delay);
          } else {
            setError('Failed to connect after multiple attempts');
          }
        };
      } catch (err) {
        console.error('[WebSocket] Failed to create connection:', err);
        setError('Failed to create WebSocket connection');
      }
    };

    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [scanId]);

  return {
    events,
    toolStates,
    isConnected,
    error,
  };
}

