/**
 * useScanEvents Hook
 * 
 * WebSocket hook for real-time scan event updates.
 * Connects to the backend WebSocket to receive live scan progress events.
 */

import { useEffect, useState, useRef, useCallback } from 'react';

export interface ScanEvent {
  id: string;
  scan_id: string;
  timestamp: string;
  phase: string;
  tool?: string | null;
  stage: string;
  message?: string | null;
  progress?: number | null;
  meta?: Record<string, any> | null;
}

export interface ScanToolState {
  tool: string;
  phase: string;
  stage: string;
  progress?: number | null;
  last_message?: string | null;
  meta?: Record<string, any> | null;
  updated_at: string;
}

interface UseScanEventsReturn {
  events: ScanEvent[];
  toolStates: ScanToolState[];
  isConnected: boolean;
  error: string | null;
}

export function useScanEvents(scanId: string | null): UseScanEventsReturn {
  const [events, setEvents] = useState<ScanEvent[]>([]);
  const [toolStates, setToolStates] = useState<ScanToolState[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds

  const connect = useCallback(() => {
    console.log(`[useScanEvents] connect() called, scanId=${scanId}`);
    
    if (!scanId) {
      console.log('[useScanEvents] No scanId, skipping connection');
      return;
    }
    
    // Don't reconnect if we've exceeded max attempts
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      console.log('[useScanEvents] Max reconnect attempts reached');
      setError('Failed to connect after multiple attempts');
      return;
    }

    try {
      // Construct WebSocket URL - connect to backend, not Next.js dev server
      const backendUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const wsProtocol = backendUrl.startsWith('https') ? 'wss:' : 'ws:';
      const wsHost = backendUrl.replace(/^https?:\/\//, '');
      const wsUrl = `${wsProtocol}//${wsHost}/ws/scans/${scanId}`;
      
      console.log(`[useScanEvents] Backend URL: ${backendUrl}`);
      console.log(`[useScanEvents] WebSocket URL: ${wsUrl}`);
      console.log(`[useScanEvents] Attempting connection...`);
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[useScanEvents] WebSocket connected');
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0; // Reset reconnect attempts on successful connection
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[useScanEvents] Received message:', data.type, data);
          
          if (data.type === 'initial_events') {
            // Initial events from backend
            console.log('[useScanEvents] Setting initial events:', data.events?.length || 0);
            setEvents(data.events || []);
          } else if (data.type === 'initial_tool_states') {
            // Initial tool states from backend
            console.log('[useScanEvents] Setting initial tool states:', data.tool_states);
            setToolStates(data.tool_states || []);
          } else if (data.type === 'event') {
            // Single event update
            setEvents(prev => [...prev, data.event]);
          } else if (data.type === 'tool_state') {
            // Single tool state update
            setToolStates(prev => {
              const existing = prev.find(
                s => s.tool === data.tool_state.tool && s.phase === data.tool_state.phase
              );
              if (existing) {
                return prev.map(s =>
                  s.tool === data.tool_state.tool && s.phase === data.tool_state.phase
                    ? data.tool_state
                    : s
                );
              } else {
                return [...prev, data.tool_state];
              }
            });
          }
        } catch (err) {
          console.error('[useScanEvents] Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (err) => {
        console.error('[useScanEvents] WebSocket error:', err);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log('[useScanEvents] WebSocket closed');
        setIsConnected(false);
        wsRef.current = null;

        // Attempt to reconnect after delay
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          console.log(
            `[useScanEvents] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})...`
          );
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectDelay);
        } else {
          setError('Connection lost. Please refresh the page.');
        }
      };
    } catch (err) {
      console.error('[useScanEvents] Failed to create WebSocket:', err);
      setError('Failed to establish WebSocket connection');
    }
  }, [scanId]);

  useEffect(() => {
    // Small delay to avoid React Strict Mode double-mount issues
    const connectTimeout = setTimeout(() => {
      connect();
    }, 100);

    // Cleanup on unmount
    return () => {
      clearTimeout(connectTimeout);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return {
    events,
    toolStates,
    isConnected,
    error,
  };
}

