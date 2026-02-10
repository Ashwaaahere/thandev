'use client';

/**
 * Scan Report Page
 * 
 * Displays detailed scan report with executive summary, findings, metadata, and stack info.
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { thandevFetchJSON, thandevFetchPDF } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';
import { formatCategory } from '@/lib/vulnCategories';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import TechDependenciesPanel from '@/components/Scans/TechDependenciesPanel';
import RepoDependenciesPanel from '@/components/Scans/RepoDependenciesPanel';
import CWEDrawer from '@/components/Dashboard/CWEDrawer';
import AISummaryPanel from '@/components/Scans/AISummaryPanel';
import PhaseTimeline from '@/components/Scans/PhaseTimeline';
import SeverityBadge from '@/components/Scans/SeverityBadge';
import { useScanEvents } from '@/hooks/useScanEvents';

// Types
type FindingStatus = "open" | "acknowledged" | "resolved" | "suppressed";

type FindingInstance = {
  url?: string | null;
  path?: string | null;
  http_method?: string | null;
  parameter?: string | null;
  evidence_snippet?: string | null;
  is_static_asset?: boolean | null;
};

type Finding = {
  id?: string;
  title: string;
  description?: string | null;
  severity?: string | null;
  status?: FindingStatus;
  cve_id?: string | null;
  cwe_id?: string | null;
  cvss_score?: number | null;
  url?: string | null;
  path?: string | null;
  line_number?: number | null;
  recommendation?: string | null;
  tool_name?: string | null;
  categories?: string[] | null;
  // Lifecycle fields
  vuln_type?: string | null;
  http_method?: string | null;
  parameter?: string | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  found_count?: number | null;
  not_seen_in_latest_scan?: boolean | null;
  // Remediation fields
  remediation_summary?: string | null;
  remediation_steps?: string | null;
  default_remediation_steps?: string | null;
  // Impact field
  impact_summary?: string | null;
  // Grouping fields (for deduplicated findings)
  affected_count?: number | null;
  instances_sample?: FindingInstance[] | null;
  mostly_static?: boolean | null;
  rule_family?: string | null;
};

type TopRisk = {
  title?: string;
  severity?: string;
  cve_id?: string | null;
  cvss_score?: number | null;
  url?: string | null;
};

type ScanSummary = {
  executive_summary?: string;
  top_risks?: (string | TopRisk)[] | null;
  remediation_overview?: string;
  risk_score?: number | null;
  findings_count?: number | null;
  [key: string]: any;
};

type StackInfo = {
  target_url?: string;
  scan_level?: string;
  http?: {
    status_code?: number;
    headers?: {
      server?: string | null;
      content_type?: string | null;
      x_powered_by?: string | null;
      [key: string]: any;
    } | null;
  } | null;
  [key: string]: any;
};

type AIPlan = {
  next_tools?: { key: string; reason?: string; priority?: string }[];
  attack_paths?: {
    goal: string;
    steps?: string[];
  }[];
};

type ToolStatus = {
  tool_name: string;
  status: "pending" | "running" | "completed" | "failed" | "timed_out" | "skipped";
  started_at?: string | null;
  completed_at?: string | null;
  execution_time?: number | null;
  error_message?: string | null;
};

type ScanDetail = {
  id: string;
  project_id: string;
  scan_level: string;
  status: string;
  summary?: ScanSummary | null;
  stack_info?: StackInfo | null;
  ai_status?: "idle" | "planned" | "failed" | null;
  ai_plan?: AIPlan | null;
  error_message?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  findings: Finding[];
  tool_statuses?: ToolStatus[];
  progress_pct?: number | null;
  total_tools?: number | null;
  completed_tools?: number | null;
};

type ToolExecution = {
  tool_name: string;
  tool_name_display?: string | null;  // Display name for the tool (optional)
  exit_code: number | null;
  started_at: string;
  completed_at: string | null;
  output_size: number;
  execution_time: number | null;
  error_message: string | null;
  timed_out: boolean;
  // New tool run tracking fields
  status?: string | null;  // ToolExecutionStatus enum value
  stdout_preview?: string | null;  // First 1000 chars of stdout
  stderr_preview?: string | null;  // First 1000 chars of stderr
  parsed_findings_count?: number;  // Number of findings parsed from output
  created_findings_count?: number;  // Number of findings actually created in DB
  duration_ms?: number | null;  // Duration in milliseconds
  skip_reason?: string | null;
  raw_stdout?: string | null;
  raw_stderr?: string | null;
};

type ToolsResponse = {
  items: ToolExecution[];
};

export default function ScanReportPage() {
  const params = useParams();
  const router = useRouter();
  const { data: session, status: sessionStatus } = useSession();
  const projectId = params.projectId as string;
  const scanId = params.scanId as string;

  // Check if scanId is actually a CVE ID (starts with "CVE-")
  // If so, redirect to the CVE detail page
  useEffect(() => {
    if (scanId && scanId.toUpperCase().startsWith('CVE-')) {
      router.replace(`/dashboard/cve/${encodeURIComponent(scanId)}`);
      return;
    }
  }, [scanId, router]);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [project, setProject] = useState<{ id: string; name: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [initialLoadFailed, setInitialLoadFailed] = useState(false);
  const [downloadingFull, setDownloadingFull] = useState(false);
  const [downloadingExecutive, setDownloadingExecutive] = useState(false);
  const [tools, setTools] = useState<ToolExecution[]>([]);
  const [toolsLoading, setToolsLoading] = useState(false);
  const [toolsError, setToolsError] = useState<string | null>(null);
  const [cveIds, setCveIds] = useState<string[]>([]);
  const [cancelling, setCancelling] = useState(false);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingsLoading, setFindingsLoading] = useState(false);
  const [expandedFindingInstances, setExpandedFindingInstances] = useState<Record<string, FindingInstance[]>>({});
  const [loadingInstances, setLoadingInstances] = useState<Record<string, boolean>>({});
  const loadingRef = useRef<Record<string, boolean>>({}); // Track loading state to prevent duplicate calls
  const [expandedDetails, setExpandedDetails] = useState<string[]>([]);
  const [showAllUrls, setShowAllUrls] = useState<Record<string, boolean>>({});
  const [urlSearchTerm, setUrlSearchTerm] = useState<Record<string, string>>({});
  const [findingsError, setFindingsError] = useState<string | null>(null);
  const [findingsTotal, setFindingsTotal] = useState(0);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [selectedToolFilter, setSelectedToolFilter] = useState<string>('all');  // Filter findings by tool
  const [showInfoFindings, setShowInfoFindings] = useState(true);  // Toggle for INFO findings - default to true to show HTTPX findings
  const [expandedToolRows, setExpandedToolRows] = useState<Set<string>>(new Set());  // Track expanded tool rows
  const [availableTools, setAvailableTools] = useState<string[]>([]);  // All tools that have findings
  const [findingsPage, setFindingsPage] = useState(0);  // Current page (0-indexed)
  const [findingsLimit] = useState(100);  // Findings per page (can be 100-200)
  const [allFindings, setAllFindings] = useState<Finding[]>([]);  // All findings for executive summary
  const [activeTab, setActiveTab] = useState<'overview' | 'findings' | 'enumeration' | 'tech-deps' | 'repo-deps' | 'ai-summary'>('overview');
  const [artifacts, setArtifacts] = useState<any>(null);
  const [artifactsLoading, setArtifactsLoading] = useState(false);
  const [techStack, setTechStack] = useState<any>(null);  // Tech stack from /tech-stack endpoint
  const [techStackLoading, setTechStackLoading] = useState(true);
  const [inventory, setInventory] = useState<any>(null);  // Enumeration inventory
  const [inventoryLoading, setInventoryLoading] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now()); // For real-time timer updates
  const [cweDrawerOpen, setCweDrawerOpen] = useState(false);
  const [selectedCweId, setSelectedCweId] = useState<string | null>(null);
  const [downloadingCSV, setDownloadingCSV] = useState(false);

  // Connect to real-time scan events via WebSocket
  const { toolStates: wsToolStates, isConnected } = useScanEvents(scanId);
  
  // Convert HTTP tools data to tool states format as fallback
  const toolStates = useMemo(() => {
    // If WebSocket provided tool states, use them
    if (wsToolStates && wsToolStates.length > 0) {
      return wsToolStates;
    }
    
    // Otherwise, convert tools data from HTTP API
    if (tools && tools.length > 0) {
      return tools.map(tool => ({
        tool: tool.tool_name?.toLowerCase() || 'unknown',
        phase: 'scan', // Tools from HTTP API are always in scan phase
        stage: tool.exit_code === 0 ? 'completed' : tool.exit_code === null ? 'running' : 'completed',
        progress: tool.exit_code !== null ? 1 : 0,
        last_message: tool.exit_code === 0 ? 'Completed' : tool.exit_code === null ? 'Running' : `Exit code: ${tool.exit_code}`,
        updated_at: tool.completed_at || tool.started_at || new Date().toISOString(),
      }));
    }
    
    return [];
  }, [wsToolStates, tools]);

  // Track if initial load has been done to prevent reloading when tab becomes visible
  const initialLoadDoneRef = useRef<string | null>(null);

  // Poll for scan status updates when scan is running/queued
  useEffect(() => {
    if (!session) return;

    // If we've already loaded this scan, do a silent refresh (no loading state) and set up polling
    if (initialLoadDoneRef.current === scanId) {
      // Immediately set loading to false to prevent loading spinner when returning to tab
      setLoading(false);
      setInitialLoadFailed(false);
      
      let pollInterval: NodeJS.Timeout | null = null;
      
      // Silent refresh - fetch without showing loading state
      const silentRefresh = async () => {
        try {
          const data = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session);
          // Update scan data silently
          setScan((prevScan) => {
            if (!prevScan || JSON.stringify(prevScan) !== JSON.stringify(data)) {
              return data;
            }
            return prevScan;
          });
          
          // Set up polling if scan is running/queued
          const isRunning = data.status === 'running' || data.status === 'queued' || data.status === 'pending';
          if (isRunning) {
            pollInterval = setInterval(async () => {
              try {
                const pollData = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session);
                // Only update if data actually changed
                setScan((prevScan) => {
                  if (!prevScan || JSON.stringify(prevScan) !== JSON.stringify(pollData)) {
                    return pollData;
                  }
                  return prevScan;
                });
                // Stop polling if scan completed
                if (pollData.status === 'completed' || pollData.status === 'failed' || pollData.status === 'cancelled') {
                  if (pollInterval) {
                    clearInterval(pollInterval);
                    pollInterval = null;
                  }
                }
              } catch (err) {
                console.error('Error polling scan:', err);
              }
            }, 15000);
          }
        } catch (err) {
          console.error('Error silently refreshing scan:', err);
          // If silent refresh fails, fall through to normal load
          initialLoadDoneRef.current = null;
        }
      };
      
      silentRefresh();
      
      // Cleanup polling interval on unmount
      return () => {
        if (pollInterval) {
          clearInterval(pollInterval);
        }
      };
    }

    let pollInterval: NodeJS.Timeout | null = null;
    let consecutiveErrors = 0;
    let errorTimeout: NodeJS.Timeout | null = null;
    const MAX_CONSECUTIVE_ERRORS = 3; // Stop polling after 3 consecutive errors

    const loadScan = async () => {
      // Skip if scanId looks like a CVE ID
      if (scanId && scanId.toUpperCase().startsWith('CVE-')) {
        return;
      }

      try {
        // Clear any pending error timeout
        if (errorTimeout) {
          clearTimeout(errorTimeout);
          errorTimeout = null;
        }

        // Add timeout to prevent infinite loading
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

        let data: ScanDetail;
        try {
          data = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session, { signal: controller.signal });
          clearTimeout(timeoutId);
        } catch (fetchError) {
          clearTimeout(timeoutId);

          // Check if it's a timeout/abort error
          if (fetchError instanceof Error && (fetchError.name === 'AbortError' || fetchError.message.includes('timeout') || fetchError.message.includes('aborted'))) {
            throw new Error('Request timed out. Please try again.');
          }
          throw fetchError;
        }

        // Reset error counter on success and clear error
        consecutiveErrors = 0;
        setError(null);

        // Only update scan if data actually changed (avoid unnecessary re-renders)
        setScan((prevScan) => {
          if (!prevScan || JSON.stringify(prevScan) !== JSON.stringify(data)) {
            return data;
          }
          return prevScan;
        });

        // Mark initial load as done for this scanId
        initialLoadDoneRef.current = scanId;

        // Stop polling if scan is completed or failed
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
          }
        }
      } catch (err) {
        consecutiveErrors++;
        const errorMessage = err instanceof Error ? err.message : 'Network error while loading scan';
        console.error(`Error loading scan (attempt ${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}):`, err);

        // Only show error temporarily, don't stop polling unless too many consecutive errors
        // This handles transient network issues gracefully
        if (consecutiveErrors < MAX_CONSECUTIVE_ERRORS) {
          // Show error but continue polling - transient error
          // Error will auto-clear on next successful poll
          setError(`Connection issue (${consecutiveErrors}/${MAX_CONSECUTIVE_ERRORS}). Retrying...`);
        } else {
          // Too many consecutive errors - stop polling and show permanent error
          setError(`${errorMessage} (Failed ${MAX_CONSECUTIVE_ERRORS} times. Please refresh the page.)`);
          if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
          }
        }
      }
    };

    // Initial load (only if we haven't loaded this scanId yet)
    if (initialLoadDoneRef.current !== scanId) {
    setLoading(true);
    setInitialLoadFailed(false);
    loadScan().catch((err) => {
      // Mark initial load as failed so we show full-page error
      setInitialLoadFailed(true);
      setError(err instanceof Error ? err.message : 'Failed to load scan');
    }).finally(() => setLoading(false));
    }

    // Set up polling if scan is running/queued
    const checkAndPoll = async () => {
      // Skip if scanId looks like a CVE ID
      if (scanId && scanId.toUpperCase().startsWith('CVE-')) {
        return;
      }

      const currentScan = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session).catch(() => null);

      if (currentScan && (currentScan.status === 'running' || currentScan.status === 'queued' || currentScan.status === 'pending')) {
        // Start polling every 15 seconds (reduced frequency to avoid disrupting user reading)
        pollInterval = setInterval(loadScan, 15000); // 15 seconds
      }
    };

    // Check after initial load
    setTimeout(checkAndPoll, 1000);

    // Cleanup on unmount
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [scanId, session]);

  // Fetch project name
  useEffect(() => {
    const fetchProject = async () => {
      if (!session || !projectId) return;
      
      try {
        const data = await thandevFetchJSON<{ id: string; name: string }>(`/api/projects/${projectId}`, session);
        setProject(data);
      } catch (err) {
        console.error('Error fetching project:', err);
        // Set a fallback name if fetch fails
        setProject({ id: projectId, name: 'Project' });
      }
    };

    fetchProject();
  }, [projectId, session]);

  // Update current time every second for real-time timer countdown
  useEffect(() => {
    if (scan?.status === 'running' && scan?.started_at) {
      const interval = setInterval(() => {
        setCurrentTime(Date.now());
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [scan?.status, scan?.started_at]);

  // Track if tools have been loaded at least once
  const toolsLoadedRef = useRef(false);
  
  // Load tools data (with polling when scan is running)
  useEffect(() => {
    async function loadTools() {
      if (!session || !scanId) return;

      try {
        // Only show loading on first load
        if (!toolsLoadedRef.current) {
        setToolsLoading(true);
        }
        setToolsError(null);
        const data = await thandevFetchJSON<ToolsResponse>(`/api/scans/${scanId}/tools`, session);
        const newTools = data.items || [];
        // Only update if data actually changed (avoid unnecessary re-renders)
        setTools((prevTools) => {
          if (JSON.stringify(prevTools) !== JSON.stringify(newTools)) {
            return newTools;
          }
          return prevTools;
        });
        toolsLoadedRef.current = true;
      } catch (err) {
        console.error('Error loading tools:', err);
        setToolsError(err instanceof Error ? err.message : 'Failed to load tools');
      } finally {
        setToolsLoading(false);
      }
    }
    
    loadTools();
    
    // Poll for tools updates while scan is running
    const isRunning = scan?.status === 'running' || scan?.status === 'queued';
    let pollInterval: NodeJS.Timeout | null = null;
    
    if (isRunning) {
      // Poll every 15 seconds (reduced frequency to avoid disrupting user reading)
      pollInterval = setInterval(loadTools, 15000); // 15 seconds
    }
    
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [scanId, session, scan?.status]);

  // Load all available tools for the scan (for filter dropdown)
  useEffect(() => {
    async function loadAvailableTools() {
      if (!session || !scanId) return;

      try {
        const data = await thandevFetchJSON<{ tools: string[]; count: number }>(
          `/api/scans/${scanId}/findings/tools`,
          session
        );
        setAvailableTools(data.tools || []);
      } catch (err) {
        console.error('Error loading available tools:', err);
        // Fallback: extract from current findings if API fails
        if (findings.length > 0) {
          setAvailableTools(Array.from(new Set(findings.map(f => f.tool_name).filter(Boolean))).sort());
        }
      }
    }
    loadAvailableTools();
  }, [scanId, session, findings]);

  // Also update availableTools when findings change (fallback if API hasn't loaded)
  useEffect(() => {
    if (availableTools.length === 0 && findings.length > 0) {
      const toolsFromFindings = Array.from(new Set(findings.map(f => f.tool_name).filter(Boolean))).sort();
      if (toolsFromFindings.length > 0) {
        setAvailableTools(toolsFromFindings);
      }
    }
  }, [findings]);

  // Load top 100 findings for executive summary (ordered by severity)
  useEffect(() => {
    async function loadTopFindings() {
      if (!session || !scanId || !scan || scan.status !== 'completed') return;

      try {
        // Fetch top 100 findings ordered by severity (backend handles ordering)
        const data = await thandevFetchJSON<{ items: Finding[]; total: number; skip: number; limit: number }>(
          `/api/scans/${scanId}/findings?limit=100&skip=0`,
          session
        );
        setAllFindings(data.items || []);
      } catch (err) {
        console.error('Error loading top findings for summary:', err);
        // If fetch fails, allFindings will remain empty and we'll use findingsTotal for counts
      }
    }
    loadTopFindings();
  }, [scanId, session, scan?.status, scan?.id]);

  // Track if findings have been loaded at least once
  const findingsLoadedRef = useRef(false);

  // Load findings data from paginated endpoint
  useEffect(() => {
    let isPolling = false;
    
    async function loadFindings() {
      if (!session || !scanId) return;

      try {
        // Only show loading on initial load, not during polling
        if (!findingsLoadedRef.current) {
          setFindingsLoading(true);
        }
        setFindingsError(null); // Clear error before each attempt
        // Fetch findings with pagination and tool filter
        const skip = findingsPage * findingsLimit;
        let url = `/api/scans/${scanId}/findings?limit=${findingsLimit}&skip=${skip}`;
        if (selectedToolFilter !== 'all') {
          url += `&tool=${encodeURIComponent(selectedToolFilter)}`;
        }
        const data = await thandevFetchJSON<{ items: Finding[]; total: number; skip: number; limit: number }>(
          url,
          session
        );
        // Only update if data actually changed (avoid unnecessary re-renders during polling)
        const newFindings = data.items || [];
        const newTotal = data.total || 0;
        setFindings((prevFindings) => {
          if (!isPolling && JSON.stringify(prevFindings) !== JSON.stringify(newFindings)) {
            return newFindings;
          }
          // During polling, only update if findings count changed or new findings appeared
          if (isPolling && (prevFindings.length !== newFindings.length || JSON.stringify(prevFindings) !== JSON.stringify(newFindings))) {
            return newFindings;
          }
          return prevFindings;
        });
        setFindingsTotal(newTotal);
        // Clear error on successful fetch
        setFindingsError(null);
        // Debug: Log first finding to verify API response
        if (data.items && data.items.length > 0) {
          const firstFinding = data.items[0];
          console.log('First finding from API:', {
            title: firstFinding.title,
            url: firstFinding.url,
            http_method: firstFinding.http_method,
            parameter: firstFinding.parameter,
            impact_summary: firstFinding.impact_summary,
            remediation_summary: firstFinding.remediation_summary,
            default_remediation_steps: firstFinding.default_remediation_steps,
            vuln_type: firstFinding.vuln_type
          });
        }
        // Note: Findings are already set above with change detection
        findingsLoadedRef.current = true;

        // Collect unique CVE IDs from findings
        const uniqueCves = new Set<string>();
        if (data.items) {
          data.items.forEach((finding) => {
            if (finding.cve_id && finding.cve_id.trim()) {
              uniqueCves.add(finding.cve_id.trim().toUpperCase());
            }
          });
        }
        setCveIds(Array.from(uniqueCves).sort());
      } catch (err) {
        console.error('Error loading findings:', err);
        // Only set error if this is not a polling attempt (to avoid showing transient errors)
        if (!isPolling || !findingsLoadedRef.current) {
          setFindingsError(err instanceof Error ? err.message : 'Failed to load findings');
        }
      } finally {
        setFindingsLoading(false);
      }
    }
    loadFindings();
    
    // Poll for findings updates while scan is running (only on first page to avoid disrupting user)
    const isRunning = scan?.status === 'running' || scan?.status === 'queued';
    let pollInterval: NodeJS.Timeout | null = null;
    
    if (isRunning && findingsPage === 0) {
      // Poll every 15 seconds (reduced frequency to avoid disrupting user reading)
      pollInterval = setInterval(() => {
        isPolling = true;
        loadFindings();
      }, 15000); // 15 seconds
    }
    
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [scanId, session, findingsPage, findingsLimit, selectedToolFilter, scan?.status]);

  // State for HTTPX surface artifacts
  const [httpxSurfaceArtifacts, setHttpxSurfaceArtifacts] = useState<any>(null);

  // Load artifacts
  const loadArtifacts = async () => {
    if (!session) return;

    try {
      setArtifactsLoading(true);
      const data = await thandevFetchJSON<{ items: any[] }>(`/api/scans/${scanId}/artifacts`, session);
      setArtifacts(data);
      
      // Extract HTTPX surface artifacts
      const httpxArtifacts = data?.items?.filter((item: any) => item.type === 'httpx_surface') || [];
      setHttpxSurfaceArtifacts(httpxArtifacts.length > 0 ? httpxArtifacts[0] : null);
    } catch (err) {
      console.error('Error loading artifacts:', err);
    } finally {
      setArtifactsLoading(false);
    }
  };

  // Load artifacts when dependency tabs or enumeration tab are activated
  // Also reload if scan status changes (e.g., from running to completed) to pick up new artifacts
  useEffect(() => {
    if ((activeTab === 'tech-deps' || activeTab === 'repo-deps' || activeTab === 'ai-summary' || activeTab === 'enumeration') && !artifactsLoading && session) {
      loadArtifacts();
    }
  }, [activeTab, session, scan?.status]); // Reload when tab changes, session changes, or scan status changes

  // Auto-load instances when section is expanded and we need more than the sample
  // REMOVED: This useEffect was causing duplicate loads and flickering
  // Loading is now handled directly in the onClick handler

  // Function to fetch all instances for a finding (with pagination support)
  const loadAllInstances = async (findingId: string, showAll: boolean = false) => {
    if (!session || !scanId) {
      console.log('loadAllInstances: Missing session or scanId', { session: !!session, scanId });
      loadingRef.current[findingId] = false;
        return;
      }
      
    // Prevent duplicate calls using ref
    if (loadingRef.current[findingId]) {
      console.log('loadAllInstances: Already loading (ref check)', findingId);
      return;
    }
    
    // Check state as well
    if (loadingInstances[findingId]) {
      console.log('loadAllInstances: Already loading (state check)', findingId);
      return;
    }
    
    // Check if we already have all instances
    const existingInstances = expandedFindingInstances[findingId];
    if (existingInstances && existingInstances.length > 0 && !showAll) {
      const finding = findings.find(f => f.id === findingId);
      const affectedCount = finding?.affected_count || 0;
      const loadedCount = existingInstances.length;
      
      // Only skip if we have all instances (or close to it, within 5%)
      if (loadedCount >= affectedCount || (affectedCount > 0 && loadedCount >= affectedCount * 0.95)) {
        console.log('loadAllInstances: Already loaded all instances', findingId, 'count:', loadedCount, 'affected_count:', affectedCount);
        loadingRef.current[findingId] = false;
        return;
      }
    }
    
    // Mark as loading
    loadingRef.current[findingId] = true;

    try {
      setLoadingInstances(prev => ({ ...prev, [findingId]: true }));
      
      // If showAll is true, fetch all instances with high limit
      // Otherwise, just fetch what's needed for pagination
      const limit = showAll ? 100000 : 1000; // Use high limit to get all at once
      const url = `/api/scans/${scanId}/findings/${findingId}/instances?limit=${limit}&offset=0`;
      
      console.log('loadAllInstances: Fetching instances for', findingId, 'showAll=', showAll);
      
      let allInstances: FindingInstance[] = [];
      
      // Use high limit to get all at once (API supports up to 20000)
      const maxLimit = 20000;
      const paginatedUrl = `/api/scans/${scanId}/findings/${findingId}/instances?limit=${maxLimit}&offset=0`;
        const data = await thandevFetchJSON<{ 
          items: FindingInstance[], 
          total: number, 
          affected_count?: number,
          next_offset: number | null
        }>(paginatedUrl, session);
        
      console.log('loadAllInstances: Received instances:', { 
          total: data.total, 
        itemsReceived: data.items?.length || 0,
          next_offset: data.next_offset,
          affected_count: data.affected_count
        });
        
        if (data.items && data.items.length > 0) {
        allInstances = data.items;
        
        // If there are more instances than the limit, fetch remaining pages
        if (data.next_offset !== null && data.next_offset !== undefined && data.items.length < data.total) {
          let currentOffset = data.next_offset;
          while (currentOffset < data.total && allInstances.length < data.total) {
            const nextPageUrl = `/api/scans/${scanId}/findings/${findingId}/instances?limit=${maxLimit}&offset=${currentOffset}`;
            const nextPageData = await thandevFetchJSON<{ 
              items: FindingInstance[], 
              total: number, 
              next_offset: number | null
            }>(nextPageUrl, session);
            
            if (nextPageData.items && nextPageData.items.length > 0) {
              allInstances = [...allInstances, ...nextPageData.items];
              currentOffset = nextPageData.next_offset || currentOffset + nextPageData.items.length;
            } else {
              break;
            }
            
            // Safety check
            if (nextPageData.next_offset === null || nextPageData.next_offset === undefined) {
              break;
            }
          }
        }
      }
      
      // Check for data inconsistency
      const finding = findings.find(f => f.id === findingId);
      const expectedCount = finding?.affected_count || 0;
      
      console.log('✅ loadAllInstances: Fetched all instances:', { 
        findingId,
        total: allInstances.length,
        expectedCount,
        firstFew: allInstances.slice(0, 3).map(i => i.url || i.path),
        lastFew: allInstances.slice(-3).map(i => i.url || i.path)
      });
      
      if (expectedCount > 0 && allInstances.length < expectedCount) {
        console.warn(
          `⚠️ Data inconsistency detected: Finding ${findingId} has affected_count=${expectedCount} ` +
          `but only ${allInstances.length} instances were returned from API. ` +
          `This indicates an ingestion issue - instances were not fully stored during scan.`
        );
      }
      
      if (allInstances.length > 0) {
        // Update state with all instances
        setExpandedFindingInstances(prev => {
          const updated = { ...prev, [findingId]: allInstances };
          console.log('✅ loadAllInstances: Updated state, now have', updated[findingId]?.length || 0, 'instances for', findingId);
          console.log('✅ loadAllInstances: First 3 URLs:', allInstances.slice(0, 3).map(i => i.url || i.path));
          return updated;
        });
        // Also ensure loading state is cleared since we have data
        loadingRef.current[findingId] = false;
        setLoadingInstances(prev => ({ ...prev, [findingId]: false }));
      } else {
        console.warn('⚠️ loadAllInstances: No instances fetched', { findingId, expectedCount });
        // Show a helpful message if we expected instances but got none
        if (expectedCount > 0) {
          console.error(
            `No instances found in database for finding ${findingId}.\n` +
            `Expected: ${expectedCount} URLs\n` +
            `Found: 0 URLs\n\n` +
            `This indicates an ingestion issue. The finding was detected but instance data was not stored.`
          );
        }
      }
    } catch (err) {
      console.error(`❌ Error loading instances for finding ${findingId}:`, err);
      const errorMessage = err instanceof Error ? err.message : String(err);
      console.error('Error details:', {
        findingId,
        scanId,
        error: errorMessage,
        stack: err instanceof Error ? err.stack : undefined
      });
      
      // Check if it's a network error
      if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
        alert(`Failed to load URLs: Network error. Please check:\n1. Backend is running\n2. No CORS issues\n3. Check browser console for details`);
      } else {
        alert(`Failed to load all URLs: ${errorMessage}`);
      }
    } finally {
      loadingRef.current[findingId] = false;
      setLoadingInstances(prev => ({ ...prev, [findingId]: false }));
    }
  };

  // Load tech stack (aggregated from url_sca artifact + ToolResult.meta fallback)
  // Only for Pro/Advanced scans
  useEffect(() => {
    if (!session || !scanId || !scan) return;
    
    // Skip tech stack for basic scans
    if (scan.scan_level === 'basic') {
      setTechStackLoading(false);
      setTechStack(null);
      return;
    }

    const fetchTechStack = async () => {
      // Only show loading on initial load, not during polling
      if (!techStack) {
      setTechStackLoading(true);
      }
      try {
        const data = await thandevFetchJSON<any>(`/api/scans/${scanId}/tech-stack`, session);
        console.log('[TECH-STACK] Received data from API:', data);
        console.log('[TECH-STACK] Fingerprint:', data?.fingerprint);
        console.log('[TECH-STACK] Technologies count:', data?.fingerprint?.technologies?.length || 0);
        // Only update if data actually changed (avoid unnecessary re-renders)
        setTechStack((prevTechStack) => {
          if (JSON.stringify(prevTechStack) !== JSON.stringify(data)) {
            return data;
          }
          return prevTechStack;
        });
      } catch (error) {
        console.error('Failed to fetch tech stack:', error);
        setTechStack(null);
      } finally {
        setTechStackLoading(false);
      }
    };

    fetchTechStack();

    // Poll if scan is running (tech stack can update as tools complete)
    const isRunning = scan.status === 'running' || scan.status === 'queued';
    const interval = isRunning ? setInterval(fetchTechStack, 20000) : null; // Poll every 20 seconds (reduced frequency to avoid disrupting user reading)

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [scanId, scan?.status, scan?.scan_level, session]);

  // Load enumeration inventory when tab is activated
  // Only for Pro/Advanced scans
  useEffect(() => {
    if (activeTab !== 'enumeration' || !session || !scanId || !scan) return;
    
    // Skip for basic scans
    if (scan.scan_level === 'basic') {
      setInventoryLoading(false);
      setInventory(null);
      return;
    }

    const fetchInventory = async () => {
      // Only show loading on initial load, not during polling
      if (!inventory) {
      setInventoryLoading(true);
      }
      try {
        const data = await thandevFetchJSON<any>(`/api/scans/${scanId}/inventory`, session);
        // Only update if data actually changed (avoid unnecessary re-renders)
        const newInventory = data?.inventory || null;
        if (JSON.stringify(newInventory) !== JSON.stringify(inventory)) {
          setInventory(newInventory);
        }
      } catch (error) {
        console.error('Failed to fetch enumeration inventory:', error);
        // Don't clear inventory on error during polling
        if (!inventory) {
        setInventory(null);
        }
      } finally {
        setInventoryLoading(false);
      }
    };

    fetchInventory();
    
    // Poll for enumeration updates while scan is running
    const isRunning = scan.status === 'running' || scan.status === 'queued';
    let pollInterval: NodeJS.Timeout | null = null;
    
    if (isRunning) {
      // Poll every 20 seconds (reduced frequency to avoid disrupting user reading)
      pollInterval = setInterval(fetchInventory, 20000);
    }
    
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [activeTab, session, scanId, scan?.status, scan?.scan_level]);

  // Helper functions
  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const calculateDuration = (started: string | null | undefined, completed: string | null | undefined) => {
    if (!started || !completed) return 'N/A';
    const start = new Date(started).getTime();
    const end = new Date(completed).getTime();
    const seconds = Math.floor((end - start) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}m ${remainingSeconds}s`;
  };

  const cancelScan = async () => {
    if (!session || !scan) return;

    if (!confirm('Are you sure you want to cancel this scan?')) {
      return;
    }

    setCancelling(true);
    setError(null);

    try {
      await thandevFetchJSON(
        `/api/scans/${scanId}/cancel`,
        session,
        {
          method: 'PATCH',
        }
      );

      // Reload scan to get updated status
      const data = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session);
      setScan(data);

      alert('Scan cancelled successfully');
    } catch (err) {
      console.error('Error cancelling scan:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to cancel scan';
      setError(errorMessage);
      alert(`Failed to cancel scan: ${errorMessage}`);
    } finally {
      setCancelling(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
        return 'bg-green-900/40 text-green-200 border-green-500/50';
      case 'running':
        return 'bg-blue-900/40 text-blue-200 border-blue-500/50';
      case 'failed':
        return 'bg-red-900/40 text-red-200 border-red-500/50';
      case 'queued':
        return 'bg-yellow-900/40 text-yellow-200 border-yellow-500/50';
      case 'pending':
        return 'bg-slate-800/40 text-slate-200 border-slate-600/50';
      default:
        return 'bg-slate-800/40 text-slate-200 border-slate-600/50';
    }
  };

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case 'advanced':
        return 'bg-purple-900/40 text-purple-200 border-purple-500/50';
      case 'pro':
        return 'bg-indigo-900/40 text-indigo-200 border-indigo-500/50';
      case 'basic':
        return 'bg-blue-900/40 text-blue-200 border-blue-500/50';
      default:
        return 'bg-slate-800/40 text-slate-200 border-slate-600/50';
    }
  };

  const severityClasses = (sev?: string | null) => {
    const s = (sev ?? '').toLowerCase();
    if (s === 'critical') return 'bg-red-900/40 text-red-200 border-red-500/50';
    if (s === 'high') return 'bg-orange-900/40 text-orange-200 border-orange-500/50';
    if (s === 'medium') return 'bg-yellow-900/40 text-yellow-200 border-yellow-500/50';
    if (s === 'low') return 'bg-green-900/40 text-green-200 border-green-500/50';
    return 'bg-slate-800/40 text-slate-200 border-slate-600/50';
  };

  // Status badge component
  function StatusBadge({ status }: { status: FindingStatus | string | null | undefined }) {
    if (!status) return null;
    const normalized = (status as string).toLowerCase() as FindingStatus;
    const base = 'px-2 py-0.5 rounded-full text-[10px] font-medium border';

    switch (normalized) {
      case 'open':
        return (
          <span className={`${base} border-rose-500/60 bg-rose-900/30 text-rose-100`}>
            Open
          </span>
        );
      case 'acknowledged':
        return (
          <span className={`${base} border-amber-500/60 bg-amber-900/30 text-amber-100`}>
            Acknowledged
          </span>
        );
      case 'resolved':
        return (
          <span className={`${base} border-emerald-500/60 bg-emerald-900/30 text-emerald-100`}>
            Resolved
          </span>
        );
      case 'suppressed':
        return (
          <span className={`${base} border-slate-500/60 bg-slate-900/60 text-slate-200`}>
            Suppressed
          </span>
        );
      default:
        return (
          <span className={`${base} border-slate-600 bg-slate-900/60 text-slate-200`}>
            {status}
          </span>
        );
    }
  }

  // Loading state
  // Show full-page error only if initial load failed (not polling errors)
  if (initialLoadFailed && !scan) {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader
            user={session?.user}
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-6xl mx-auto">
              <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-4 mb-4">
                <p className="text-red-300">{error || 'Failed to fetch'}</p>
              </div>
              <Link
                href={`/projects/${projectId}/scans`}
                className="text-indigo-400 hover:text-indigo-300 underline"
              >
                ← Back to scans
              </Link>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (loading || sessionStatus === 'loading') {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader
            user={session?.user}
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-6xl mx-auto">
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                <p className="mt-4" style={{ color: 'var(--muted)' }}>Loading scan...</p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Error state - only show full-page error if initial load failed and no scan data
  // Polling errors should not replace the entire page content
  if (initialLoadFailed && !scan) {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader
            user={session?.user}
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-6xl mx-auto">
              <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-4 mb-4">
                <p className="text-red-300">{error || 'Failed to fetch'}</p>
              </div>
              <Link
                href={`/projects/${projectId}/scans`}
                className="text-indigo-400 hover:text-indigo-300 underline"
              >
                ← Back to scans
              </Link>
            </div>
          </main>
        </div>
      </div>
    );
  }

  // If scan is null but we're not in initial load failure, show loading
  if (!scan) {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader
            user={session?.user}
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-6xl mx-auto">
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                <p className="mt-4" style={{ color: 'var(--muted)' }}>Loading scan...</p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  // Calculate network & TLS metrics from loaded findings
  const nmapFindings = findings.filter(f => f.tool_name?.toLowerCase() === 'nmap');
  const sslscanFindings = findings.filter(f => f.tool_name?.toLowerCase() === 'sslscan');
  const openPortsCount = nmapFindings.length;
  const hasTlsIssues = sslscanFindings.length > 0;

  // Generate executive summary if not available but findings exist
  // Prefer canonical keys (severity_breakdown, findings_count) with fallback to deprecated (findings_by_severity, total_findings)
  // Backend emits both during migration period. See MIGRATION_NOTES.md
  const generateExecutiveSummary = () => {
    if (scan?.summary?.executive_summary) {
      return scan.summary.executive_summary;
    }

    // Prefer canonical keys with fallback to deprecated
    let criticalCount = 0, highCount = 0, mediumCount = 0, lowCount = 0, infoCount = 0;
    const totalFindingsCount = findingsTotal || (scan?.summary?.findings_count ?? scan?.summary?.total_findings ?? 0);

    // Prefer canonical severity_breakdown, fallback to deprecated findings_by_severity
    const severityBreakdown = scan?.summary?.severity_breakdown ?? scan?.summary?.findings_by_severity;
    if (severityBreakdown && typeof severityBreakdown === 'object') {
      // Use severity breakdown from scan summary (complete data)
      criticalCount = severityBreakdown.critical || severityBreakdown.CRITICAL || 0;
      highCount = severityBreakdown.high || severityBreakdown.HIGH || 0;
      mediumCount = severityBreakdown.medium || severityBreakdown.MEDIUM || 0;
      lowCount = severityBreakdown.low || severityBreakdown.LOW || 0;
      infoCount = severityBreakdown.info || severityBreakdown.INFO || 0;
    } else {
      // Fallback: use top 100 findings to estimate (may not be complete)
      const findingsForSummary = allFindings.length > 0 ? allFindings : findings;
      criticalCount = findingsForSummary.filter(f => f.severity?.toLowerCase() === 'critical').length;
      highCount = findingsForSummary.filter(f => f.severity?.toLowerCase() === 'high').length;
      mediumCount = findingsForSummary.filter(f => f.severity?.toLowerCase() === 'medium').length;
      lowCount = findingsForSummary.filter(f => f.severity?.toLowerCase() === 'low').length;
      infoCount = findingsForSummary.filter(f => f.severity?.toLowerCase() === 'info').length;
    }

    if (totalFindingsCount === 0 || scan?.status !== 'completed') {
      return null;
    }

    if (criticalCount > 0) {
      return `CRITICAL: ${criticalCount} critical vulnerability${criticalCount > 1 ? 'ies' : 'y'} detected requiring immediate attention. ${highCount > 0 ? `Additionally, ${highCount} high-severity issue${highCount > 1 ? 's' : ''} were found.` : ''} This scan identified ${totalFindingsCount} total finding${totalFindingsCount > 1 ? 's' : ''} across the target.`;
    } else if (highCount > 0) {
      return `HIGH PRIORITY: ${highCount} high-severity vulnerability${highCount > 1 ? 'ies' : 'y'} found. Review recommended. ${mediumCount > 0 ? `The scan also detected ${mediumCount} medium-severity issue${mediumCount > 1 ? 's' : ''}.` : ''} Total findings: ${totalFindingsCount}.`;
    } else if (mediumCount > 0 || lowCount > 0) {
      return `Scan completed with ${totalFindingsCount} finding${totalFindingsCount > 1 ? 's' : ''}. ${mediumCount > 0 ? `${mediumCount} medium-severity` : `${lowCount} low-severity`} issue${(mediumCount || lowCount) > 1 ? 's' : ''} detected. No critical or high-severity vulnerabilities found.`;
    } else if (infoCount > 0) {
      return `Scan completed successfully. ${infoCount} informational finding${infoCount > 1 ? 's' : ''} detected. No security vulnerabilities identified.`;
    } else {
      return `Scan completed with ${totalFindingsCount} finding${totalFindingsCount > 1 ? 's' : ''}. Review recommended.`;
    }
  };

  // Generate top risks if not available but findings exist
  // Use allFindings (complete dataset) instead of paginated findings
  const generateTopRisks = () => {
    if (scan?.summary?.top_risks && scan.summary.top_risks.length > 0) {
      return scan.summary.top_risks;
    }
    // Use allFindings if available, otherwise fallback to paginated findings
    const findingsForRisks = allFindings.length > 0 ? allFindings : findings;

    if (findingsForRisks.length === 0 || scan?.status !== 'completed') {
      return [];
    }

    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    const sortedFindings = [...findingsForRisks].sort((a, b) => {
      const aSev = severityOrder[a.severity?.toLowerCase() as keyof typeof severityOrder] ?? 99;
      const bSev = severityOrder[b.severity?.toLowerCase() as keyof typeof severityOrder] ?? 99;
      if (aSev !== bSev) return aSev - bSev;
      const aScore = a.cvss_score ?? 0;
      const bScore = b.cvss_score ?? 0;
      return bScore - aScore;
    });

    return sortedFindings.slice(0, 5).map(f => ({
      title: f.title,
      severity: f.severity || 'info',
      cve_id: f.cve_id,
      cvss_score: f.cvss_score,
      url: f.url,
    }));
  };

  const executiveSummary = generateExecutiveSummary();
  const topRisks = generateTopRisks();

  // PDF download handler
  const handleDownloadPdf = async (mode: 'full' | 'executive') => {
    if (!session) {
      alert('Session required. Please log in again.');
      return;
    }

    const setDownloading = mode === 'full' ? setDownloadingFull : setDownloadingExecutive;

    try {
      setDownloading(true);
      const url = mode === 'executive'
        ? `/api/scans/${scanId}/report.pdf?mode=executive`
        : `/api/scans/${scanId}/report.pdf`;

      const blob = await thandevFetchPDF(url, session);

      const fileUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = fileUrl;
      a.download = mode === 'executive'
        ? `thandev-scan-${scanId}-executive.pdf`
        : `thandev-scan-${scanId}-full.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(fileUrl);
    } catch (e) {
      console.error('Error downloading PDF:', e);
      alert(`Failed to download ${mode === 'executive' ? 'executive summary' : 'full report'}. Please try again.`);
    } finally {
      setDownloading(false);
    }
  };

  // CSV download handler for enumeration data
  const handleDownloadCSV = async () => {
    if (!session || !inventory) {
      alert('Session required or no enumeration data available.');
      return;
    }

    try {
      setDownloadingCSV(true);
      
      // Build CSV content
      const rows: string[] = [];
      
      // Header
      rows.push('URL,Type,Parameters,Technologies');
      
      // Add all URLs
      const allUrls = inventory.discovery?.merged?.all_urls || [];
      const paramUrls = inventory.discovery?.merged?.param_urls || [];
      const paramUrlSet = new Set(paramUrls);
      const technologies = inventory.technologies || [];
      const techString = technologies.join('; ');
      
      allUrls.forEach((url: string) => {
        const isParam = paramUrlSet.has(url);
        const type = isParam ? 'Parameterized' : 'Standard';
        const params = isParam && inventory.discovery?.arjun?.params_by_url?.[url] 
          ? (Array.isArray(inventory.discovery.arjun.params_by_url[url]) 
              ? inventory.discovery.arjun.params_by_url[url].join('; ')
              : Object.keys(inventory.discovery.arjun.params_by_url[url]).join('; '))
          : '';
        
        // Escape CSV values
        const escapeCSV = (val: string) => {
          if (val.includes(',') || val.includes('"') || val.includes('\n')) {
            return `"${val.replace(/"/g, '""')}"`;
          }
          return val;
        };
        
        rows.push(`${escapeCSV(url)},${type},${escapeCSV(params)},${escapeCSV(techString)}`);
      });
      
      const csvContent = rows.join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const fileUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = fileUrl;
      a.download = `thandev-scan-${scanId}-enumeration.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(fileUrl);
    } catch (e) {
      console.error('Error downloading CSV:', e);
      alert('Failed to download CSV. Please try again.');
    } finally {
      setDownloadingCSV(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        showLogo={!sidebarOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader
          user={session?.user}
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-6xl mx-auto space-y-6">
            {/* Polling error banner - Show non-intrusive banner for transient errors */}
            {error && !initialLoadFailed && (
              <div className="bg-yellow-900/20 border border-yellow-500/50 rounded-lg p-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-yellow-300 text-sm">{error}</p>
                </div>
                <button
                  onClick={() => setError(null)}
                  className="text-yellow-400 hover:text-yellow-300 text-sm underline"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Error banner - Show prominently at top if scan has error */}
            {scan?.error_message && scan.status === 'failed' && (
              <div className="rounded-xl border-2 border-red-500/70 bg-red-900/30 p-4 shadow-lg">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold mb-1 text-sm text-red-300">Scan Error</div>
                    <pre className="whitespace-pre-wrap text-sm text-red-200 font-sans mb-3">{scan.error_message}</pre>
                    <button
                      onClick={async () => {
                        if (!session) {
                          alert('Session required. Please log in again.');
                          return;
                        }
                        try {
                          // Create a new scan with the same level
                          const newScan = await thandevFetchJSON<ScanDetail>(
                            '/api/scans',
                            session,
                            {
                              method: 'POST',
                              body: JSON.stringify({
                                project_id: projectId,
                                scan_level: scan.scan_level,
                              }),
                            }
                          );
                          // Navigate to the new scan
                          router.push(`/projects/${projectId}/scans/${newScan.id}`);
                        } catch (err) {
                          console.error('Error retrying scan:', err);
                          alert(`Failed to retry scan: ${err instanceof Error ? err.message : 'Unknown error'}`);
                        }
                      }}
                      className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border transition hover:opacity-80"
                      style={{
                        background: 'var(--surface)',
                        borderColor: 'var(--border)',
                        color: 'var(--fg)',
                      }}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Retry Scan
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Header: Back to Project + Project Name */}
            <div className="mb-6 flex items-center justify-between">
              <Link
                href={`/projects/${projectId}`}
                className="flex items-center gap-2 text-sm font-medium transition-colors hover:opacity-80"
                style={{ color: 'var(--muted)' }}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                <span>Back to Project</span>
              </Link>
              <h1 className="text-2xl font-semibold" style={{ color: 'var(--fg)' }}>
                {project?.name || 'Loading...'}
              </h1>
            </div>

            {/* Tabs */}
            <div className="border-b mb-6" style={{ borderColor: 'var(--border)' }}>
              <nav className="flex space-x-8">
                {[
                  { id: 'overview', label: 'Overview' },
                  { id: 'findings', label: 'Findings' },
                  ...(scan?.scan_level !== 'basic' ? [{ id: 'enumeration', label: 'Enumeration' }] : []),
                  ...(scan?.scan_level !== 'basic' ? [{ id: 'tech-deps', label: 'Tech & Dependencies' }] : []),
                  { id: 'repo-deps', label: 'Repo Dependencies' },
                  { id: 'ai-summary', label: 'AI Summary' },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id as any)}
                    className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors relative ${activeTab === tab.id
                      ? 'border-indigo-500 text-indigo-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                      }`}
                    style={{
                      borderBottomColor: activeTab === tab.id ? 'var(--brand)' : 'transparent',
                      color: activeTab === tab.id ? 'var(--brand)' : 'var(--muted)',
                    }}
                  >
                    {tab.label}
                    {activeTab === tab.id && (
                      <span 
                        className="absolute bottom-0 left-1/2 transform -translate-x-1/2 w-1 h-1 rounded-full"
                        style={{ 
                          background: 'var(--brand)',
                          bottom: '-2px'
                        }}
                      />
                    )}
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab Content */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {/* Header Section with Scan ID, Status, Progress, and Action Buttons */}
                <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                  <div className="space-y-4">
                    {/* Scan ID and Status Row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div>
                          <div className="text-sm font-mono" style={{ color: 'var(--muted)' }}>
                            ID: {scan?.id.substring(0, 8).toUpperCase()}...
                          </div>
                          {/* Progress Bar */}
                          {(scan?.status === 'running' || scan?.status === 'queued') && (
                            <div className="mt-2 w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
                              <div 
                                className="h-full transition-all duration-300"
                                style={{ 
                                  background: 'var(--brand)',
                                  width: `${scan?.progress_pct || 0}%`
                                }}
                              />
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {scan?.status === 'running' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border flex items-center gap-1.5" style={{ background: '#10b981', color: '#ffffff', borderColor: '#10b981' }}>
                              <span className="w-1.5 h-1.5 rounded-full bg-white"></span>
                              RUNNING
                            </span>
                          )}
                          {scan?.status === 'queued' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#f59e0b', color: '#ffffff', borderColor: '#f59e0b' }}>
                              QUEUED
                            </span>
                          )}
                          {scan?.status === 'completed' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#10b981', color: '#ffffff', borderColor: '#10b981' }}>
                              COMPLETED
                            </span>
                          )}
                          {scan?.scan_level === 'advanced' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#a855f7', color: '#ffffff', borderColor: '#a855f7' }}>
                              ADVANCE
                            </span>
                          )}
                          {scan?.scan_level === 'pro' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#6366f1', color: '#ffffff', borderColor: '#6366f1' }}>
                              PRO
                            </span>
                          )}
                        </div>
                      </div>
                      {/* Action Buttons */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleDownloadPdf('full')}
                          disabled={downloadingFull || downloadingExecutive}
                          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', color: 'var(--fg)' }}
                        >
                          {downloadingFull ? (
                            <>
                              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: 'var(--muted)' }}></span>
                              <span>Preparing...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                              </svg>
                              <span>Download Full PDF</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => handleDownloadPdf('executive')}
                          disabled={downloadingFull || downloadingExecutive}
                          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', color: 'var(--fg)' }}
                        >
                          {downloadingExecutive ? (
                            <>
                              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: 'var(--muted)' }}></span>
                              <span>Preparing...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                              </svg>
                              <span>Executive PDF</span>
                            </>
                          )}
                        </button>
                        {(scan?.status === 'running' || scan?.status === 'queued') && (
                          <button
                            onClick={cancelScan}
                            disabled={cancelling}
                            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                            style={{ borderColor: '#ef4444', background: '#ef4444', color: '#ffffff' }}
                          >
                            {cancelling ? (
                              <>
                                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent border-white"></span>
                                <span>Cancelling...</span>
                              </>
                            ) : (
                              'CANCEL SCAN'
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid gap-6 md:grid-cols-3">
                  {/* Left column - Main content */}
                  <div className="md:col-span-2 space-y-6">
                    {/* Executive Summary card */}
                    <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                      <div className="flex items-center gap-2 mb-4">
                        <svg className="w-5 h-5" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                        </svg>
                        <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Executive Summary</h2>
                      </div>
                    {executiveSummary ? (
                      <div className="space-y-4">
                        <p className="text-sm leading-relaxed" style={{ color: 'var(--fg)' }}>
                          {executiveSummary}
                        </p>
                        {/* Coverage line: unique categories across all findings */}
                        {(() => {
                          const uniqueCats = Array.from(new Set(
                            (findings ?? []).flatMap((f) => f.categories ?? [])
                          ));
                          return uniqueCats.length > 0 && (
                            <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
                              Coverage: {uniqueCats.map(formatCategory).join(' • ')}
                            </p>
                          );
                        })()}
                        {cveIds.length > 0 && (
                          <div className="mb-4">
                            <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>Related security news</h3>
                            <div className="relative inline-block group">
                              <Link
                                href={`/dashboard/cve/${encodeURIComponent(cveIds[0])}`}
                                className="inline-flex items-center gap-1.5 text-xs text-[var(--brand)] hover:text-[var(--brand)]/80 hover:underline transition-colors"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                                </svg>
                                View details for {cveIds[0]}
                                {cveIds.length > 1 && (
                                  <span className="ml-1 text-[var(--muted)]">({cveIds.length} CVEs)</span>
                                )}
                              </Link>
                              {cveIds.length > 1 && (
                                <div className="absolute left-0 top-full mt-2 z-20 hidden group-hover:block w-64 p-3 rounded-lg border shadow-xl" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                                  <p className="text-xs font-medium mb-2" style={{ color: 'var(--fg)' }}>All CVEs in this scan:</p>
                                  <div className="flex flex-wrap gap-1.5">
                                    {cveIds.map((cve) => (
                                      <span key={cve} className="text-xs font-mono px-1.5 py-0.5 rounded bg-[var(--surface-2)] border" style={{ color: 'var(--muted)', borderColor: 'var(--border)' }}>
                                        {cve}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                        {topRisks.length > 0 && (
                          <div>
                            <h3 className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>Top Risks</h3>
                            <ul className="list-disc list-inside space-y-1">
                              {topRisks.map((risk, idx) => {
                                // Handle both string and object formats
                                if (typeof risk === 'string') {
                                  return (
                                    <li key={`risk-string-${idx}-${risk.substring(0, 20)}`} className="text-sm" style={{ color: 'var(--fg)' }}>{risk}</li>
                                  );
                                }

                                // Handle object format with finding details
                                const riskObj = risk as TopRisk;
                                const severity = riskObj.severity?.toUpperCase() || 'INFO';
                                const severityColor = severityClasses(riskObj.severity || 'info');

                                // Generate stable key from object properties
                                const objectKey = `${riskObj.title || 'untitled'}-${riskObj.cve_id || idx}-${riskObj.url || ''}`;

                                return (
                                  <li key={objectKey} className="text-sm" style={{ color: 'var(--fg)' }}>
                                <span className="mr-2">
                                  <SeverityBadge severity={riskObj.severity || 'info'} />
                                    </span>
                                    <span className="font-semibold">{riskObj.title || 'Untitled finding'}</span>
                                    {riskObj.cvss_score != null && typeof riskObj.cvss_score === 'number' && (
                                      <> · CVSS {riskObj.cvss_score.toFixed(1)}</>
                                    )}
                                    {riskObj.cve_id && (
                                      <> · {riskObj.cve_id}</>
                                    )}
                                    {riskObj.url && (
                                      <>
                                        {' · '}
                                        <a
                                          href={riskObj.url}
                                          target="_blank"
                                          rel="noreferrer"
                                          className="underline decoration-dotted text-indigo-400 hover:text-indigo-300"
                                        >
                                          View
                                        </a>
                                      </>
                                    )}
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-center py-12 relative">
                        {/* Large document icon with dashed circle */}
                        <div className="relative mx-auto mb-6" style={{ width: '120px', height: '120px' }}>
                          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 120 120" fill="none">
                            <circle cx="60" cy="60" r="55" stroke="var(--border)" strokeWidth="2" strokeDasharray="8 4" fill="none" opacity="0.5" />
                          </svg>
                          <div className="absolute inset-0 flex items-center justify-center">
                            <svg className="w-16 h-16" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                          </div>
                        </div>
                        <p className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                          Executive summary will be available once the primary vulnerability scanning phase completes.
                        </p>
                        {/* Faint brain/gear icon on the right */}
                        <div className="absolute right-8 top-8 opacity-10">
                          <svg className="w-24 h-24" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Findings card */}
                  <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
                        Findings {findingsTotal > 0 && <span style={{ color: 'var(--muted)' }}>{findingsTotal}</span>}
                      </h2>
                      <div className="flex items-center gap-3">
                        {/* Tool filter dropdown */}
                        {(availableTools.length > 0 || findingsTotal > 0) && (
                          <select
                            value={selectedToolFilter}
                            onChange={(e) => {
                              setSelectedToolFilter(e.target.value);
                              setFindingsPage(0);
                            }}
                            className="text-sm px-3 py-1.5 rounded-lg border appearance-none cursor-pointer font-medium"
                            style={{
                              background: 'var(--surface)',
                              borderColor: 'var(--border)',
                              color: 'var(--fg)',
                              cursor: 'pointer'
                            }}
                          >
                            <option value="all" style={{ background: 'var(--bg)', color: 'var(--fg)', padding: '8px' }}>All Tools</option>
                            {(availableTools.length > 0 ? availableTools : Array.from(new Set(findings.map(f => f.tool_name).filter(Boolean))).sort()).map(toolName => (
                              <option key={toolName} value={toolName} style={{ background: 'var(--bg)', color: 'var(--fg)', padding: '8px' }}>
                                {toolName.charAt(0).toUpperCase() + toolName.slice(1)}
                              </option>
                            ))}
                          </select>
                        )}
                        {(() => {
                          const infoCount = findings.filter(f => f.severity?.toLowerCase() === 'info').length;
                          if (infoCount > 0) {
                            return (
                              <label className="flex items-center gap-2 text-sm cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={showInfoFindings}
                                  onChange={(e) => {
                                    setShowInfoFindings(e.target.checked);
                                    setFindingsPage(0);
                                  }}
                                  className="w-4 h-4 rounded border"
                                  style={{
                                    background: showInfoFindings ? 'var(--brand)' : 'var(--surface)',
                                    borderColor: 'var(--border)',
                                    accentColor: 'var(--brand)'
                                  }}
                                />
                                <span style={{ color: 'var(--fg)' }}>
                                  Show informational
                                </span>
                              </label>
                            );
                          }
                          return null;
                        })()}
                      </div>
                    </div>

                    {/* Pagination controls at top */}
                    {findingsTotal > findingsLimit && (
                      <div className="flex items-center justify-between mb-4 pb-4 border-b" style={{ borderColor: 'var(--border)' }}>
                        <div className="text-sm" style={{ color: 'var(--muted)' }}>
                          Showing {findingsPage * findingsLimit + 1} - {Math.min((findingsPage + 1) * findingsLimit, findingsTotal)} of {findingsTotal} findings
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setFindingsPage(prev => Math.max(0, prev - 1))}
                            disabled={findingsPage === 0 || findingsLoading}
                            className="px-3 py-1.5 text-sm rounded-lg border disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            style={{
                              background: findingsPage === 0 ? 'var(--surface-2)' : 'var(--surface-2)',
                              borderColor: 'var(--border)',
                              color: findingsPage === 0 ? 'var(--muted)' : 'var(--fg)'
                            }}
                          >
                            Previous
                          </button>
                          <span className="text-sm px-2" style={{ color: 'var(--muted)' }}>
                            Page {findingsPage + 1} of {Math.ceil(findingsTotal / findingsLimit)}
                          </span>
                          <button
                            onClick={() => setFindingsPage(prev => prev + 1)}
                            disabled={findingsPage >= Math.ceil(findingsTotal / findingsLimit) - 1 || findingsLoading}
                            className="px-3 py-1.5 text-sm rounded-lg border disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                            style={{
                              background: findingsPage >= Math.ceil(findingsTotal / findingsLimit) - 1 ? 'var(--surface-2)' : 'var(--surface-2)',
                              borderColor: 'var(--border)',
                              color: findingsPage >= Math.ceil(findingsTotal / findingsLimit) - 1 ? 'var(--muted)' : 'var(--fg)'
                            }}
                          >
                            Next
                          </button>
                        </div>
                      </div>
                    )}
                    {findingsLoading ? (
                      <div className="space-y-4">
                        {[...Array(3)].map((_, i) => (
                          <div key={i} className="border rounded-lg p-4 animate-pulse" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-2"></div>
                            <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                          </div>
                        ))}
                      </div>
                    ) : findingsError ? (
                      <div className="text-sm text-red-400 py-4">{findingsError}</div>
                    ) : findings.length === 0 ? (
                      <div className="text-center py-8">
                        <div className="w-12 h-12 mx-auto mb-3 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', opacity: 0.5 }}>
                          <svg className="w-6 h-6" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <p className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>No findings detected</p>
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {scan?.status === 'completed'
                            ? 'This scan completed successfully but did not identify any security vulnerabilities or issues.'
                            : 'Findings will appear here once the scan completes.'}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {findings.filter(f => showInfoFindings || f.severity?.toLowerCase() !== 'info').map((finding, idx) => {
                          // Generate stable key from finding properties
                          const findingKey = finding.id || `${finding.title || 'finding'}-${finding.url || ''}-${idx}`;
                          return (
                            <div key={findingKey} className="border rounded-lg p-4 transition-colors hover:opacity-80 overflow-hidden relative" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', maxWidth: '100%', wordWrap: 'break-word', overflowWrap: 'break-word' }}>
                              {/* External link icon in top right */}
                              <button className="absolute top-4 right-4 p-1 rounded hover:opacity-80" style={{ color: 'var(--muted)' }}>
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                </svg>
                              </button>
                              
                              {/* Header: Severity + Status + Title */}
                              <div className="flex items-start justify-between gap-2 mb-3 pr-8">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 flex-wrap mb-2">
                                    <SeverityBadge severity={finding.severity || 'info'} />
                                    {finding.status && <StatusBadge status={finding.status} />}
                                    {finding.not_seen_in_latest_scan !== null && (
                                      finding.not_seen_in_latest_scan ? (
                                        <span className="px-2 py-1 text-xs font-medium rounded-full border" style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fbbf24' }}>
                                          NOT SEEN IN LATEST
                                        </span>
                                      ) : (
                                        <span className="px-2 py-1 text-xs font-medium rounded-full border" style={{ background: '#d1fae5', color: '#065f46', borderColor: '#10b981' }}>
                                          STILL PRESENT
                                        </span>
                                      )
                                    )}
                                  </div>
                                  <h4 className="font-semibold text-sm break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>{finding.title}</h4>
                                </div>
                              </div>

                              <div className="space-y-3">
                                {/* 1. Where it was found - ALWAYS SHOW with tolerant logic */}
                                <div className="space-y-1">
                                  <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                    Where it was found
                                  </div>
                                  {(() => {
                                    // Check if this is a grouped finding
                                    const affectedCount = finding.affected_count || 1;
                                    const instances = finding.instances_sample || [];
                                    const mostlyStatic = finding.mostly_static || false;
                                    
                                    // Tolerant logic: use defaults when missing
                                    const method = finding.http_method || "GET";
                                    const url = finding.url || finding.path || null;
                                    const param = finding.parameter;

                                    // Show grouped finding if affected_count > 1
                                    if (affectedCount > 1) {
                                      return (
                                        <>
                                          <div className="text-xs font-medium mb-2" style={{ color: 'var(--fg)' }}>
                                            This issue affects <strong>{affectedCount}</strong> URL{affectedCount !== 1 ? 's' : ''}
                                            {mostlyStatic && (
                                              <span className="ml-2 px-2 py-0.5 text-[10px] rounded border" style={{ background: 'var(--surface)', color: 'var(--muted)', borderColor: 'var(--border)' }}>
                                                Mostly static assets
                                              </span>
                                            )}
                                          </div>
                                          {(instances.length > 0 || affectedCount > 1) && (
                                            <div className="mt-2">
                                              <button
                                                onClick={() => {
                                                  if (!finding.id) return;
                                                  const findingId = finding.id;
                                                  const isExpanded = expandedDetails.includes(findingId);
                                                  
                                                  if (!isExpanded) {
                                                    // Expanding - update state first
                                                    setExpandedDetails(prev => prev.includes(findingId) ? prev : [...prev, findingId]);
                                                    
                                                    // Check if we need to load instances
                                                    const hasAllInstances = expandedFindingInstances[findingId] && expandedFindingInstances[findingId].length >= affectedCount;
                                                    const isCurrentlyLoading = loadingInstances[findingId] || loadingRef.current[findingId];
                                                    
                                                    // Only load if we don't have all instances and we're not already loading
                                                    if (affectedCount > instances.length && !hasAllInstances && !isCurrentlyLoading) {
                                                      // Mark as loading immediately to prevent duplicate calls
                                                      loadingRef.current[findingId] = true;
                                                      setLoadingInstances(prev => ({ ...prev, [findingId]: true }));
                                                      setShowAllUrls(prev => ({ ...prev, [findingId]: true }));
                                                      
                                                      // Load instances asynchronously
                                                      loadAllInstances(findingId, true).finally(() => {
                                                        loadingRef.current[findingId] = false;
                                                      });
                                                    }
                                                  } else {
                                                    // Collapsing
                                                    setExpandedDetails(prev => prev.filter(id => id !== findingId));
                                                    setShowAllUrls(prev => {
                                                      const updated = { ...prev };
                                                      delete updated[findingId];
                                                      return updated;
                                                    });
                                                  }
                                                }}
                                                className="text-xs cursor-pointer font-medium mb-2 flex items-center gap-1 hover:opacity-80 transition-opacity"
                                                style={{ color: 'var(--brand)' }}
                                              >
                                                <svg 
                                                  className={`w-3 h-3 transition-transform ${expandedDetails.includes(finding.id || '') ? 'rotate-180' : ''}`}
                                                  fill="none" 
                                                  stroke="currentColor" 
                                                  viewBox="0 0 24 24"
                                                >
                                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                </svg>
                                                {(() => {
                                                  const findingId = finding.id;
                                                  const loadedInstances = findingId ? expandedFindingInstances[findingId] : null;
                                                  const displayedCount = (loadedInstances && loadedInstances.length > 0)
                                                    ? loadedInstances.length
                                                    : instances.length;
                                                  return `View affected URLs (${displayedCount} shown${affectedCount > displayedCount ? ` of ${affectedCount}` : ''})`;
                                                })()}
                                              </button>
                                              {expandedDetails.includes(finding.id || '') && (
                                                <div className="mt-2">
                                                  {(() => {
                                                    const findingId = finding.id;
                                                    const isLoading = findingId && loadingInstances[findingId];
                                                    const loadedInstances = findingId ? expandedFindingInstances[findingId] : null;
                                                    // Check if we have all instances by comparing with affected_count
                                                    const hasAllInstances = loadedInstances && loadedInstances.length >= affectedCount;
                                                    const showingAll = findingId && showAllUrls[findingId];
                                                    
                                                    // Use all instances if they're loaded, otherwise use sample
                                                    // The key is: if we have loaded instances, show them (regardless of showingAll flag)
                                                    const allInstances = (loadedInstances && loadedInstances.length > 0)
                                                      ? loadedInstances 
                                                      : instances;
                                                    
                                                    // Debug logging
                                                    if (findingId && affectedCount > 1) {
                                                      console.log('🔍 Rendering instances for', findingId, {
                                                        hasAllInstances,
                                                        loadedCount: loadedInstances?.length || 0,
                                                        sampleCount: instances.length,
                                                        allInstancesCount: allInstances.length,
                                                        affectedCount,
                                                        isLoading,
                                                        expandedFindingInstances: Object.keys(expandedFindingInstances),
                                                        findingInExpanded: findingId in expandedFindingInstances
                                                      });
                                                    }
                                                    
                                                    // Filter by search term if present
                                                    const searchTerm = findingId ? (urlSearchTerm[findingId] || '').toLowerCase() : '';
                                                    const filteredInstances = searchTerm
                                                      ? allInstances.filter(inst => {
                                                          const url = (inst.url || inst.path || '').toLowerCase();
                                                          const param = (inst.parameter || '').toLowerCase();
                                                          return url.includes(searchTerm) || param.includes(searchTerm);
                                                        })
                                                      : allInstances;
                                                    
                                                    // Copy all URLs function
                                                    const copyAllUrls = () => {
                                                      const urlsToCopy = allInstances
                                                        .map(inst => inst.url || inst.path || '')
                                                        .filter(Boolean)
                                                        .join('\n');
                                                      if (urlsToCopy) {
                                                        navigator.clipboard.writeText(urlsToCopy).then(() => {
                                                          alert(`Copied ${allInstances.length} URL${allInstances.length !== 1 ? 's' : ''} to clipboard`);
                                                        }).catch(err => {
                                                          console.error('Failed to copy:', err);
                                                          alert('Failed to copy URLs to clipboard');
                                                        });
                                                      }
                                                    };
                                                    
                                                    return (
                                                      <>
                                                        {/* Action buttons */}
                                                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                                                          {!hasAllInstances && affectedCount > allInstances.length && (
                                                            <button
                                                              onClick={() => {
                                                                if (findingId) {
                                                                  setShowAllUrls(prev => ({ ...prev, [findingId]: true }));
                                                                  if (!hasAllInstances && !isLoading) {
                                                                    loadAllInstances(findingId, true);
                                                                  }
                                                                }
                                                              }}
                                                              disabled={isLoading}
                                                              className="text-xs px-2 py-1 rounded border hover:opacity-80 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                                                              style={{ 
                                                                background: 'var(--surface)', 
                                                                borderColor: 'var(--border)',
                                                                color: 'var(--fg)'
                                                              }}
                                                            >
                                                              {isLoading ? 'Loading...' : 'Show all URLs'}
                                                            </button>
                                                          )}
                                                          {hasAllInstances && allInstances.length > 0 && (
                                                            <button
                                                              onClick={copyAllUrls}
                                                              className="text-xs px-2 py-1 rounded border hover:opacity-80 transition-opacity"
                                                              style={{ 
                                                                background: 'var(--surface)', 
                                                                borderColor: 'var(--border)',
                                                                color: 'var(--fg)'
                                                              }}
                                                            >
                                                              Copy all ({allInstances.length})
                                                            </button>
                                                          )}
                                                          {hasAllInstances && (
                                                            <input
                                                              type="text"
                                                              placeholder="Search URLs..."
                                                              value={findingId ? (urlSearchTerm[findingId] || '') : ''}
                                                              onChange={(e) => {
                                                                if (findingId) {
                                                                  setUrlSearchTerm(prev => ({ ...prev, [findingId]: e.target.value }));
                                                                }
                                                              }}
                                                              className="text-xs px-2 py-1 rounded border flex-1 min-w-[150px]"
                                                              style={{ 
                                                                background: 'var(--surface)', 
                                                                borderColor: 'var(--border)',
                                                                color: 'var(--fg)'
                                                              }}
                                                            />
                                                          )}
                                                        </div>
                                                        
                                                        {/* Status message */}
                                                        <div className="text-xs mb-2 font-medium" style={{ color: 'var(--muted)' }}>
                                                          {isLoading && !hasAllInstances
                                                            ? `Loading all URLs... (${allInstances.length} shown so far${allInstances.length < affectedCount ? ` of ${affectedCount}` : ''})`
                                                            : hasAllInstances 
                                                            ? `Showing all ${allInstances.length} of ${affectedCount} URL${affectedCount !== 1 ? 's' : ''}${searchTerm ? ` (${filteredInstances.length} filtered)` : ''}`
                                                            : `Showing ${allInstances.length} of ${affectedCount} URL${affectedCount !== 1 ? 's' : ''}${searchTerm ? ` (${filteredInstances.length} filtered)` : ''}`
                                                          }
                                                        </div>
                                                        
                                                        {/* Loading state - show only if we have no instances yet */}
                                                        {isLoading && filteredInstances.length === 0 && (
                                                          <div className="text-xs text-center py-4" style={{ color: 'var(--muted)' }}>
                                                            Loading all URLs...
                                                          </div>
                                                        )}
                                                        
                                                        {/* Empty state */}
                                                        {!isLoading && filteredInstances.length === 0 && allInstances.length === 0 && (
                                                          <div className="text-xs text-center py-4" style={{ color: 'var(--muted)' }}>
                                                            {searchTerm 
                                                              ? 'No URLs match your search'
                                                              : hasAllInstances && allInstances.length === 0
                                                              ? `No URLs available in database. This finding affects ${affectedCount} URL${affectedCount !== 1 ? 's' : ''} but instance data was not fully stored.`
                                                              : 'No URLs available'
                                                            }
                                                          </div>
                                                        )}
                                                        
                                                        {/* URL list with virtualization for large lists */}
                                                        {/* Show instances even while loading if we have any */}
                                                        {filteredInstances.length > 0 && (
                                                          <div 
                                                            className="space-y-1 overflow-y-auto"
                                                            style={{ 
                                                              maxHeight: filteredInstances.length > 50 ? '400px' : '300px',
                                                              // Basic virtualization: only render visible items for very large lists
                                                              // For lists > 200, we'll use a simpler approach
                                                            }}
                                                          >
                                                            {filteredInstances.length > 200 ? (
                                                              // For very large lists, show first 100 + indicator
                                                              <>
                                                                {filteredInstances.slice(0, 100).map((inst, instIdx) => (
                                                                  <div key={instIdx} className="text-xs font-mono p-2 rounded border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                                                                    <div className="break-all" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>
                                                                      <span className="font-semibold">{inst.http_method || method}</span>{' '}
                                                                      <span>{inst.url || inst.path || 'N/A'}</span>
                                                                    </div>
                                                                    {inst.parameter && (
                                                                      <div className="text-[10px] mt-1" style={{ color: 'var(--muted)' }}>
                                                                        Parameter: <span className="font-mono">{inst.parameter}</span>
                                                                      </div>
                                                                    )}
                                                                    {inst.is_static_asset && (
                                                                      <span className="text-[10px] px-1 py-0.5 rounded border ml-1" style={{ background: 'var(--surface-2)', color: 'var(--muted)', borderColor: 'var(--border)' }}>
                                                                        Static
                                                                      </span>
                                                                    )}
                                                                  </div>
                                                                ))}
                                                                <div className="text-xs text-center py-2 italic" style={{ color: 'var(--muted)' }}>
                                                                  ... and {filteredInstances.length - 100} more URL{filteredInstances.length - 100 !== 1 ? 's' : ''} (showing first 100, use search to find specific URLs)
                                                                </div>
                                                              </>
                                                            ) : (
                                                              // For smaller lists, show all
                                                              filteredInstances.map((inst, instIdx) => (
                                                                <div key={instIdx} className="text-xs font-mono p-2 rounded border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                                                                  <div className="break-all" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>
                                                                    <span className="font-semibold">{inst.http_method || method}</span>{' '}
                                                                    <span>{inst.url || inst.path || 'N/A'}</span>
                                                                  </div>
                                                                  {inst.parameter && (
                                                                    <div className="text-[10px] mt-1" style={{ color: 'var(--muted)' }}>
                                                                      Parameter: <span className="font-mono">{inst.parameter}</span>
                                                                    </div>
                                                                  )}
                                                                  {inst.is_static_asset && (
                                                                    <span className="text-[10px] px-1 py-0.5 rounded border ml-1" style={{ background: 'var(--surface-2)', color: 'var(--muted)', borderColor: 'var(--border)' }}>
                                                                      Static
                                                                    </span>
                                                                  )}
                                                                </div>
                                                              ))
                                                            )}
                                                          </div>
                                                        )}
                                                      </>
                                                    );
                                                  })()}
                                                </div>
                                              )}
                                            </div>
                                          )}
                                          {instances.length === 0 && url && (
                                            <div className="text-xs font-mono break-all overflow-wrap-anywhere" style={{ color: 'var(--fg)', wordBreak: 'break-all', overflowWrap: 'anywhere', maxWidth: '100%' }}>
                                              <span className="font-semibold">{method}</span>{' '}
                                              <span className="break-all" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>{url}</span>
                                            </div>
                                          )}
                                        </>
                                      );
                                    }

                                    // Single finding (legacy behavior)
                                    if (!url) {
                                      return (
                                        <p className="text-xs italic" style={{ color: 'var(--muted)' }}>
                                          Location information not available
                                        </p>
                                      );
                                    }

                                    return (
                                      <>
                                        <div className="text-xs font-mono break-all overflow-wrap-anywhere p-2 rounded" style={{ background: 'var(--bg)', color: 'var(--fg)', wordBreak: 'break-all', overflowWrap: 'anywhere', maxWidth: '100%' }}>
                                          <span className="font-semibold">{method}</span>{' '}
                                          <span className="break-all" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>{url}</span>
                                        </div>
                                        {param && (
                                          <div className="text-xs break-words mt-1" style={{ color: 'var(--muted)', wordBreak: 'break-word', overflowWrap: 'break-word' }}>
                                            Parameter: <span className="font-mono font-medium break-all" style={{ color: 'var(--fg)', wordBreak: 'break-all', overflowWrap: 'anywhere' }}>{param}</span>
                                          </div>
                                        )}
                                      </>
                                    );
                                  })()}
                                </div>

                                {/* 2. What we found - ALWAYS SHOW */}
                                <div className="space-y-1">
                                  <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                    What we found
                                  </div>
                                  {finding.description ? (
                                    <p className="text-xs leading-relaxed break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                      {finding.description}
                                    </p>
                                  ) : (
                                    <p className="text-xs italic" style={{ color: 'var(--muted)' }}>
                                      No description available
                                    </p>
                                  )}
                                </div>

                                {/* 3. Why it matters - ALWAYS SHOW with smart fallback */}
                                <div className="space-y-1">
                                  <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                    Why it matters
                                  </div>
                                  {(() => {
                                    // Prefer backend impact_summary
                                    if (finding.impact_summary) {
                                      return (
                                        <p className="text-xs leading-relaxed break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                          {finding.impact_summary}
                                        </p>
                                      );
                                    }

                                    // Derive from vuln_type if available
                                    const vulnType = finding.vuln_type?.toLowerCase() || '';
                                    if (vulnType.includes('xss')) {
                                      return (
                                        <p className="text-xs leading-relaxed break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                          An attacker could run JavaScript in the user's browser, steal sessions, or act as the logged-in user.
                                        </p>
                                      );
                                    }
                                    if (vulnType.includes('sqli') || vulnType.includes('sql')) {
                                      return (
                                        <p className="text-xs leading-relaxed break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                          An attacker could read or modify data in your database and potentially gain full control of the application.
                                        </p>
                                      );
                                    }
                                    if (vulnType.includes('open') && vulnType.includes('port')) {
                                      return (
                                        <p className="text-xs leading-relaxed break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                          Exposed services can be attacked or abused if they are misconfigured, outdated, or unnecessary.
                                        </p>
                                      );
                                    }

                                    // Generic fallback
                                    return (
                                      <p className="text-xs italic break-words" style={{ color: 'var(--muted)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                        This issue could pose a security risk to your application.
                                      </p>
                                    );
                                  })()}
                                </div>

                                {/* 4. How to fix it - ALWAYS SHOW, prefer backend remediation */}
                                <div className="space-y-1">
                                  <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                    How to fix it
                                  </div>
                                  {(() => {
                                    // Prefer backend remediation fields
                                    const hasRemediation = finding.remediation_summary || finding.remediation_steps || (finding as any).default_remediation_steps || finding.recommendation;

                                    if (hasRemediation) {
                                      return (
                                        <>
                                          {finding.remediation_summary && (
                                            <p className="text-xs mb-1 break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                              {finding.remediation_summary}
                                            </p>
                                          )}
                                          {(finding.remediation_steps || (finding as any).default_remediation_steps) && (
                                            <ul className="text-xs list-disc list-inside space-y-0.5 break-words" style={{ color: 'var(--muted)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                              {(finding.remediation_steps || (finding as any).default_remediation_steps || '')
                                                .split('\n')
                                                .filter(s => s.trim())
                                                .map((step, idx) => (
                                                  <li key={idx} className="break-words" style={{ wordBreak: 'break-word', overflowWrap: 'break-word' }}>{step.trim()}</li>
                                                ))}
                                            </ul>
                                          )}
                                          {finding.recommendation && !finding.remediation_summary && !finding.remediation_steps && (
                                            <p className="text-xs italic break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>{finding.recommendation}</p>
                                          )}
                                        </>
                                      );
                                    }

                                    // Only show fallback if truly no remediation available
                                    return (
                                      <p className="text-xs italic break-words" style={{ color: 'var(--muted)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>
                                        Remediation guidance for this specific issue is not available yet. Review the technical details or consult your security team.
                                      </p>
                                    );
                                  })()}
                                </div>
                              </div>

                              {/* CVE/CWE/CVSS badges */}
                              {(finding.cve_id || finding.cwe_id || (finding.cvss_score !== null && finding.cvss_score !== undefined)) && (
                                <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                                  {finding.cve_id && (
                                    <Link
                                      href={`/dashboard/cve/${encodeURIComponent(finding.cve_id)}`}
                                      className="px-2 py-1 text-xs font-mono rounded border hover:opacity-80 transition-opacity cursor-pointer"
                                      style={{ background: 'var(--surface)', color: 'var(--brand)', borderColor: 'var(--border)' }}
                                      title={`View details for ${finding.cve_id}`}
                                    >
                                      CVE: {finding.cve_id}
                                    </Link>
                                  )}
                                  {finding.cwe_id && (
                                    <button
                                      type="button"
                                      onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        setSelectedCweId(finding.cwe_id || null);
                                        setCweDrawerOpen(true);
                                      }}
                                      className="px-2 py-1 text-xs font-mono rounded border transition-colors cursor-pointer"
                                      style={{ background: 'var(--surface)', color: 'var(--brand)', borderColor: 'var(--border)' }}
                                      onMouseEnter={(e) => {
                                        e.currentTarget.style.background = 'var(--surface-2)';
                                      }}
                                      onMouseLeave={(e) => {
                                        e.currentTarget.style.background = 'var(--surface)';
                                      }}
                                      aria-label={`View CWE-${String(finding.cwe_id).replace(/^CWE-/i, '')} details`}
                                    >
                                      CWE: {finding.cwe_id}
                                    </button>
                                  )}
                                  {finding.cvss_score !== null && finding.cvss_score !== undefined && typeof finding.cvss_score === 'number' && (
                                    <span className="px-2 py-1 text-xs rounded border" style={{ background: 'var(--surface)', color: 'var(--fg)', borderColor: 'var(--border)' }}>
                                      CVSS: {finding.cvss_score.toFixed(1)}
                                    </span>
                                  )}
                                </div>
                              )}

                              {/* Lifecycle info */}
                              {(finding.first_seen_at || finding.last_seen_at || finding.found_count) && (
                                <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                                  <p className="text-xs font-medium mb-1" style={{ color: 'var(--fg)' }}>Lifecycle</p>
                                  <div className="text-xs space-y-1" style={{ color: 'var(--muted)' }}>
                                    {finding.first_seen_at && (
                                      <p>First seen: {formatDateTime(finding.first_seen_at)}</p>
                                    )}
                                    {finding.last_seen_at && (
                                      <p>Last seen: {formatDateTime(finding.last_seen_at)}</p>
                                    )}
                                    {finding.found_count && finding.found_count > 1 && (
                                      <p>Seen in {finding.found_count} scans</p>
                                    )}
                                  </div>
                                </div>
                              )}

                              {/* Action Buttons */}
                              <div className="flex items-center gap-2 mt-4 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                                {(finding.remediation_summary || finding.remediation_steps || finding.recommendation) && (
                                  <button
                                    className="px-3 py-1.5 text-xs font-medium rounded border transition hover:opacity-80"
                                    style={{ background: 'var(--brand)', color: '#ffffff', borderColor: 'var(--brand)' }}
                                    onClick={() => {
                                      // Scroll to remediation section or open drawer
                                      const details = document.querySelector(`[data-finding-id="${finding.id || findingKey}"] details`);
                                      if (details) {
                                        (details as HTMLDetailsElement).open = true;
                                        details.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                                      }
                                    }}
                                  >
                                    View Remediation
                                  </button>
                                )}
                                <details>
                                  <summary className="px-3 py-1.5 text-xs font-medium rounded border cursor-pointer list-none transition hover:opacity-80" style={{ background: 'transparent', color: 'var(--muted)', borderColor: 'var(--border)' }}>
                                    <span className="flex items-center gap-1">
                                      Technical details
                                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                      </svg>
                                    </span>
                                  </summary>
                                  <div className="mt-2 p-3 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                                    <div className="space-y-2 text-xs" style={{ color: 'var(--muted)' }}>
                                      {finding.tool_name && (
                                        <div>
                                          <span className="font-medium" style={{ color: 'var(--fg)' }}>Detected by: </span>
                                          <span className="font-mono">{finding.tool_name}</span>
                                        </div>
                                      )}
                                      {finding.categories && finding.categories.length > 0 && (
                                        <div>
                                          <span className="font-medium" style={{ color: 'var(--fg)' }}>Categories: </span>
                                          <span>{finding.categories.map(cat => formatCategory(cat)).join(', ')}</span>
                                        </div>
                                      )}
                                      {finding.path && (
                                        <div>
                                          <span className="font-medium" style={{ color: 'var(--fg)' }}>Path: </span>
                                          <span className="font-mono">{finding.path}</span>
                                          {finding.line_number && <span> (line {finding.line_number})</span>}
                                        </div>
                                      )}
                                      {finding.url && (
                                        <div>
                                          <span className="font-medium" style={{ color: 'var(--fg)' }}>URL: </span>
                                          <span className="font-mono break-all">{finding.url}</span>
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </details>
                              </div>

                              {/* Technical details (collapsible) - includes tool name - hidden, used for View Remediation button */}
                              <details data-finding-id={finding.id || findingKey} className="mt-3 pt-3 border-t hidden" style={{ borderColor: 'var(--border)' }}>
                                <summary className="text-xs cursor-pointer font-medium mb-2" style={{ color: 'var(--brand)' }}>
                                  Technical details
                                </summary>
                                <div className="mt-2 space-y-2 text-xs" style={{ color: 'var(--muted)' }}>
                                  {finding.tool_name && (
                                    <div>
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>Detected by: </span>
                                      <span className="font-mono">{finding.tool_name}</span>
                                    </div>
                                  )}
                                  {finding.categories && finding.categories.length > 0 && (
                                    <div>
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>Categories: </span>
                                      <span>{finding.categories.map(cat => formatCategory(cat)).join(', ')}</span>
                                    </div>
                                  )}
                                  {finding.path && (
                                    <div>
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>Path: </span>
                                      <span className="font-mono">{finding.path}</span>
                                      {finding.line_number && <span> (line {finding.line_number})</span>}
                                    </div>
                                  )}
                                  {finding.url && (
                                    <div>
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>URL: </span>
                                      <span className="font-mono break-all">{finding.url}</span>
                                    </div>
                                  )}
                                </div>
                              </details>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right column - Sidebar */}
                <div className="space-y-6">
                  {/* Scan Pipeline */}
                  <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--fg)' }}>SCAN PIPELINE</h2>
                      {(scan.status === 'running' || scan.status === 'queued' || scan.status === 'pending') && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full border" style={{ background: '#10b981', color: '#ffffff', borderColor: '#10b981' }}>
                          LIVE
                        </span>
                      )}
                    </div>
                    {(scan.status === 'running' || scan.status === 'queued' || scan.status === 'pending') ? (
                      <PhaseTimeline
                        toolStates={toolStates}
                        scanStatus={scan.status}
                        scanLevel={scan.scan_level}
                        isConnected={isConnected}
                      />
                    ) : (
                      <div className="text-sm" style={{ color: 'var(--muted)' }}>
                        Scan completed
                      </div>
                    )}
                  </div>

                  {/* Surface Stats */}
                  <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                    <div className="flex items-center gap-2 mb-4">
                      <svg className="w-4 h-4" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                      </svg>
                      <h2 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--fg)' }}>SURFACE STATS</h2>
                    </div>
                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span style={{ color: 'var(--muted)' }}>OPEN PORTS</span>
                        <span className="font-medium" style={{ color: 'var(--fg)' }}>{openPortsCount}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span style={{ color: 'var(--muted)' }}>TLS STATUS</span>
                        <span className="font-medium" style={{ color: hasTlsIssues ? '#f59e0b' : '#10b981' }}>
                          {hasTlsIssues ? 'ISSUES DETECTED' : 'SECURE'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Scan Details */}
                  <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                    <h2 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: 'var(--fg)' }}>SCAN DETAILS</h2>
                    <div className="space-y-3 text-sm">
                      <div>
                        <p className="mb-1" style={{ color: 'var(--muted)' }}>Created At:</p>
                        <p style={{ color: 'var(--fg)' }}>{formatDateTime(scan.created_at)}</p>
                      </div>
                      {scan.started_at && (
                        <div>
                          <p className="mb-1" style={{ color: 'var(--muted)' }}>Started At:</p>
                          <p style={{ color: 'var(--fg)' }}>{formatDateTime(scan.started_at)}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Legacy progress fallback - Show only if WebSocket not connected */}
                  {!isConnected && (scan.status === 'running' || scan.status === 'queued' || scan.status === 'pending') && (() => {
                    // Calculate timeout remaining (max timeout - elapsed time)
                    const getTimeoutRemaining = () => {
                      if (!scan.started_at) {
                        return null;
                      }

                      // Max timeout per scan level (in seconds)
                      const maxTimeouts: Record<string, number> = {
                        'basic': 600,    // 10 minutes
                        'pro': 3600,     // 60 minutes
                        'advanced': 5400, // 90 minutes
                      };

                      const maxTimeout = maxTimeouts[scan.scan_level?.toLowerCase() || 'pro'] || 3600;
                      const startedAt = new Date(scan.started_at).getTime();
                      const now = currentTime; // Use currentTime state for real-time updates
                      const elapsedSeconds = (now - startedAt) / 1000;
                      const remainingSeconds = Math.max(0, maxTimeout - elapsedSeconds);

                      if (remainingSeconds <= 0) {
                        return 'Timeout reached';
                      }

                      const minutes = Math.floor(remainingSeconds / 60);
                      const hours = Math.floor(minutes / 60);
                      const remainingMinutes = minutes % 60;

                      if (hours > 0) {
                        return `${hours}h ${remainingMinutes}m`;
                      }
                      return `${minutes}m`;
                    };

                    const progressPct = scan.progress_pct ?? 0;
                    const timeRemaining = getTimeoutRemaining();

                    return (
                      <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                        <div className="flex items-center justify-between mb-4">
                          <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Scan Progress</h2>
                          {timeRemaining && (
                            <div className="flex items-center gap-2 px-3 py-1 rounded-full" style={{ background: 'var(--surface-2)' }}>
                              <svg className="w-4 h-4 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--muted)' }}>
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                                {timeRemaining} left
                              </span>
                            </div>
                          )}
                        </div>

                        {/* Progress Bar */}
                        {scan.progress_pct !== null && scan.progress_pct !== undefined && scan.total_tools !== null && scan.total_tools !== undefined && (
                          <>
                            <div className="mb-3 relative">
                              <div className="w-full h-4 rounded-full overflow-hidden relative" style={{ background: 'var(--surface-2)' }}>
                                {/* Animated progress bar with shimmer effect */}
                                <div
                                  className="h-full relative transition-all duration-500 ease-out"
                                  style={{
                                    width: `${progressPct}%`,
                                    background: progressPct === 100
                                      ? 'linear-gradient(90deg, #10b981 0%, #059669 50%, #10b981 100%)'
                                      : 'linear-gradient(90deg, #3b82f6 0%, #2563eb 50%, #3b82f6 100%)',
                                    backgroundSize: '200% 100%',
                                    animation: progressPct < 100 ? 'shimmer 2s infinite' : 'none',
                                  }}
                                >
                                  {/* Shimmer overlay */}
                                  {progressPct < 100 && (
                                    <div
                                      className="absolute inset-0 opacity-30"
                                      style={{
                                        background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                                        animation: 'shimmer-slide 2s infinite',
                                      }}
                                    />
                                  )}
                                </div>
                                {/* Pulse effect on the edge */}
                                {progressPct < 100 && progressPct > 0 && (
                                  <div
                                    className="absolute top-0 h-full w-1 rounded-full"
                                    style={{
                                      left: `${progressPct}%`,
                                      background: 'rgba(59, 130, 246, 0.8)',
                                      boxShadow: '0 0 8px rgba(59, 130, 246, 0.6)',
                                      animation: 'pulse-edge 1.5s infinite',
                                      transform: 'translateX(-50%)',
                                    }}
                                  />
                                )}
                              </div>
                              {/* Progress percentage label */}
                              <div className="absolute top-0 right-0 text-xs font-medium mt-1" style={{ color: 'var(--muted)' }}>
                                {Math.round(progressPct)}%
                              </div>
                            </div>
                            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
                              {(() => {
                                const total = scan.total_tools ?? 0;
                                const completed = scan.completed_tools ?? 0;
                                const running = (scan.tool_statuses || []).filter(t => t.status === 'running').length;
                                const queued = (scan.tool_statuses || []).filter(t => t.status === 'pending').length;
                                const parts = [`${completed} / ${total} checks completed`];
                                if (running > 0) parts.push(`${running} running`);
                                if (queued > 0) parts.push(`${queued} queued`);
                                return parts.join(' • ');
                              })()}
                            </p>
                          </>
                        )}

                        {/* Fallback if progress_pct not available */}
                        {(!scan.progress_pct && scan.progress_pct !== 0) && scan.tool_statuses && scan.tool_statuses.length > 0 && (() => {
                          const fallbackProgress = (scan.tool_statuses.filter(t => t.status === 'completed' || t.status === 'failed' || t.status === 'timed_out' || t.status === 'skipped').length / scan.tool_statuses.length) * 100;
                          const fallbackTimeRemaining = getTimeoutRemaining();

                          return (
                            <>
                              {fallbackTimeRemaining && (
                                <div className="flex items-center gap-2 px-3 py-1 rounded-full mb-4" style={{ background: 'var(--surface-2)' }}>
                                  <svg className="w-4 h-4 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--muted)' }}>
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                  <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                                    {fallbackTimeRemaining} left
                                  </span>
                                </div>
                              )}
                              <div className="mb-3 relative">
                                <div className="w-full h-4 rounded-full overflow-hidden relative" style={{ background: 'var(--surface-2)' }}>
                                  {/* Animated progress bar with shimmer effect */}
                                  <div
                                    className="h-full relative transition-all duration-500 ease-out"
                                    style={{
                                      width: `${fallbackProgress}%`,
                                      background: 'linear-gradient(90deg, #3b82f6 0%, #2563eb 50%, #3b82f6 100%)',
                                      backgroundSize: '200% 100%',
                                      animation: fallbackProgress < 100 ? 'shimmer 2s infinite' : 'none',
                                    }}
                                  >
                                    {/* Shimmer overlay */}
                                    {fallbackProgress < 100 && (
                                      <div
                                        className="absolute inset-0 opacity-30"
                                        style={{
                                          background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)',
                                          animation: 'shimmer-slide 2s infinite',
                                        }}
                                      />
                                    )}
                                  </div>
                                  {/* Pulse effect on the edge */}
                                  {fallbackProgress < 100 && fallbackProgress > 0 && (
                                    <div
                                      className="absolute top-0 h-full w-1 rounded-full"
                                      style={{
                                        left: `${fallbackProgress}%`,
                                        background: 'rgba(59, 130, 246, 0.8)',
                                        boxShadow: '0 0 8px rgba(59, 130, 246, 0.6)',
                                        animation: 'pulse-edge 1.5s infinite',
                                        transform: 'translateX(-50%)',
                                      }}
                                    />
                                  )}
                                </div>
                                {/* Progress percentage label */}
                                <div className="absolute top-0 right-0 text-xs font-medium mt-1" style={{ color: 'var(--muted)' }}>
                                  {Math.round(fallbackProgress)}%
                                </div>
                              </div>
                              <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
                                {scan.tool_statuses.filter(t => t.status === 'completed' || t.status === 'failed' || t.status === 'timed_out' || t.status === 'skipped').length} / {scan.tool_statuses.length} checks completed
                              </p>
                            </>
                          );
                        })()}

                        {/* Technical Details Toggle */}
                        {scan.tool_statuses && scan.tool_statuses.length > 0 && (
                          <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
                            <button
                              onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                              className="flex items-center justify-between w-full text-sm font-medium transition-colors"
                              style={{ color: 'var(--fg)' }}
                            >
                              <span>Show technical details</span>
                              <svg
                                className={`w-5 h-5 transition-transform ${showTechnicalDetails ? 'rotate-180' : ''}`}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            </button>

                            {/* Technical Details Panel */}
                            {showTechnicalDetails && (
                              <div className="mt-4 space-y-4">
                                {/* Per-tool status list */}
                                <div>
                                  <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Tool Execution Status</h3>
                                  <div className="space-y-2">
                                    {scan.tool_statuses.map((toolStatus) => {
                                      const statusIcon = toolStatus.status === 'completed' ? '✅' :
                                        toolStatus.status === 'running' ? '🟡' :
                                          toolStatus.status === 'failed' || toolStatus.status === 'timed_out' ? '❌' : '⬜';
                                      const statusLabel = toolStatus.status === 'completed' ? 'Completed' :
                                        toolStatus.status === 'running' ? 'Running' :
                                          toolStatus.status === 'failed' ? 'Failed' :
                                            toolStatus.status === 'timed_out' ? 'Timed Out' :
                                              toolStatus.status === 'skipped' ? 'Skipped' : 'Pending';
                                      const statusColor = toolStatus.status === 'completed' ? 'text-emerald-300' :
                                        toolStatus.status === 'running' ? 'text-blue-300' :
                                          toolStatus.status === 'failed' || toolStatus.status === 'timed_out' ? 'text-red-300' : 'text-slate-400';

                                      return (
                                        <div
                                          key={toolStatus.tool_name}
                                          className="flex items-start justify-between p-3 rounded-lg border"
                                          style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                                        >
                                          <div className="flex items-start gap-3 flex-1">
                                            <span className="text-lg mt-0.5">{statusIcon}</span>
                                            <div className="flex-1">
                                              <span className="font-medium text-sm block mb-1" style={{ color: 'var(--fg)' }}>
                                                {toolStatus.tool_name.charAt(0).toUpperCase() + toolStatus.tool_name.slice(1)}
                                              </span>
                                              {toolStatus.error_message && (
                                                <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                                                  {toolStatus.error_message}
                                                </p>
                                              )}
                                            </div>
                                          </div>
                                          <span className={`text-xs font-medium ${statusColor} ml-2`}>
                                            {statusLabel}
                                          </span>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>

                                {/* Tools Used list (moved from separate card) */}
                                {tools.length > 0 && (
                                  <div>
                                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Tools Used</h3>
                                    {toolsLoading ? (
                                      <div className="text-xs" style={{ color: 'var(--muted)' }}>Loading...</div>
                                    ) : toolsError ? (
                                      <div className="text-xs text-red-400">{toolsError}</div>
                                    ) : (
                                      <div className="space-y-2">
                                        {tools.map((tool) => {
                                          const isSuccess = tool.exit_code === 0 && !tool.timed_out;
                                          const isTimedOut = tool.timed_out;
                                          const toolName = tool.tool_name.charAt(0).toUpperCase() + tool.tool_name.slice(1);
                                          const runtime = tool.execution_time ? `${tool.execution_time.toFixed(1)}s` : 'N/A';
                                          const outputSizeKB = tool.output_size > 0 ? (tool.output_size / 1024).toFixed(1) : '0';

                                          return (
                                            <div
                                              key={tool.tool_name}
                                              className="flex items-center justify-between p-2 rounded border"
                                              style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                                            >
                                              <div className="flex items-center gap-2 flex-1">
                                                <span className="text-xs font-medium" style={{ color: 'var(--fg)' }}>
                                                  {toolName}
                                                </span>
                                                <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--muted)' }}>
                                                  <span className="font-mono">{runtime}</span>
                                                  {tool.output_size > 0 && (
                                                    <>
                                                      <span>•</span>
                                                      <span className="font-mono">{outputSizeKB} KB</span>
                                                    </>
                                                  )}
                                                </div>
                                              </div>
                                              <div className="flex items-center gap-2">
                                                {isTimedOut && (
                                                  <span className="text-xs text-amber-400">Timed out</span>
                                                )}
                                                {!isTimedOut && tool.error_message && (
                                                  <span className="text-xs text-red-400 truncate max-w-[150px]" title={tool.error_message}>
                                                    Error
                                                  </span>
                                                )}
                                                {isSuccess && !isTimedOut && !tool.error_message && (
                                                  <span className="text-xs text-emerald-400">Success</span>
                                                )}
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })()}


                  {/* Tools Executed card */}
                  <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Tools Executed</h2>
                    {toolsLoading ? (
                      <div className="text-sm" style={{ color: 'var(--muted)' }}>Loading tools...</div>
                    ) : toolsError ? (
                      <div className="text-sm text-red-400">{toolsError}</div>
                    ) : tools.length === 0 ? (
                      <div className="text-sm" style={{ color: 'var(--muted)' }}>No tool execution data available</div>
                    ) : (
                      <div className="space-y-2">
                        {tools.map((tool) => {
                          const isExpanded = expandedToolRows.has(tool.tool_name);
                          // Use tool_name_display from API if available, otherwise capitalize tool_name
                          const toolName = tool.tool_name_display || (tool.tool_name ? tool.tool_name.charAt(0).toUpperCase() + tool.tool_name.slice(1) : 'Unknown');

                          // Determine status
                          const status = tool.status || (tool.exit_code === 0 && !tool.timed_out ? 'completed' : tool.timed_out ? 'timed_out' : 'failed');
                          const statusLabel = status === 'completed' ? 'Success' :
                            status === 'running' ? 'Running' :
                              status === 'failed' ? 'Failed' :
                                status === 'timed_out' ? 'Timed Out' :
                                  status === 'skipped' ? 'Skipped' : 'Pending';
                          const statusColor = status === 'completed' ? 'text-emerald-400' :
                            status === 'running' ? 'text-blue-400' :
                              status === 'failed' || status === 'timed_out' ? 'text-red-400' :
                                status === 'skipped' ? 'text-amber-400' : 'text-slate-400';
                          const statusBg = status === 'completed' ? 'bg-emerald-500/20' :
                            status === 'running' ? 'bg-blue-500/20' :
                              status === 'failed' || status === 'timed_out' ? 'bg-red-500/20' :
                                status === 'skipped' ? 'bg-amber-500/20' : 'bg-slate-500/20';

                          // Format duration
                          const duration = tool.duration_ms ? `${(tool.duration_ms / 1000).toFixed(1)}s` :
                            tool.execution_time ? `${tool.execution_time.toFixed(1)}s` : 'N/A';

                          // Findings count display
                          // Collapsed row: simple count (API guarantees values, coalesces NULL to 0)
                          const createdCount = tool.created_findings_count ?? 0;
                          const parsedCount = tool.parsed_findings_count ?? 0;
                          const findingsDisplay = `${createdCount} finding${createdCount !== 1 ? 's' : ''}`;
                          // Expanded row: detailed breakdown
                          const findingsDetail = parsedCount !== createdCount
                            ? `parsed ${parsedCount} / created ${createdCount}`
                            : `${createdCount} finding${createdCount !== 1 ? 's' : ''}`;
                          const skipReason = tool.skip_reason;

                          return (
                            <div
                              key={tool.tool_name}
                              className="border rounded-lg overflow-hidden"
                              style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}
                            >
                              <div
                                className="flex items-center justify-between p-3 cursor-pointer hover:opacity-80 transition-opacity"
                                onClick={() => {
                                  const newExpanded = new Set(expandedToolRows);
                                  if (isExpanded) {
                                    newExpanded.delete(tool.tool_name);
                                  } else {
                                    newExpanded.add(tool.tool_name);
                                  }
                                  setExpandedToolRows(newExpanded);
                                }}
                              >
                                <div className="flex items-center gap-3 flex-1">
                                  <span className="font-medium text-sm" style={{ color: 'var(--fg)' }}>
                                    {toolName}
                                  </span>
                                  <span className={`text-xs px-2 py-0.5 rounded ${statusBg} ${statusColor} font-medium`}>
                                    {statusLabel}
                                  </span>
                                  {findingsDisplay && (
                                    <span className="text-xs" style={{ color: 'var(--muted)' }}>
                                      • {findingsDisplay}
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                                  <span>Duration: {duration}</span>
                                  {tool.exit_code !== null && (
                                    <span>Exit: {tool.exit_code}</span>
                                  )}
                                  {skipReason && (
                                    <span className="text-amber-400" title="Tool skipped / partial">
                                      Skip: {skipReason.replace(/_/g, ' ')}
                                    </span>
                                  )}
                                  <svg
                                    className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                  </svg>
                                </div>
                              </div>

                              {/* Expanded content: findings detail, stdout/stderr previews */}
                              {isExpanded && (
                                <div className="border-t p-3 space-y-3" style={{ borderColor: 'var(--border)' }}>
                                  {/* Findings detail: parsed/created breakdown */}
                                  <div>
                                    <div className="text-xs font-semibold mb-1" style={{ color: 'var(--muted)' }}>Findings</div>
                                    <div className="text-xs" style={{ color: 'var(--fg)' }}>
                                      {findingsDetail}
                                    </div>
                                  </div>
                                  {skipReason && (
                                    <div>
                                      <div className="text-xs font-semibold mb-1" style={{ color: 'var(--muted)' }}>Skip reason</div>
                                      <div className="text-xs text-amber-300">{skipReason.replace(/_/g, ' ')}</div>
                                    </div>
                                  )}
                                  {tool.stdout_preview && (
                                    <div>
                                      <div className="text-xs font-semibold mb-1" style={{ color: 'var(--muted)' }}>STDOUT Preview</div>
                                      <pre className="text-xs p-2 rounded overflow-x-auto" style={{ background: 'var(--surface)', color: 'var(--fg)' }}>
                                        {tool.stdout_preview}
                                      </pre>
                                    </div>
                                  )}
                                  {tool.stderr_preview && (
                                    <div>
                                      <div className="text-xs font-semibold mb-1" style={{ color: 'var(--muted)' }}>STDERR Preview</div>
                                      <pre className="text-xs p-2 rounded overflow-x-auto" style={{ background: 'var(--surface)', color: 'var(--fg)' }}>
                                        {tool.stderr_preview}
                                      </pre>
                                    </div>
                                  )}
                                  {!tool.stdout_preview && !tool.stderr_preview && (
                                    <div className="text-xs" style={{ color: 'var(--muted)' }}>No output preview available</div>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>


                  {/* Network & TLS Surface card */}
                  <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Network & TLS Surface</h2>
                    <dl className="space-y-3 text-sm">
                      <div className="flex items-center justify-between">
                        <dt style={{ color: 'var(--muted)' }}>Open ports</dt>
                        <dd className="font-medium" style={{ color: 'var(--fg)' }}>{openPortsCount}</dd>
                      </div>
                      <div className="flex items-center justify-between">
                        <dt style={{ color: 'var(--muted)' }}>TLS issues</dt>
                        <dd className={hasTlsIssues ? 'font-medium text-amber-300' : 'font-medium text-emerald-300'}>
                          {hasTlsIssues ? 'Detected' : 'None detected'}
                        </dd>
                      </div>
                    </dl>
                    {nmapFindings.length > 0 && (
                      <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
                        <p className="text-xs mb-2" style={{ color: 'var(--muted)' }}>Sample ports</p>
                        <ul className="space-y-1.5 text-xs" style={{ color: 'var(--fg)' }}>
                          {nmapFindings.slice(0, 3).map((f, idx) => {
                            // Generate stable key from finding properties
                            const portKey = f.id || `${f.title || 'port'}-${f.url || ''}-${idx}`;
                            return (
                              <li key={portKey} className="truncate">
                                • {f.title || 'Unknown port'}
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Stack fingerprint card */}
                  {scan.stack_info && (
                    <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                      <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Stack Fingerprint</h2>
                      <div className="space-y-3 text-sm">
                        {scan.stack_info.target_url && (
                          <div>
                            <p className="mb-1" style={{ color: 'var(--muted)' }}>Target URL</p>
                            <p className="break-all" style={{ color: 'var(--fg)' }}>{scan.stack_info.target_url}</p>
                          </div>
                        )}
                        {scan.stack_info.scan_level && (
                          <div>
                            <p className="mb-1" style={{ color: 'var(--muted)' }}>Scan Level</p>
                            <p style={{ color: 'var(--fg)' }}>{scan.stack_info.scan_level}</p>
                          </div>
                        )}
                        {scan.stack_info.http && (
                          <>
                            {scan.stack_info.http.status_code !== null && scan.stack_info.http.status_code !== undefined && (
                              <div>
                                <p className="mb-1" style={{ color: 'var(--muted)' }}>HTTP Status</p>
                                <p style={{ color: 'var(--fg)' }}>{scan.stack_info.http.status_code}</p>
                              </div>
                            )}
                            {scan.stack_info.http.headers && (
                              <div>
                                <p className="mb-2" style={{ color: 'var(--muted)' }}>HTTP Headers</p>
                                <div className="space-y-1">
                                  {scan.stack_info.http.headers.server && (
                                    <div className="text-xs">
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>Server:</span>{' '}
                                      <span style={{ color: 'var(--muted)' }}>{scan.stack_info.http.headers.server}</span>
                                    </div>
                                  )}
                                  {scan.stack_info.http.headers.content_type && (
                                    <div className="text-xs">
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>Content-Type:</span>{' '}
                                      <span style={{ color: 'var(--muted)' }}>{scan.stack_info.http.headers.content_type}</span>
                                    </div>
                                  )}
                                  {scan.stack_info.http.headers.x_powered_by && (
                                    <div className="text-xs">
                                      <span className="font-medium" style={{ color: 'var(--fg)' }}>X-Powered-By:</span>{' '}
                                      <span style={{ color: 'var(--muted)' }}>{scan.stack_info.http.headers.x_powered_by}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Error card - Keep in sidebar for reference, but main error is shown at top */}
                  {scan.error_message && (
                    <div className="rounded-xl border border-red-500/50 bg-red-900/20 p-4">
                      <div className="font-semibold mb-1 text-xs text-red-300">Error Details</div>
                      <pre className="whitespace-pre-wrap text-xs text-red-200">{scan.error_message}</pre>
                    </div>
                  )}

                  {/* Remediation Overview */}
                  {scan.summary?.remediation_overview && (
                    <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                      <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Remediation Overview</h2>
                      <p className="text-sm leading-relaxed" style={{ color: 'var(--fg)' }}>
                        {scan.summary.remediation_overview}
                      </p>
                    </div>
                  )}
                </div>
                </div>
              </div>
            )}

            {activeTab === 'findings' && (
              <div className="space-y-6">
                {/* Findings card - Full detailed view */}
                <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
                      Findings
                      {findingsTotal > 0 && (
                        <span className="ml-2 text-sm font-normal" style={{ color: 'var(--muted)' }}>
                          ({findingsTotal})
                        </span>
                      )}
                    </h2>
                    {/* Tool filter dropdown */}
                    {(availableTools.length > 0 || findingsTotal > 0) && (
                      <select
                        value={selectedToolFilter}
                        onChange={(e) => {
                          setSelectedToolFilter(e.target.value);
                          setFindingsPage(0);
                        }}
                        className="px-3 py-1.5 text-sm rounded border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--fg)' }}
                      >
                        <option value="all">All Tools</option>
                        {(availableTools.length > 0 ? availableTools : Array.from(new Set(findings.map(f => f.tool_name).filter(Boolean))).sort()).map(toolName => (
                          <option key={toolName} value={toolName}>{toolName}</option>
                        ))}
                      </select>
                    )}
                  </div>
                  {findingsTotal > findingsLimit && (
                    <div className="flex items-center justify-between mb-4 text-sm" style={{ color: 'var(--muted)' }}>
                      <span>
                        Showing {findingsPage * findingsLimit + 1} - {Math.min((findingsPage + 1) * findingsLimit, findingsTotal)} of {findingsTotal} findings
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setFindingsPage(prev => Math.max(0, prev - 1))}
                          disabled={findingsPage === 0 || findingsLoading}
                          className="px-3 py-1 rounded border transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{
                            background: 'var(--surface-2)',
                            borderColor: 'var(--border)',
                            color: findingsPage === 0 ? 'var(--muted)' : 'var(--fg)'
                          }}
                        >
                          Previous
                        </button>
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>
                          Page {findingsPage + 1} of {Math.ceil(findingsTotal / findingsLimit)}
                        </span>
                        <button
                          onClick={() => setFindingsPage(prev => prev + 1)}
                          disabled={findingsPage >= Math.ceil(findingsTotal / findingsLimit) - 1 || findingsLoading}
                          className="px-3 py-1 rounded border transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{
                            background: 'var(--surface-2)',
                            borderColor: 'var(--border)',
                            color: findingsPage >= Math.ceil(findingsTotal / findingsLimit) - 1 ? 'var(--muted)' : 'var(--fg)'
                          }}
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                  {findingsLoading ? (
                    <div className="text-center py-8">
                      <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                      <p className="mt-4 text-sm" style={{ color: 'var(--muted)' }}>Loading findings...</p>
                    </div>
                  ) : findingsError ? (
                    <div className="text-sm text-red-400 py-4">{findingsError}</div>
                  ) : findings.length === 0 ? (
                    <div className="text-center py-8">
                      <p className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>No findings detected</p>
                      <p className="text-xs" style={{ color: 'var(--muted)' }}>
                        {scan?.status === 'running' || scan?.status === 'queued'
                          ? 'Findings will appear here once the scan completes.'
                          : 'No security vulnerabilities or issues were detected during this scan.'}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {findings.filter(f => showInfoFindings || f.severity?.toLowerCase() !== 'info').map((finding, idx) => {
                        const findingKey = finding.id || `${finding.title || 'finding'}-${finding.url || ''}-${idx}`;
                        return (
                          <div key={findingKey} className="border rounded-lg p-4" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                            <div className="flex items-start justify-between gap-2 mb-3">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 flex-wrap mb-2">
                                  <SeverityBadge severity={finding.severity || 'info'} />
                                  {finding.status && <StatusBadge status={finding.status} />}
                                </div>
                                <h4 className="font-semibold text-sm" style={{ color: 'var(--fg)' }}>{finding.title}</h4>
                              </div>
                            </div>
                            {finding.description && (
                              <p className="text-sm mb-2" style={{ color: 'var(--muted)' }}>{finding.description}</p>
                            )}
                            {finding.recommendation && (
                              <div className="mt-2 pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
                                <p className="text-xs font-medium mb-1" style={{ color: 'var(--fg)' }}>Recommendation:</p>
                                <p className="text-xs" style={{ color: 'var(--muted)' }}>{finding.recommendation}</p>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'enumeration' && (
              <div className="space-y-6">
                {/* Header Section with Scan ID, Status, Progress, and Action Buttons */}
                <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                  <div className="space-y-4">
                    {/* Scan ID and Status Row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div>
                          <div className="text-sm font-mono" style={{ color: 'var(--muted)' }}>
                            ID: {scan?.id.substring(0, 8).toUpperCase()}...
                          </div>
                          {/* Progress Bar */}
                          {(scan?.status === 'running' || scan?.status === 'queued') && (
                            <div className="mt-2 w-full h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
                              <div 
                                className="h-full transition-all duration-300"
                                style={{ 
                                  background: 'var(--brand)',
                                  width: `${scan?.progress_pct || 0}%`
                                }}
                              />
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          {scan?.status === 'running' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#10b981', color: '#ffffff', borderColor: '#10b981' }}>
                              RUNNING
                            </span>
                          )}
                          {scan?.status === 'queued' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#f59e0b', color: '#ffffff', borderColor: '#f59e0b' }}>
                              QUEUED
                            </span>
                          )}
                          {scan?.status === 'completed' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#10b981', color: '#ffffff', borderColor: '#10b981' }}>
                              COMPLETED
                            </span>
                          )}
                          {scan?.scan_level === 'advanced' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#a855f7', color: '#ffffff', borderColor: '#a855f7' }}>
                              ADVANCE
                            </span>
                          )}
                          {scan?.scan_level === 'pro' && (
                            <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: '#6366f1', color: '#ffffff', borderColor: '#6366f1' }}>
                              PRO
                            </span>
                          )}
                        </div>
                      </div>
                      {/* Action Buttons */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleDownloadPdf('full')}
                          disabled={downloadingFull || downloadingExecutive}
                          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', color: 'var(--fg)' }}
                        >
                          {downloadingFull ? (
                            <>
                              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: 'var(--muted)' }}></span>
                              <span>Preparing...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                              </svg>
                              <span>Download Full PDF</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => handleDownloadPdf('executive')}
                          disabled={downloadingFull || downloadingExecutive}
                          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', color: 'var(--fg)' }}
                        >
                          {downloadingExecutive ? (
                            <>
                              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: 'var(--muted)' }}></span>
                              <span>Preparing...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                              </svg>
                              <span>Executive PDF</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={handleDownloadCSV}
                          disabled={downloadingCSV || !inventory}
                          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ borderColor: '#10b981', background: '#10b981', color: '#ffffff' }}
                        >
                          {downloadingCSV ? (
                            <>
                              <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent border-white"></span>
                              <span>Preparing...</span>
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                              <span>Download Technical CSV</span>
                            </>
                          )}
                        </button>
                        {(scan?.status === 'running' || scan?.status === 'queued') && (
                          <button
                            onClick={cancelScan}
                            disabled={cancelling}
                            className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                            style={{ borderColor: '#ef4444', background: '#ef4444', color: '#ffffff' }}
                          >
                            {cancelling ? (
                              <>
                                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent border-white"></span>
                                <span>Cancelling...</span>
                              </>
                            ) : (
                              'CANCEL SCAN'
                            )}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Summary Cards */}
                {inventoryLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500"></div>
                  </div>
                ) : !inventory ? (
                  <div className="text-center py-12" style={{ color: 'var(--muted)' }}>
                    <p>No enumeration data available yet.</p>
                    <p className="text-sm mt-2">Enumeration data will appear here once the scan completes the discovery phase.</p>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* Summary Cards */}
                    {inventory.discovery?.merged && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                          <div className="text-3xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                            {inventory.discovery.merged.all_urls_count || 0}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Total URLs</div>
                        </div>
                        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                          <div className="text-3xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                            {inventory.discovery.merged.unique_urls_count || 0}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Unique URLs</div>
                        </div>
                        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                          <div className="text-3xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                            {inventory.discovery.merged.param_urls_count || 0}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Parameterized URLs</div>
                        </div>
                        <div className="rounded-lg border p-4" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                          <div className="text-3xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                            {(() => {
                              // Count total parameters discovered by Arjun
                              const arjunParams = inventory.discovery?.arjun?.params_by_url || {};
                              let totalParams = 0;
                              Object.values(arjunParams).forEach((params: any) => {
                                if (Array.isArray(params)) {
                                  totalParams += params.length;
                                } else if (typeof params === 'object' && params !== null) {
                                  totalParams += Object.keys(params).length;
                                }
                              });
                              return totalParams;
                            })()}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Parameters Discovered</div>
                        </div>
                      </div>
                    )}

                    {/* Tool Breakdown */}
                    <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Tool Breakdown</h3>
                        <span className="px-3 py-1 text-xs font-medium rounded-full border" style={{ background: 'var(--surface-2)', color: 'var(--muted)', borderColor: 'var(--border)' }}>
                          Asset Enumeration Phase
                        </span>
                      </div>
                      <div className="space-y-4">
                        {/* HTTPX - Always show if inventory exists, even if empty */}
                        {inventory.discovery && (
                          <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg)' }}>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                                <svg className="w-5 h-5" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                                </svg>
                              </div>
                              <div>
                                <div className="font-medium" style={{ color: 'var(--fg)' }}>HTTPX (Tech Detection)</div>
                                {inventory.discovery.httpx?.final_url && (
                                  <div className="text-xs truncate max-w-md" style={{ color: 'var(--muted)' }}>
                                    {inventory.discovery.httpx.final_url}
                                  </div>
                                )}
                                {inventory.discovery.httpx?.error && (
                                  <div className="text-xs" style={{ color: 'var(--error)' }}>
                                    {inventory.discovery.httpx.error}
                                  </div>
                                )}
                              </div>
                            </div>
                            <span className="px-3 py-1 text-xs font-medium rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                              {inventory.discovery.httpx?.tech?.length || 0} technologies
                            </span>
                          </div>
                        )}
                        
                        {/* Katana - Always show if inventory exists */}
                        {inventory.discovery && (
                          <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg)' }}>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                                <svg className="w-5 h-5" style={{ color: '#10b981' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                                </svg>
                              </div>
                              <div>
                              <div className="font-medium" style={{ color: 'var(--fg)' }}>Katana (Live Crawl)</div>
                                {inventory.discovery.katana?.error && (
                                  <div className="text-xs" style={{ color: 'var(--error)' }}>
                                    {inventory.discovery.katana.error}
                                  </div>
                                )}
                              </div>
                            </div>
                            <span className="px-3 py-1 text-xs font-medium rounded-full" style={{ background: '#10b981', color: '#ffffff' }}>
                              {inventory.discovery.katana?.urls_count || inventory.discovery.katana?.urls?.length || 0} URLs
                            </span>
                          </div>
                        )}
                        
                        {/* GAU - Always show if inventory exists */}
                        {inventory.discovery && (
                          <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg)' }}>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                                <svg className="w-5 h-5" style={{ color: '#a855f7' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                </svg>
                              </div>
                              <div className="font-medium" style={{ color: 'var(--fg)' }}>GAU (Historical URLs)</div>
                            </div>
                            <span className="px-3 py-1 text-xs font-medium rounded-full" style={{ background: '#a855f7', color: '#ffffff' }}>
                              {inventory.discovery.gau?.urls_count || inventory.discovery.gau?.urls?.length || 0} URLs
                            </span>
                          </div>
                        )}
                        
                        {/* Arjun - Always show if inventory exists */}
                        {inventory.discovery && (
                          <div className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--bg)' }}>
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                                <svg className="w-5 h-5" style={{ color: '#f97316' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                </svg>
                              </div>
                              <div>
                                <div className="font-medium flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                                  Arjun (Parameter Discovery)
                                  {(() => {
                                    const arjunState = toolStates.find(ts => ts.tool === 'arjun' && ts.phase === 'enumerate');
                                    if (arjunState && ['running', 'starting', 'queued'].includes(arjunState.stage)) {
                                      return <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse"></span>;
                                    }
                                    return null;
                                  })()}
                                </div>
                                {(() => {
                                  const arjunState = toolStates.find(ts => ts.tool === 'arjun' && ts.phase === 'enumerate');
                                  if (arjunState && ['running', 'starting', 'queued'].includes(arjunState.stage)) {
                                    return <div className="text-xs" style={{ color: 'var(--muted)' }}>Scan in progress...</div>;
                                  }
                                  return null;
                                })()}
                              </div>
                            </div>
                            <span className="px-3 py-1 text-xs font-medium rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                              {Object.keys(inventory.discovery.arjun?.params_by_url || {}).length || 0} URLs with params
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Parameterized URLs */}
                    {inventory.discovery?.merged?.param_urls && inventory.discovery.merged.param_urls.length > 0 && (
                      <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                        <div className="flex items-center justify-between mb-4">
                          <div className="flex items-center gap-2">
                            <h3 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Parameterized URLs</h3>
                            <span className="px-2 py-0.5 text-xs font-medium rounded border" style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fbbf24' }}>
                              FOR XSS/SQLI TESTING
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm" style={{ color: 'var(--muted)' }}>
                              {inventory.discovery.merged.param_urls.length} total
                            </span>
                            <button
                              onClick={handleDownloadCSV}
                              disabled={downloadingCSV}
                              className="p-1.5 rounded hover:opacity-80 transition disabled:opacity-50"
                              style={{ color: 'var(--muted)' }}
                              title="Download CSV"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {inventory.discovery.merged.param_urls.map((url: string, idx: number) => {
                            // Extract parameter value from URL for highlighting
                            // Try to find the first parameter value after = sign
                            const paramMatch = url.match(/([?&][^=]+=)([^&]+)/);
                            
                            if (paramMatch) {
                              const beforeParam = url.substring(0, paramMatch.index! + paramMatch[1].length);
                              const paramValue = paramMatch[2];
                              const afterParam = url.substring(paramMatch.index! + paramMatch[0].length);
                              
                              return (
                                <div
                                  key={idx}
                                  className="text-sm font-mono p-3 rounded break-all"
                                  style={{ background: 'var(--bg)', color: 'var(--fg)' }}
                                >
                                  <span className="text-gray-400">{(idx + 1).toString().padStart(2, '0')}</span>{' '}
                                  {beforeParam}
                                  <span style={{ color: '#f97316', fontWeight: 'bold' }}>{paramValue}</span>
                                  {afterParam}
                                </div>
                              );
                            }
                            
                            return (
                              <div
                                key={idx}
                                className="text-sm font-mono p-3 rounded break-all"
                                style={{ background: 'var(--bg)', color: 'var(--fg)' }}
                              >
                                <span className="text-gray-400">{(idx + 1).toString().padStart(2, '0')}</span>{' '}
                                {url}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* All Discovered URLs */}
                    {(() => {
                      const allUrls = inventory.discovery?.merged?.all_urls || [];
                      const uniqueUrls = inventory.discovery?.merged?.unique_urls || [];
                      const paramUrls = inventory.discovery?.merged?.param_urls || [];
                      const paramUrlSet = new Set(paramUrls);
                      // Filter out parameterized URLs to show only non-parameterized ones
                      const nonParamUrls = uniqueUrls.filter((url: string) => !paramUrlSet.has(url));
                      
                      return nonParamUrls.length > 0 ? (
                        <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2">
                              <h3 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>All Discovered URLs</h3>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm" style={{ color: 'var(--muted)' }}>
                                {nonParamUrls.length} total
                              </span>
                              <button
                                onClick={handleDownloadCSV}
                                disabled={downloadingCSV}
                                className="p-1.5 rounded hover:opacity-80 transition disabled:opacity-50"
                                style={{ color: 'var(--muted)' }}
                                title="Download CSV"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                              </button>
                            </div>
                          </div>
                          <div className="space-y-2 max-h-96 overflow-y-auto">
                            {nonParamUrls.map((url: string, idx: number) => (
                              <div
                                key={idx}
                                className="text-sm font-mono p-3 rounded break-all"
                                style={{ background: 'var(--bg)', color: 'var(--fg)' }}
                              >
                                <span className="text-gray-400">{(idx + 1).toString().padStart(2, '0')}</span>{' '}
                                {url}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null;
                    })()}

                    {/* HTTPX Surface Assets Section */}
                    {httpxSurfaceArtifacts && httpxSurfaceArtifacts.payload && (
                      <div className="rounded-lg border p-6" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                        <div className="flex items-center justify-between mb-4">
                          <div>
                            <h3 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>HTTP Surface Discovery</h3>
                            <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                              Endpoints discovered by HTTPX. These are informational assets, not security vulnerabilities.
                            </p>
                          </div>
                        </div>

                        {/* In-Scope Endpoints */}
                        {httpxSurfaceArtifacts.payload.in_scope && (
                          <div className="mb-6">
                            <h4 className="text-sm font-semibold mb-3" style={{ color: 'var(--fg)' }}>In-Scope Endpoints</h4>
                            
                            {/* In-Scope 404 Groups */}
                            {httpxSurfaceArtifacts.payload.in_scope['404_groups'] && httpxSurfaceArtifacts.payload.in_scope['404_groups'].length > 0 && (
                              <div className="mb-4">
                                <details className="group">
                                  <summary className="cursor-pointer text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                                    <svg className="w-4 h-4 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                    404 Endpoints ({httpxSurfaceArtifacts.payload.in_scope['404_groups'].reduce((sum: number, g: any) => sum + (g.count || 0), 0)} total)
                                  </summary>
                                  <div className="mt-2 space-y-2 pl-6">
                                    {httpxSurfaceArtifacts.payload.in_scope['404_groups'].map((group: any, idx: number) => (
                                      <div key={idx} className="p-3 rounded border" style={{ background: 'var(--bg)', borderColor: 'var(--border)' }}>
                                        <div className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>
                                          {group.count} endpoints with 404 status
                                          {group.normalized_title && (
                                            <span className="text-xs ml-2" style={{ color: 'var(--muted)' }}>
                                              ({group.normalized_title})
                                            </span>
                                          )}
                                        </div>
                                        {group.urls && group.urls.length > 0 && (
                                          <div className="mt-2 space-y-1">
                                            {group.urls.slice(0, 5).map((url: string, urlIdx: number) => (
                                              <div key={urlIdx} className="text-xs font-mono break-all" style={{ color: 'var(--muted)' }}>
                                                {url}
                                              </div>
                                            ))}
                                            {group.urls.length > 5 && (
                                              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                                                ... and {group.urls.length - 5} more
                                              </div>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                </details>
                              </div>
                            )}

                            {/* In-Scope Other Endpoints */}
                            {httpxSurfaceArtifacts.payload.in_scope.other_endpoints && httpxSurfaceArtifacts.payload.in_scope.other_endpoints.length > 0 && (
                              <div>
                                <details className="group">
                                  <summary className="cursor-pointer text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                                    <svg className="w-4 h-4 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                    </svg>
                                    Other Endpoints ({httpxSurfaceArtifacts.payload.in_scope.other_endpoints.length} shown
                                    {httpxSurfaceArtifacts.payload.in_scope.other_endpoints_summary && (
                                      <span>, {httpxSurfaceArtifacts.payload.in_scope.other_endpoints_summary.remaining} more
                                      </span>
                                    )})
                                  </summary>
                                  <div className="mt-2 space-y-2 pl-6 max-h-96 overflow-y-auto">
                                    {httpxSurfaceArtifacts.payload.in_scope.other_endpoints.map((endpoint: any, idx: number) => (
                                      <div key={idx} className="p-3 rounded border" style={{ background: 'var(--bg)', borderColor: 'var(--border)' }}>
                                        <div className="text-sm font-mono break-all mb-1" style={{ color: 'var(--fg)' }}>
                                          {endpoint.url}
                                        </div>
                                        <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--muted)' }}>
                                          {endpoint.status_code && (
                                            <span>HTTP {endpoint.status_code}</span>
                                          )}
                                          {endpoint.title && (
                                            <span className="truncate max-w-md">{endpoint.title}</span>
                                          )}
                                          {endpoint.tech && endpoint.tech.length > 0 && (
                                            <span>Tech: {endpoint.tech.slice(0, 3).join(', ')}</span>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </details>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Out-of-Scope 404s (Collapsed by default) */}
                        {httpxSurfaceArtifacts.payload.out_of_scope && httpxSurfaceArtifacts.payload.out_of_scope['404_groups'] && httpxSurfaceArtifacts.payload.out_of_scope['404_groups'].length > 0 && (
                          <div className="border-t pt-4" style={{ borderColor: 'var(--border)' }}>
                            <details className="group">
                              <summary className="cursor-pointer text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--muted)' }}>
                                <svg className="w-4 h-4 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                                External 404 Pages (Out-of-Scope) - {httpxSurfaceArtifacts.payload.out_of_scope['404_groups'].reduce((sum: number, g: any) => sum + (g.count || 0), 0)} URLs
                              </summary>
                              <div className="mt-2 space-y-2 pl-6">
                                {httpxSurfaceArtifacts.payload.out_of_scope['404_groups'].map((group: any, idx: number) => (
                                  <div key={idx} className="p-3 rounded border" style={{ background: 'var(--bg)', borderColor: 'var(--border)' }}>
                                    <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>
                                      {group.count} external 404 endpoints
                                      {group.normalized_title && (
                                        <span className="text-xs ml-2">({group.normalized_title})</span>
                                      )}
                                    </div>
                                    {group.urls && group.urls.length > 0 && (
                                      <div className="mt-2 space-y-1">
                                        {group.urls.slice(0, 3).map((url: string, urlIdx: number) => (
                                          <div key={urlIdx} className="text-xs font-mono break-all" style={{ color: 'var(--muted)' }}>
                                            {url}
                                          </div>
                                        ))}
                                        {group.urls.length > 3 && (
                                          <div className="text-xs" style={{ color: 'var(--muted)' }}>
                                            ... and {group.urls.length - 3} more
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </details>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'tech-deps' && (
              <div className="space-y-6">
                <TechDependenciesPanel
                  artifact={techStack}
                  loading={techStackLoading}
                />
              </div>
            )}

            {activeTab === 'repo-deps' && (
              <div className="space-y-6">
                <RepoDependenciesPanel
                  artifact={artifacts?.items?.find((a: any) => a.type === 'repo_sca')?.payload || null}
                  loading={artifactsLoading}
                />
              </div>
            )}

            {activeTab === 'ai-summary' && (
              <div className="space-y-6">
                <AISummaryPanel scanId={scanId} />
              </div>
            )}
          </div>
        </main>

        {selectedCweId && (
          <CWEDrawer
            cweId={selectedCweId}
            open={cweDrawerOpen}
            onClose={() => {
              setCweDrawerOpen(false);
              setSelectedCweId(null);
            }}
          />
        )}
      </div>
    </div>
  );
}
