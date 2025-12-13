'use client';

/**
 * Scan Report Page
 * 
 * Displays detailed scan report with executive summary, findings, metadata, and stack info.
 */

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { thandevFetchJSON, thandevFetchPDF } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';
import { formatCategory } from '@/lib/vulnCategories';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import AIAttackPlan from '@/components/Scans/AIAttackPlan';

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
};

type ToolExecution = {
  tool_name: string;
  exit_code: number | null;
  started_at: string;
  completed_at: string | null;
  output_size: number;
  execution_time: number | null;
  error_message: string | null;
  timed_out: boolean;
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

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

  useEffect(() => {
    async function load() {
      if (!session) return;
      
      try {
        setLoading(true);
        setError(null);
        const data = await thandevFetchJSON<ScanDetail>(`/api/scans/${scanId}`, session);
        setScan(data);
      } catch (err) {
        console.error('Error loading scan:', err);
        setError(err instanceof Error ? err.message : 'Network error while loading scan');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scanId, session]);

  // Load tools data
  useEffect(() => {
    async function loadTools() {
      if (!session || !scanId) return;
      
      try {
        setToolsLoading(true);
        setToolsError(null);
        const data = await thandevFetchJSON<ToolsResponse>(`/api/scans/${scanId}/tools`, session);
        setTools(data.items || []);
      } catch (err) {
        console.error('Error loading tools:', err);
        setToolsError(err instanceof Error ? err.message : 'Failed to load tools');
      } finally {
        setToolsLoading(false);
      }
    }
    loadTools();
  }, [scanId, session]);

  // Load findings data from paginated endpoint
  useEffect(() => {
    async function loadFindings() {
      if (!session || !scanId) return;
      
      try {
        setFindingsLoading(true);
        setFindingsError(null);
        // Fetch findings with a reasonable limit (200 max per backend)
        const data = await thandevFetchJSON<{ items: Finding[]; total: number; skip: number; limit: number }>(
          `/api/scans/${scanId}/findings?limit=200`,
          session
        );
        setFindings(data.items || []);
        setFindingsTotal(data.total || 0);
        
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
  }, [scanId, session]);

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

  // Tool badge component
  function ToolBadge({ tool }: { tool: string }) {
    const normalized = tool.toLowerCase();
    let label = tool;
    let classes = 'px-2 py-0.5 rounded-full text-[10px] font-medium border';

    if (normalized === 'nmap') {
      classes += ' bg-sky-900/40 text-sky-200 border-sky-500/50';
      label = 'Nmap';
    } else if (normalized === 'sslscan') {
      classes += ' bg-teal-900/40 text-teal-200 border-teal-500/50';
      label = 'SSLScan';
    } else if (normalized === 'nuclei') {
      classes += ' bg-purple-900/40 text-purple-200 border-purple-500/50';
      label = 'Nuclei';
    } else if (normalized === 'http_headers') {
      classes += ' bg-amber-900/40 text-amber-200 border-amber-500/50';
      label = 'HTTP Headers';
    } else {
      classes += ' bg-slate-800/40 text-slate-200 border-slate-600/50';
      label = tool;
    }

    return <span className={classes}>{label}</span>;
  }

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

  // Error state
  if (error || !scan) {
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
                <p className="text-red-300">{error || 'Scan not found'}</p>
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

  // Calculate network & TLS metrics from loaded findings
  const nmapFindings = findings.filter(f => f.tool_name?.toLowerCase() === 'nmap');
  const sslscanFindings = findings.filter(f => f.tool_name?.toLowerCase() === 'sslscan');
  const openPortsCount = nmapFindings.length;
  const hasTlsIssues = sslscanFindings.length > 0;

  // Generate executive summary if not available but findings exist
  const generateExecutiveSummary = () => {
    if (scan?.summary?.executive_summary) {
      return scan.summary.executive_summary;
    }
    if (findings.length === 0 || scan?.status !== 'completed') {
      return null;
    }
    
    const criticalCount = findings.filter(f => f.severity?.toLowerCase() === 'critical').length;
    const highCount = findings.filter(f => f.severity?.toLowerCase() === 'high').length;
    const mediumCount = findings.filter(f => f.severity?.toLowerCase() === 'medium').length;
    const lowCount = findings.filter(f => f.severity?.toLowerCase() === 'low').length;
    const infoCount = findings.filter(f => f.severity?.toLowerCase() === 'info').length;
    
    if (criticalCount > 0) {
      return `CRITICAL: ${criticalCount} critical vulnerability${criticalCount > 1 ? 'ies' : 'y'} detected requiring immediate attention. ${highCount > 0 ? `Additionally, ${highCount} high-severity issue${highCount > 1 ? 's' : ''} were found.` : ''} This scan identified ${findings.length} total finding${findings.length > 1 ? 's' : ''} across the target.`;
    } else if (highCount > 0) {
      return `HIGH PRIORITY: ${highCount} high-severity vulnerability${highCount > 1 ? 'ies' : 'y'} found. Review recommended. ${mediumCount > 0 ? `The scan also detected ${mediumCount} medium-severity issue${mediumCount > 1 ? 's' : ''}.` : ''} Total findings: ${findings.length}.`;
    } else if (mediumCount > 0 || lowCount > 0) {
      return `Scan completed with ${findings.length} finding${findings.length > 1 ? 's' : ''}. ${mediumCount > 0 ? `${mediumCount} medium-severity` : `${lowCount} low-severity`} issue${(mediumCount || lowCount) > 1 ? 's' : ''} detected. No critical or high-severity vulnerabilities found.`;
    } else if (infoCount > 0) {
      return `Scan completed successfully. ${infoCount} informational finding${infoCount > 1 ? 's' : ''} detected. No security vulnerabilities identified.`;
    } else {
      return `Scan completed with ${findings.length} finding${findings.length > 1 ? 's' : ''}. Review recommended.`;
    }
  };

  // Generate top risks if not available but findings exist
  const generateTopRisks = () => {
    if (scan?.summary?.top_risks && scan.summary.top_risks.length > 0) {
      return scan.summary.top_risks;
    }
    if (findings.length === 0 || scan?.status !== 'completed') {
      return [];
    }
    
    const severityOrder = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
    const sortedFindings = [...findings].sort((a, b) => {
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
            {/* Error banner - Show prominently at top if scan has error */}
            {scan?.error_message && (
              <div className="rounded-xl border-2 border-red-500/70 bg-red-900/30 p-4 shadow-lg">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div className="flex-1">
                    <div className="font-semibold mb-1 text-sm text-red-300">Scan Error</div>
                    <pre className="whitespace-pre-wrap text-sm text-red-200 font-sans">{scan.error_message}</pre>
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

            {/* Main grid */}
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
                          href={`/dashboard/news?search=${encodeURIComponent(cveIds[0])}`}
                          className="inline-flex items-center gap-1.5 text-xs text-[var(--brand)] hover:text-[var(--brand)]/80 hover:underline transition-colors"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                          </svg>
                          View news for {cveIds[0]}
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
                              <span className={`px-1.5 py-0.5 rounded text-xs font-medium border ${severityColor} mr-2`}>
                                [{severity}]
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
              <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>
                Findings
                {findingsTotal > 0 && (
                  <span className="ml-2 text-sm font-normal" style={{ color: 'var(--muted)' }}>
                    ({findingsTotal})
                  </span>
                )}
              </h2>
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
                    <div key={findingKey} className="border rounded-lg p-4 transition-colors hover:opacity-80" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex-1">
                          <h4 className="font-medium text-sm" style={{ color: 'var(--fg)' }}>{finding.title}</h4>
                        </div>
                        <div className="flex items-center gap-2">
                          {finding.tool_name && <ToolBadge tool={finding.tool_name} />}
                          {finding.status && <StatusBadge status={finding.status} />}
                          <span className={`px-2 py-1 text-xs font-medium rounded-full border ${severityClasses(finding.severity)}`}>
                            {finding.severity?.toUpperCase() || 'INFO'}
                          </span>
                        </div>
                      </div>
                      {finding.description && (
                        <p className="text-sm mb-2" style={{ color: 'var(--fg)' }}>{finding.description}</p>
                      )}
                      {finding.categories && finding.categories.length > 0 && (
                        <div className="mt-1 mb-2 flex flex-wrap gap-1">
                          {finding.categories.map((cat) => (
                            <span
                              key={cat}
                              className="inline-flex items-center rounded-full border border-border/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
                              style={{
                                borderColor: 'var(--border)',
                                color: 'var(--muted)',
                                background: 'var(--surface-2)'
                              }}
                            >
                              {formatCategory(cat)}
                            </span>
                          ))}
                        </div>
                      )}
                      <div className="flex flex-wrap gap-2 mt-2">
                        {finding.cve_id && (
                          <span className="px-2 py-1 text-xs font-mono rounded border" style={{ background: 'var(--surface-2)', color: 'var(--fg)', borderColor: 'var(--border)' }}>
                            CVE: {finding.cve_id}
                          </span>
                        )}
                        {finding.cwe_id && (
                          <span className="px-2 py-1 text-xs font-mono rounded border" style={{ background: 'var(--surface-2)', color: 'var(--fg)', borderColor: 'var(--border)' }}>
                            CWE: {finding.cwe_id}
                          </span>
                        )}
                        {finding.cvss_score !== null && finding.cvss_score !== undefined && typeof finding.cvss_score === 'number' && (
                          <span className="px-2 py-1 text-xs rounded border" style={{ background: 'var(--surface-2)', color: 'var(--fg)', borderColor: 'var(--border)' }}>
                            CVSS: {finding.cvss_score.toFixed(1)}
                          </span>
                        )}
                      </div>
                      {finding.url && (
                        <p className="text-xs font-mono mt-2 break-all" style={{ color: 'var(--muted)' }}>{finding.url}</p>
                      )}
                      {finding.path && (
                        <p className="text-xs font-mono mt-1" style={{ color: 'var(--muted)' }}>
                          Path: {finding.path}
                          {finding.line_number && ` (line ${finding.line_number})`}
                        </p>
                      )}
                      {finding.recommendation && (
                        <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
                          <p className="text-xs font-medium mb-1" style={{ color: 'var(--fg)' }}>Recommendation:</p>
                          <p className="text-xs italic" style={{ color: 'var(--muted)' }}>{finding.recommendation}</p>
                        </div>
                      )}
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
              <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Scan Details</h2>
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

            {/* Tools Used card */}
            <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Tools Used</h2>
              {toolsLoading ? (
                <div className="space-y-3">
                  <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" style={{ background: 'var(--surface-2)' }}></div>
                  <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" style={{ background: 'var(--surface-2)' }}></div>
                </div>
              ) : toolsError ? (
                <div className="text-sm text-red-400">{toolsError}</div>
              ) : tools.length === 0 ? (
                <div className="text-center py-6">
                  <div className="w-10 h-10 mx-auto mb-2 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', opacity: 0.5 }}>
                    <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>No tool execution data available</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {tools.map((tool) => {
                    const isSuccess = tool.exit_code === 0 && !tool.timed_out;
                    const isTimedOut = tool.timed_out;
                    const toolName = tool.tool_name.charAt(0).toUpperCase() + tool.tool_name.slice(1);
                    const runtime = tool.execution_time ? `${tool.execution_time.toFixed(1)}s` : 'N/A';
                    const outputSizeKB = tool.output_size > 0 ? (tool.output_size / 1024).toFixed(1) : '0';
                    
                    // Determine status label and styling
                    let statusLabel = '';
                    let statusColor = '';
                    let statusBg = '';
                    let statusBorder = '';
                    let statusHelpText = '';
                    
                    if (isTimedOut) {
                      statusLabel = 'Timed out';
                      statusColor = 'text-amber-200';
                      statusBg = 'bg-amber-900/40';
                      statusBorder = 'border-amber-500/50';
                      statusHelpText = 'ffuf hit the maximum runtime limit; results may be partial.';
                    } else if (isSuccess) {
                      statusLabel = 'Success';
                      statusColor = 'text-emerald-200';
                      statusBg = 'bg-emerald-900/40';
                      statusBorder = 'border-emerald-500/50';
                    } else {
                      statusLabel = 'Error';
                      statusColor = 'text-red-200';
                      statusBg = 'bg-red-900/40';
                      statusBorder = 'border-red-500/50';
                    }
                    
                    return (
                      <div
                        key={tool.tool_name}
                        className="flex items-center justify-between p-3 rounded-lg border"
                        style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                      >
                        <div className="flex items-center gap-3 flex-1">
                          <span
                            className={`px-2.5 py-1 text-xs font-medium rounded-full border ${statusBg} ${statusColor} ${statusBorder}`}
                          >
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
                            <span 
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded border bg-amber-900/20 text-amber-300 border-amber-500/30"
                              title={statusHelpText}
                            >
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Timed out
                            </span>
                          )}
                          {!isTimedOut && tool.error_message && (
                            <span 
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded border bg-red-900/20 text-red-300 border-red-500/30 truncate max-w-[200px]"
                              title={tool.error_message}
                            >
                              <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Error
                            </span>
                          )}
                          {isSuccess && !isTimedOut && !tool.error_message && (
                            <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded border bg-emerald-900/20 text-emerald-300 border-emerald-500/30">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              Success
                            </span>
                          )}
                        </div>
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
          </div>
        </main>
      </div>
    </div>
  );
}
