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
import AIAttackPlan from '@/components/Scans/AIAttackPlan';
import TechDependenciesPanel from '@/components/Scans/TechDependenciesPanel';
import RepoDependenciesPanel from '@/components/Scans/RepoDependenciesPanel';
import CWEDrawer from '@/components/Dashboard/CWEDrawer';
import AISummaryPanel from '@/components/Scans/AISummaryPanel';
import PhaseTimeline from '@/components/Scans/PhaseTimeline';
import SeverityBadge from '@/components/Scans/SeverityBadge';
import { useScanEvents } from '@/hooks/useScanEvents';

// Types
type FindingStatus = "open" | "acknowledged" | "resolved" | "suppressed";

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
  const [findingsError, setFindingsError] = useState<string | null>(null);
  const [findingsTotal, setFindingsTotal] = useState(0);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [selectedToolFilter, setSelectedToolFilter] = useState<string>('all');  // Filter findings by tool
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

  // Connect to real-time scan events via WebSocket
  const { events, toolStates: wsToolStates, isConnected } = useScanEvents(scanId);
  
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

  // Poll for scan status updates when scan is running/queued
  useEffect(() => {
    if (!session) return;

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

        setScan(data);

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

    // Initial load
    setLoading(true);
    setInitialLoadFailed(false);
    loadScan().catch((err) => {
      // Mark initial load as failed so we show full-page error
      setInitialLoadFailed(true);
      setError(err instanceof Error ? err.message : 'Failed to load scan');
    }).finally(() => setLoading(false));

    // Set up polling if scan is running/queued
    const checkAndPoll = async () => {
      // Skip if scanId looks like a CVE ID
      if (scanId && scanId.toUpperCase().startsWith('CVE-')) {
        return;
      }

      const currentScan = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session).catch(() => null);

      if (currentScan && (currentScan.status === 'running' || currentScan.status === 'queued' || currentScan.status === 'pending')) {
        // Start polling every 3-5 seconds
        pollInterval = setInterval(loadScan, 4000); // 4 seconds
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
        setTools(data.items || []);
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
      pollInterval = setInterval(loadTools, 3000); // Poll every 3 seconds
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
        setFindingsError(null);
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
        setFindings(data.items || []);
        setFindingsTotal(data.total || 0);
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
        setFindingsError(err instanceof Error ? err.message : 'Failed to load findings');
      } finally {
        setFindingsLoading(false);
      }
    }
    loadFindings();
    
    // Poll for findings updates while scan is running (only on first page to avoid disrupting user)
    const isRunning = scan?.status === 'running' || scan?.status === 'queued';
    let pollInterval: NodeJS.Timeout | null = null;
    
    if (isRunning && findingsPage === 0) {
      pollInterval = setInterval(() => {
        isPolling = true;
        loadFindings();
      }, 5000); // Poll every 5 seconds
    }
    
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [scanId, session, findingsPage, findingsLimit, selectedToolFilter, scan?.status]);

  // Load artifacts
  const loadArtifacts = async () => {
    if (!session) return;

    try {
      setArtifactsLoading(true);
      const data = await thandevFetchJSON<{ items: any[] }>(`/api/scans/${scanId}/artifacts`, session);
      setArtifacts(data);
    } catch (err) {
      console.error('Error loading artifacts:', err);
    } finally {
      setArtifactsLoading(false);
    }
  };

  // Load artifacts when dependency tabs are activated
  // Also reload if scan status changes (e.g., from running to completed) to pick up new artifacts
  useEffect(() => {
    if ((activeTab === 'tech-deps' || activeTab === 'repo-deps' || activeTab === 'ai-summary') && !artifactsLoading && session) {
      loadArtifacts();
    }
  }, [activeTab, session, scan?.status]); // Reload when tab changes, session changes, or scan status changes

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
      setTechStackLoading(true);
      try {
        const data = await thandevFetchJSON<any>(`/api/scans/${scanId}/tech-stack`, session);
        console.log('[TECH-STACK] Received data from API:', data);
        console.log('[TECH-STACK] Fingerprint:', data?.fingerprint);
        console.log('[TECH-STACK] Technologies count:', data?.fingerprint?.technologies?.length || 0);
        setTechStack(data);
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
    const interval = isRunning ? setInterval(fetchTechStack, 10000) : null; // Reduced frequency to 10s

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
      setInventoryLoading(true);
      try {
        const data = await thandevFetchJSON<any>(`/api/scans/${scanId}/inventory`, session);
        setInventory(data?.inventory || null);
      } catch (error) {
        console.error('Failed to fetch enumeration inventory:', error);
        setInventory(null);
      } finally {
        setInventoryLoading(false);
      }
    };

    fetchInventory();
  }, [activeTab, session, scanId, scan]);

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

            {/* Top bar */}
            <div className="flex items-center justify-between">
              <Link
                href={`/projects/${projectId}/scans`}
                className="underline flex items-center gap-2 hover:opacity-80 transition-opacity"
                style={{ color: 'var(--brand)' }}
              >
                <span>←</span>
                <span>Back to scans</span>
              </Link>
              <div className="flex items-center gap-3">
                {/* Reports / Export section */}
                <div className="flex flex-col items-end gap-2">
                  <div className="flex items-center gap-2 rounded-lg border p-1" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                    <button
                      onClick={() => handleDownloadPdf('full')}
                      disabled={downloadingFull || downloadingExecutive}
                      className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                      style={{ borderColor: 'var(--border)', background: 'var(--surface)', color: 'var(--fg)' }}
                    >
                      {downloadingFull ? (
                        <>
                          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: 'var(--muted)' }}></span>
                          <span>Preparing...</span>
                        </>
                      ) : (
                        <>
                          <span>📄</span>
                          <span>Download Full PDF</span>
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleDownloadPdf('executive')}
                      disabled={downloadingFull || downloadingExecutive}
                      className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                      style={{ borderColor: 'var(--border)', background: 'var(--surface)', color: 'var(--fg)' }}
                    >
                      {downloadingExecutive ? (
                        <>
                          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: 'var(--muted)' }}></span>
                          <span>Preparing...</span>
                        </>
                      ) : (
                        <>
                          <span>📊</span>
                          <span>Download Executive PDF</span>
                        </>
                      )}
                    </button>
                  </div>
                  <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                    <span>Full PDF: detailed technical findings</span>
                    <span>•</span>
                    <span>Executive PDF: high-level summary for stakeholders</span>
                  </div>
                </div>
                <span className="text-sm font-mono" style={{ color: 'var(--muted)' }}>
                  {scan.id.substring(0, 8)}...
                </span>
                <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getStatusColor(scan.status)}`}>
                  {scan.status.charAt(0).toUpperCase() + scan.status.slice(1)}
                </span>
                <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getLevelColor(scan.scan_level)}`}>
                  {scan.scan_level.charAt(0).toUpperCase() + scan.scan_level.slice(1)}
                </span>
                {(scan.status === 'queued' || scan.status === 'running') && (
                  <button
                    onClick={cancelScan}
                    disabled={cancelling}
                    className="px-3 py-1 text-xs font-medium rounded border transition-opacity disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                    style={{
                      color: 'var(--destructive)',
                      borderColor: 'var(--destructive)',
                      background: 'transparent'
                    }}
                    title="Cancel scan"
                  >
                    {cancelling ? (
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                        Cancelling...
                      </span>
                    ) : (
                      'Cancel Scan'
                    )}
                  </button>
                )}
              </div>
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
                    className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === tab.id
                      ? 'border-indigo-500 text-indigo-400'
                      : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                      }`}
                    style={{
                      borderBottomColor: activeTab === tab.id ? 'var(--brand)' : 'transparent',
                      color: activeTab === tab.id ? 'var(--brand)' : 'var(--muted)',
                    }}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab Content */}
            {activeTab === 'overview' && (
              <div className="grid gap-6 md:grid-cols-3">
                {/* Left column - Main content */}
                <div className="md:col-span-2 space-y-6">
                  {/* Executive Summary card */}
                  <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Executive Summary</h2>
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
                      <div className="text-center py-8">
                        <div className="w-12 h-12 mx-auto mb-3 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', opacity: 0.5 }}>
                          <svg className="w-6 h-6" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                        </div>
                        <p className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>Executive summary not available yet</p>
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {scan.status === 'completed'
                            ? 'The scan completed but no executive summary was generated. This may occur when no significant findings were detected.'
                            : scan.status === 'running' || scan.status === 'queued'
                              ? 'Executive summary will be available once the scan completes.'
                              : 'Executive summary is not available for this scan.'}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Findings card */}
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
                      <div className="flex items-center gap-3">
                        {/* Tool filter dropdown - shows ALL tools with findings, not just current page */}
                        {(availableTools.length > 0 || findingsTotal > 0) && (
                          <select
                            value={selectedToolFilter}
                            onChange={(e) => {
                              setSelectedToolFilter(e.target.value);
                              setFindingsPage(0); // Reset to first page when filter changes
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
                        {findings.map((finding, idx) => {
                          // Generate stable key from finding properties
                          const findingKey = finding.id || `${finding.title || 'finding'}-${finding.url || ''}-${idx}`;
                          return (
                            <div key={findingKey} className="border rounded-lg p-4 transition-colors hover:opacity-80 overflow-hidden" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)', maxWidth: '100%', wordWrap: 'break-word', overflowWrap: 'break-word' }}>
                              {/* Header: Severity + Status + Title */}
                              <div className="flex items-start justify-between gap-2 mb-3">
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
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <h4 className="font-semibold text-sm break-words" style={{ color: 'var(--fg)', wordBreak: 'break-word', overflowWrap: 'break-word', maxWidth: '100%' }}>{finding.title}</h4>
                                    {finding.vuln_type && (
                                      <span className="px-2 py-0.5 text-[10px] font-medium rounded border uppercase" style={{ background: 'var(--surface)', color: 'var(--muted)', borderColor: 'var(--border)' }}>
                                        {finding.vuln_type}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>

                              <div className="space-y-3">
                                {/* 1. Where it was found - ALWAYS SHOW with tolerant logic */}
                                <div className="space-y-1">
                                  <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                                    Where it was found
                                  </div>
                                  {(() => {
                                    // Tolerant logic: use defaults when missing
                                    const method = finding.http_method || "GET";
                                    const url = finding.url || finding.path || null;
                                    const param = finding.parameter;

                                    if (!url) {
                                      return (
                                        <p className="text-xs italic" style={{ color: 'var(--muted)' }}>
                                          Location information not available
                                        </p>
                                      );
                                    }

                                    return (
                                      <>
                                        <div className="text-xs font-mono break-all overflow-wrap-anywhere" style={{ color: 'var(--fg)', wordBreak: 'break-all', overflowWrap: 'anywhere', maxWidth: '100%' }}>
                                          <span className="font-semibold">{method}</span>{' '}
                                          <span className="break-all" style={{ wordBreak: 'break-all', overflowWrap: 'anywhere' }}>{url}</span>
                                        </div>
                                        {param && (
                                          <div className="text-xs break-words" style={{ color: 'var(--muted)', wordBreak: 'break-word', overflowWrap: 'break-word' }}>
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

                              {/* Technical details (collapsible) - includes tool name */}
                              <details className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
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
                  {/* Scan metadata card */}
                  <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Scan Details</h2>
                    </div>
                    <div className="space-y-3 text-sm">
                      <div>
                        <p className="mb-1" style={{ color: 'var(--muted)' }}>Status</p>
                        <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full border ${getStatusColor(scan.status)}`}>
                          {scan.status.charAt(0).toUpperCase() + scan.status.slice(1)}
                        </span>
                      </div>
                      <div>
                        <p className="mb-1" style={{ color: 'var(--muted)' }}>Level</p>
                        <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full border ${getLevelColor(scan.scan_level)}`}>
                          {scan.scan_level.charAt(0).toUpperCase() + scan.scan_level.slice(1)}
                        </span>
                      </div>
                      <div>
                        <p className="mb-1" style={{ color: 'var(--muted)' }}>Created At</p>
                        <p style={{ color: 'var(--fg)' }}>{formatDateTime(scan.created_at)}</p>
                      </div>
                      {scan.started_at && (
                        <div>
                          <p className="mb-1" style={{ color: 'var(--muted)' }}>Started At</p>
                          <p style={{ color: 'var(--fg)' }}>{formatDateTime(scan.started_at)}</p>
                        </div>
                      )}
                      {scan.completed_at && (
                        <div>
                          <p className="mb-1" style={{ color: 'var(--muted)' }}>Completed At</p>
                          <p style={{ color: 'var(--fg)' }}>{formatDateTime(scan.completed_at)}</p>
                        </div>
                      )}
                      {scan.started_at && scan.completed_at && (
                        <div>
                          <p className="mb-1" style={{ color: 'var(--muted)' }}>Duration</p>
                          <p style={{ color: 'var(--fg)' }}>{calculateDuration(scan.started_at, scan.completed_at)}</p>
                        </div>
                      )}
                      {scan.summary?.risk_score !== null && scan.summary?.risk_score !== undefined && (
                        <div>
                          <p className="mb-1" style={{ color: 'var(--muted)' }}>Risk Score</p>
                          <p className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{scan.summary.risk_score}</p>
                        </div>
                      )}
                      {scan.summary?.findings_count !== null && scan.summary?.findings_count !== undefined && (
                        <div>
                          <p className="mb-1" style={{ color: 'var(--muted)' }}>Findings Count</p>
                          <p className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{scan.summary.findings_count}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Phase Timeline - Show when scan is running */}
                  {(scan.status === 'running' || scan.status === 'queued' || scan.status === 'pending') && (
                    <PhaseTimeline
                      events={events}
                      toolStates={toolStates}
                      scanStatus={scan.status}
                      scanLevel={scan.scan_level}
                      isConnected={isConnected}
                    />
                  )}

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

                  {/* AI Attack Plan card */}
                  <AIAttackPlan aiStatus={scan.ai_status} aiPlan={scan.ai_plan} />

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
                      {findings.map((finding, idx) => {
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
                <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                  <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>
                    Asset Enumeration Results
                  </h2>
                  
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
                      {/* Discovery Summary */}
                      {inventory.discovery?.merged && (
                        <div className="border rounded-lg p-4" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                          <h3 className="text-md font-semibold mb-3" style={{ color: 'var(--fg)' }}>Discovery Summary</h3>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div>
                              <div className="text-2xl font-bold text-indigo-400">{inventory.discovery.merged.all_urls_count || 0}</div>
                              <div className="text-sm" style={{ color: 'var(--muted)' }}>Total URLs</div>
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-green-400">{inventory.discovery.merged.unique_urls_count || 0}</div>
                              <div className="text-sm" style={{ color: 'var(--muted)' }}>Unique URLs</div>
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-yellow-400">{inventory.discovery.merged.param_urls_count || 0}</div>
                              <div className="text-sm" style={{ color: 'var(--muted)' }}>Parameterized URLs</div>
                            </div>
                            <div>
                              <div className="text-2xl font-bold text-purple-400">
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
                        </div>
                      )}

                      {/* Technologies Detected */}
                      {inventory.technologies && inventory.technologies.length > 0 && (
                        <div className="border rounded-lg p-4" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                          <h3 className="text-md font-semibold mb-3" style={{ color: 'var(--fg)' }}>Technologies Detected</h3>
                          <div className="flex flex-wrap gap-2">
                            {inventory.technologies.map((tech: string, idx: number) => (
                              <span
                                key={idx}
                                className="px-3 py-1 rounded-full text-sm font-medium"
                                style={{ background: 'var(--surface)', color: 'var(--brand)', borderWidth: '1px', borderColor: 'var(--border)' }}
                              >
                                {tech}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Tool Breakdown */}
                      <div className="border rounded-lg p-4" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                        <h3 className="text-md font-semibold mb-3" style={{ color: 'var(--fg)' }}>Tool Breakdown</h3>
                        <div className="space-y-3">
                          {inventory.discovery?.httpx && (
                            <div className="flex justify-between items-center">
                              <div>
                                <span className="font-medium">HTTPX (Tech Detection)</span>
                                {inventory.discovery.httpx.final_url && (
                                  <span className="ml-2 text-xs" style={{ color: 'var(--muted)' }}>
                                    → {inventory.discovery.httpx.final_url}
                                  </span>
                                )}
                              </div>
                              <span className="text-sm px-3 py-1 rounded-full" style={{ background: 'var(--surface)', color: 'var(--muted)' }}>
                                {inventory.discovery.httpx.tech?.length || 0} technologies
                              </span>
                            </div>
                          )}
                          {inventory.discovery?.katana && (
                            <div className="flex justify-between items-center">
                              <span className="font-medium">Katana (Live Crawl)</span>
                              <span className="text-sm px-3 py-1 rounded-full" style={{ background: 'var(--surface)', color: inventory.discovery.katana.urls_count > 0 ? 'var(--success)' : 'var(--muted)' }}>
                                {inventory.discovery.katana.urls_count || inventory.discovery.katana.urls?.length || 0} URLs
                              </span>
                            </div>
                          )}
                          {inventory.discovery?.gau && (
                            <div className="flex justify-between items-center">
                              <span className="font-medium">GAU (Historical URLs)</span>
                              <span className="text-sm px-3 py-1 rounded-full" style={{ background: 'var(--surface)', color: inventory.discovery.gau.urls_count > 0 ? 'var(--success)' : 'var(--muted)' }}>
                                {inventory.discovery.gau.urls_count || inventory.discovery.gau.urls?.length || 0} URLs
                              </span>
                            </div>
                          )}
                          {inventory.discovery?.arjun && (
                            <div className="flex justify-between items-center">
                              <span className="font-medium">Arjun (Parameter Discovery)</span>
                              <span className="text-sm px-3 py-1 rounded-full" style={{ background: 'var(--surface)', color: 'var(--muted)' }}>
                                {Object.keys(inventory.discovery.arjun.params_by_url || {}).length || 0} URLs with params
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Parameterized URLs */}
                      {inventory.discovery?.merged?.param_urls && inventory.discovery.merged.param_urls.length > 0 && (
                        <div className="border rounded-lg p-4" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                          <h3 className="text-md font-semibold mb-3" style={{ color: 'var(--fg)' }}>
                            Parameterized URLs (for XSS/SQLi testing) - showing first 15
                          </h3>
                          <div className="space-y-2 max-h-64 overflow-y-auto">
                            {inventory.discovery.merged.param_urls.slice(0, 15).map((url: string, idx: number) => (
                              <div
                                key={idx}
                                className="text-sm font-mono p-2 rounded break-all"
                                style={{ background: 'var(--surface)', color: 'var(--warning)' }}
                              >
                                {url}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* All URLs Preview */}
                      {(() => {
                        const urls = inventory.discovery?.merged?.unique_urls || inventory.discovery?.merged?.all_urls || [];
                        return urls.length > 0 ? (
                          <div className="border rounded-lg p-4" style={{ borderColor: 'var(--border)', background: 'var(--bg)' }}>
                            <h3 className="text-md font-semibold mb-3" style={{ color: 'var(--fg)' }}>
                              All Discovered URLs (showing first 30)
                            </h3>
                            <div className="space-y-2 max-h-96 overflow-y-auto">
                              {urls.slice(0, 30).map((url: string, idx: number) => (
                                <div
                                  key={idx}
                                  className="text-sm font-mono p-2 rounded break-all"
                                  style={{ background: 'var(--surface)', color: 'var(--muted)' }}
                                >
                                  {url}
                                </div>
                              ))}
                              {urls.length > 30 && (
                                <div className="text-center text-sm py-2" style={{ color: 'var(--muted)' }}>
                                  ... and {urls.length - 30} more URLs
                                </div>
                              )}
                            </div>
                          </div>
                        ) : null;
                      })()}
                    </div>
                  )}
                </div>
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
