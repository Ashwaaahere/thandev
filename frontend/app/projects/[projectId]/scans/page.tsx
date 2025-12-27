'use client';

/**
 * Project Scans Page
 * 
 * Architecture:
 * - Frontend runs on http://localhost:3000 (Next.js)
 * - Backend API runs on http://localhost:8000 with /api prefix (FastAPI)
 * - All security scan UI uses thandevFetchJSON/thandevFetchPDF helpers with auth headers
 * 
 * API Endpoints used:
 * - GET  /api/projects/{projectId}
 * - GET  /api/projects (fallback)
 * - GET  /api/scans/project/{projectId} (list scans for project)
 * - POST /api/scans (create new scan)
 * - GET  /api/scans/{scanId} (get scan details)
 * - GET  /api/scans/{scanId}/report.pdf (PDF downloads)
 */

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { thandevFetchJSON, thandevFetchPDF } from '@/lib/thandevApi';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';

// Types
interface Project {
  id: string;
  name: string;
  target_url: string;
  root_domain?: string | null;
  description?: string;
}

interface Finding {
  id: string;
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  url?: string;
  cve_id?: string;
  tool_name: string;
}

interface Scan {
  id: string;
  project_id: string;
  scan_level: 'basic' | 'pro' | 'advanced';
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  summary?: {
    executive_summary?: string;
    top_risks?: string[];
    remediation_overview?: string;
    risk_score?: number;
    findings_count?: number;
    severity_breakdown?: Record<string, number>;
  };
  stack_info?: {
    target_url?: string;
    scan_level?: string;
    http?: {
      status_code?: number;
      headers?: Record<string, string>;
    };
  };
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  findings: Finding[];
}

type DomainVerificationStatus = {
  project_id: string;
  domain: string;
  status: 'pending' | 'verified' | 'failed' | 'expired';
  token: string;
  record_name: string;
  record_value: string;
  last_checked_at?: string | null;
  verified_at?: string | null;
  expires_at?: string | null;
  last_error?: string | null;
};

// Plan types
type TenantPlanUsage = {
  projects_count: number;
  projects_max: number;
  scans_this_month: number;
  scans_monthly_max: number;
  concurrent_scans: number;
  concurrent_scans_max: number;
};

type PlanLimits = {
  max_projects: number;
  max_scans_per_month: number;
  max_concurrent_scans: number;
  allowed_scan_levels: string[];
};

type TenantPlanInfo = {
  id: string;
  name: string;
  plan: string; // "free" | "individual" | "team"
  limits: PlanLimits;
  usage: TenantPlanUsage;
};

export default function ProjectScansPage() {
  const params = useParams();
  const projectId = params.projectId as string;
  const { data: session } = useSession();

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [project, setProject] = useState<Project | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingScan, setCreatingScan] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [planInfo, setPlanInfo] = useState<TenantPlanInfo | null>(null);
  const [dvStatus, setDvStatus] = useState<DomainVerificationStatus | null>(null);
  const [dvLoading, setDvLoading] = useState<boolean>(false);
  const [dvError, setDvError] = useState<string | null>(null);
  // Track PDF download state per scan: { scanId: { full: boolean, executive: boolean } }
  const [downloadingPdfs, setDownloadingPdfs] = useState<Record<string, { full: boolean; executive: boolean }>>({});
  // Track cancelling state per scan
  const [cancellingScans, setCancellingScans] = useState<Record<string, boolean>>({});

  // Fetch project
  useEffect(() => {
    const fetchProject = async () => {
      if (!session) return;
      
      try {
        const data = await thandevFetchJSON<Project>(`/api/projects/${projectId}`, session);
        setProject(data);
      } catch (err) {
        console.error('Error in project scans page (fetchProject):', err);
        let errorMessage: string;
        if (err instanceof TypeError && err.message === 'Failed to fetch') {
          errorMessage = 'Network error: Cannot reach backend. Is the FastAPI server running?';
        } else if (err instanceof Error) {
          errorMessage = err.message;
        } else {
          errorMessage = 'Unexpected error while fetching data';
        }
        setError(errorMessage);
      }
    };

    fetchProject();
  }, [projectId, session]);

  // Fetch scans
  const fetchScans = async () => {
    if (!session) return;
    
    try {
      // Use project-specific endpoint to get only scans for this project
      const data = await thandevFetchJSON<{ items: Scan[]; total: number }>(
        `/api/scans/project/${projectId}`,
        session
      );
      // Backend returns { items: Scan[], total: number }
      // Items are already sorted by newest first and filtered by project_id
      setScans(data.items);
    } catch (err) {
      console.error('Error in project scans page (fetchScans):', err);
      let errorMessage: string;
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        errorMessage = 'Network error: Cannot reach backend. Is the FastAPI server running?';
      } else if (err instanceof Error) {
        errorMessage = err.message;
      } else {
        errorMessage = 'Unexpected error while fetching data';
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (projectId && session) {
      fetchScans();
    }
  }, [projectId, session]);

  // Fetch domain verification status
  const fetchDomainVerification = async () => {
    if (!session) return;
    setDvLoading(true);
    setDvError(null);
    try {
      const data = await thandevFetchJSON<DomainVerificationStatus>(
        `/api/projects/${projectId}/domain-verification`,
        session
      );
      setDvStatus(data);
    } catch (err) {
      console.error('Error fetching domain verification status:', err);
      if (err instanceof Error) {
        setDvError(err.message);
      } else {
        setDvError('Failed to load domain verification status');
      }
    } finally {
      setDvLoading(false);
    }
  };

  useEffect(() => {
    if (projectId && session) {
      fetchDomainVerification();
    }
  }, [projectId, session]);

  // Fetch plan info
  useEffect(() => {
    async function loadPlan() {
      if (!session) return;
      
      try {
        const data = await thandevFetchJSON<TenantPlanInfo>('/api/tenants/current', session);
        setPlanInfo(data);
      } catch (err) {
        console.error("Error fetching tenant plan info", err);
      }
    }

    loadPlan();
  }, [session]);

  // Cancel scan
  const cancelScan = async (scanId: string) => {
    if (!session) {
      setError('Session required. Please log in again.');
      return;
    }
    
    if (!confirm('Are you sure you want to cancel this scan?')) {
      return;
    }
    
    setCancellingScans(prev => ({ ...prev, [scanId]: true }));
    setError(null);

    try {
      await thandevFetchJSON<Scan>(
        `/api/scans/${scanId}/cancel`,
        session,
        {
          method: 'PATCH',
        }
      );
      
      // Refresh scans to get updated status
      await fetchScans();
      
      alert('Scan cancelled successfully');
    } catch (err) {
      console.error('Error cancelling scan:', err);
      let errorMessage: string;
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        errorMessage = 'Network error: Cannot reach backend. Is the FastAPI server running?';
      } else if (err instanceof Error) {
        errorMessage = err.message;
      } else {
        errorMessage = 'Failed to cancel scan';
      }
      setError(errorMessage);
      alert(`Failed to cancel scan: ${errorMessage}`);
    } finally {
      setCancellingScans(prev => {
        const next = { ...prev };
        delete next[scanId];
        return next;
      });
    }
  };

  // Create scan
  const createScan = async (scanLevel: 'basic' | 'pro' | 'advanced') => {
    if (!session) {
      setError('Session required. Please log in again.');
      return;
    }
    
    setCreatingScan(scanLevel);
    setError(null);

    try {
      const newScan = await thandevFetchJSON<Scan>(
        '/api/scans',
        session,
        {
          method: 'POST',
          body: JSON.stringify({
            project_id: projectId,
            scan_level: scanLevel,
          }),
        }
      );
      
      // Optimistically add to list with 'queued' status
      setScans(prev => [newScan, ...prev]);
      
      // Show success message (simple alert for now)
      const levelName = scanLevel.charAt(0).toUpperCase() + scanLevel.slice(1);
      alert(`${levelName} scan started`);
      
      // Refresh scans after a short delay
      setTimeout(() => {
        fetchScans();
      }, 1000);
    } catch (err) {
      console.error('Error in project scans page (createScan):', err);
      let errorMessage: string;
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        errorMessage = 'Network error: Cannot reach backend. Is the FastAPI server running on port 8000?';
      } else if (err instanceof Error) {
        errorMessage = err.message;
      } else {
        errorMessage = 'Unexpected error while fetching data';
      }
      setError(errorMessage);
      if (errorMessage.toLowerCase().includes('domain not verified')) {
        // Refresh DV status to show latest
        fetchDomainVerification();
      }
    } finally {
      setCreatingScan(null);
    }
  };


  // PDF download handler
  const handleDownloadPdf = async (scanId: string, mode: 'full' | 'executive') => {
    if (!session) {
      alert('Session required. Please log in again.');
      return;
    }
    
    // Update downloading state for this scan
    setDownloadingPdfs(prev => ({
      ...prev,
      [scanId]: {
        ...prev[scanId],
        [mode]: true,
      },
    }));
    
    try {
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
      // Clear downloading state for this scan
      setDownloadingPdfs(prev => ({
        ...prev,
        [scanId]: {
          ...prev[scanId],
          [mode]: false,
        },
      }));
    }
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const renderDomainVerificationBanner = () => {
    const status = dvStatus?.status || 'pending';
    const isVerified = status === 'verified';
    if (dvLoading) {
      return (
        <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4 text-sm text-slate-200">
          Checking domain verification...
        </div>
      );
    }
    if (isVerified) return null;

    return (
      <div className="rounded-xl border border-amber-600/50 bg-amber-900/30 p-4 text-sm text-amber-100 space-y-2">
        <div className="flex items-center justify-between">
          <div className="font-semibold">Domain verification required</div>
          <div className="text-xs uppercase px-2 py-1 rounded bg-amber-800/60 border border-amber-500/60">
            {status}
          </div>
        </div>
        <p className="text-amber-100/90">
          Add the DNS TXT record below, then click &quot;Check verification&quot;. Scans are blocked until verified.
        </p>
        <div className="rounded-lg border border-slate-700 bg-slate-950/70 p-3 text-slate-100 space-y-1">
          <div className="text-xs text-slate-400">Record name</div>
          <div className="font-mono text-sm break-all">{dvStatus?.record_name || '...'}</div>
          <div className="text-xs text-slate-400 pt-2">Record value</div>
          <div className="font-mono text-sm break-all">{dvStatus?.record_value || '...'}</div>
        </div>
        {dvStatus?.last_error && (
          <div className="text-xs text-red-200">Last error: {dvStatus.last_error}</div>
        )}
        <div className="flex items-center gap-2">
          <button
            onClick={fetchDomainVerification}
            className="px-3 py-2 text-sm font-medium rounded-lg bg-slate-800 text-slate-100 border border-slate-600 hover:border-slate-400 transition"
          >
            Check verification
          </button>
          <button
            onClick={async () => {
              if (!session) return;
              setDvLoading(true);
              setDvError(null);
              try {
                await thandevFetchJSON<DomainVerificationStatus>(
                  `/api/projects/${projectId}/domain-verification/request`,
                  session,
                  {
                    method: 'POST',
                    body: JSON.stringify({ force_rotate: true }),
                  }
                );
                await fetchDomainVerification();
              } catch (err) {
                console.error('Error rotating token:', err);
                setDvError(err instanceof Error ? err.message : 'Failed to rotate token');
              } finally {
                setDvLoading(false);
              }
            }}
            className="px-3 py-2 text-sm font-medium rounded-lg bg-slate-900 text-slate-100 border border-slate-700 hover:border-slate-500 transition"
          >
            Regenerate token
          </button>
          {dvError && <span className="text-xs text-red-200">{dvError}</span>}
        </div>
      </div>
    );
  };

  // Get status badge color (dark theme)
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-500/10 text-green-400 border-green-500/20';
      case 'running':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'failed':
        return 'bg-red-500/10 text-red-400 border-red-500/20';
      case 'queued':
        return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
      case 'pending':
        return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
      default:
        return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
    }
  };

  // Get scan level badge color (dark theme)
  const getLevelColor = (level: string) => {
    switch (level) {
      case 'advanced':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'pro':
        return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
      case 'basic':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      default:
        return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
    }
  };

  if (loading && !project) {
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
            <div className="max-w-7xl mx-auto px-6 py-8">
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="rounded-xl border p-6 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                  </div>
                ))}
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (error && !project) {
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
            <div className="max-w-7xl mx-auto px-6 py-8">
              <div className="rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>
                  {error}
                </p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const domainBlocked = !!dvStatus && dvStatus.status !== 'verified';

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
          <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Back link */}
        <Link
          href={`/projects/${projectId}`}
          className="text-sm font-medium hover:opacity-80 transition-opacity inline-block"
          style={{ color: 'var(--brand)' }}
        >
          ← Back to Project Overview
        </Link>

        {/* Domain verification banner */}
        {renderDomainVerificationBanner()}
        
        {/* Project Header Card */}
        {project && (
          <div className="rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{project.name}</h1>
                <p className="mt-1 font-mono text-sm" style={{ color: 'var(--muted)' }}>{project.target_url}</p>
                {project.root_domain && (
                  <p className="text-xs text-slate-500 mt-1">Root domain: {project.root_domain}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Run Scan Card */}
        <div className="rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Run a Scan</h2>
          
          {/* Plan Info Strip */}
          {planInfo && (
            <div className="mb-4 text-sm flex flex-wrap gap-2 items-center" style={{ color: 'var(--muted)' }}>
              <span className="font-semibold">
                Plan: {planInfo.plan.charAt(0).toUpperCase() + planInfo.plan.slice(1)}
              </span>
              <span>·</span>
              <span>Projects {planInfo.usage.projects_count}/{planInfo.usage.projects_max}</span>
              <span>·</span>
              <span>Scans this month {planInfo.usage.scans_this_month}/{planInfo.usage.scans_monthly_max}</span>
              <span>·</span>
              <span>Concurrent {planInfo.usage.concurrent_scans}/{planInfo.usage.concurrent_scans_max}</span>
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-3">
            {(['basic', 'pro', 'advanced'] as const).map((level) => {
              const allowedLevels = planInfo?.limits.allowed_scan_levels ?? [];
              const canRunPro = allowedLevels.includes("pro");
              const canRunAdvanced = allowedLevels.includes("advanced");
              
              // Basic is always allowed, pro/advanced need plan check; domain must be verified
              const isDisabled = domainBlocked || creatingScan !== null || !planInfo || 
                (level === 'pro' && !canRunPro) || 
                (level === 'advanced' && !canRunAdvanced);
              
              const tooltipText = 
                domainBlocked ? "Verify domain to run scans" :
                !planInfo ? "Loading plan info..." :
                level === 'pro' && !canRunPro ? "Upgrade plan to unlock Pro scans" :
                level === 'advanced' && !canRunAdvanced ? "Upgrade plan to unlock Advanced scans" :
                undefined;
              
              // Level descriptions
              const levelDescriptions = {
                basic: {
                  title: "Basic",
                  subtitle: "Fast, limited tools",
                  description: "Quick scan with essential tools (httpx, nuclei). Ideal for quick checks and basic vulnerability detection. Typically completes in 3-8 minutes.",
                  tools: ["httpx", "nuclei"]
                },
                pro: {
                  title: "Pro",
                  subtitle: "More tools, deeper checks",
                  description: "Comprehensive scan with additional tools (ffuf, nmap, sslscan, dalfox). Includes directory discovery, port scanning, and XSS testing. Typically completes in 10-25 minutes.",
                  tools: ["httpx", "nuclei", "ffuf", "nmap", "sslscan", "dalfox"]
                },
                advanced: {
                  title: "Advanced",
                  subtitle: "Full suite, slower, for power users",
                  description: "Complete security scan with all available tools including SQL injection testing (sqlmap). Most thorough but takes longer. Typically completes in 20-45 minutes.",
                  tools: ["httpx", "nuclei", "ffuf", "nmap", "sslscan", "dalfox", "sqlmap"]
                }
              };
              
              const levelInfo = levelDescriptions[level];

              return (
                <div key={level} className="relative group flex-1">
                  <button
                    onClick={() => createScan(level)}
                    disabled={isDisabled}
                    title={tooltipText || levelInfo.description}
                    className={`w-full px-4 py-3 rounded-lg font-medium transition-colors text-left ${
                      isDisabled
                        ? 'opacity-50 cursor-not-allowed'
                        : 'hover:opacity-90'
                    }`}
                    style={isDisabled ? {
                      background: 'var(--surface-2)',
                      color: 'var(--muted)',
                      border: '1px solid var(--border)'
                    } : {
                      background: 'var(--brand)',
                      color: 'white'
                    }}
                  >
                    <div className="flex flex-col gap-1">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold">{levelInfo.title}</span>
                        {creatingScan === level && (
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        )}
                      </div>
                      <span className="text-xs opacity-90">{levelInfo.subtitle}</span>
                    </div>
                  </button>
                  {/* Tooltip on hover */}
                  <div className="absolute left-0 top-full mt-2 z-20 hidden group-hover:block w-80 p-3 rounded-lg border shadow-xl" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <p className="text-xs font-medium mb-1" style={{ color: 'var(--fg)' }}>{levelInfo.title} Scan</p>
                    <p className="text-xs mb-2" style={{ color: 'var(--muted)' }}>{levelInfo.description}</p>
                    <p className="text-xs font-medium mb-1" style={{ color: 'var(--fg)' }}>Tools used:</p>
                    <div className="flex flex-wrap gap-1">
                      {levelInfo.tools.map((tool) => (
                        <span key={tool} className="text-xs px-1.5 py-0.5 rounded bg-[var(--surface-2)] border" style={{ color: 'var(--muted)', borderColor: 'var(--border)' }}>
                          {tool}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="rounded-xl border p-4 mb-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              {error}
            </p>
          </div>
        )}

        {/* Scans Table */}
        <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="p-6 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Scans</h2>
            <button
              onClick={() => {
                setRefreshing(true);
                fetchScans();
              }}
              disabled={refreshing}
              className="px-4 py-2 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              style={{ 
                background: 'var(--surface-2)', 
                color: 'var(--fg)',
                border: '1px solid var(--border)'
              }}
            >
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {loading ? (
            <div className="p-12">
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-16 rounded-lg" style={{ background: 'var(--surface-2)' }}></div>
                  </div>
                ))}
              </div>
            </div>
          ) : scans.length === 0 ? (
            <div className="p-12 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--brand)', opacity: 0.1 }}>
                <svg className="w-8 h-8" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--fg)' }}>
                No scans for this project yet
              </h3>
              <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
                Get started by running your first security scan. Choose a scan level above to begin.
              </p>
            </div>
          ) : error ? (
            <div className="p-6">
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                Could not load scans. Please try again.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead style={{ background: 'var(--surface-2)' }}>
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Level
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Risk Score
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Findings
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Completed
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Actions
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                      Reports
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                  {scans.map((scan, index) => {
                    const riskScore = scan.summary?.risk_score;
                    const findingsCount = scan.summary?.findings_count ?? 0;
                    
                    return (
                      <tr key={`${scan.id}-${index}-${scan.created_at}`} className="hover:opacity-80 transition-opacity" style={{ background: 'var(--surface)' }}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(scan.status)}`}>
                            {scan.status.charAt(0).toUpperCase() + scan.status.slice(1)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getLevelColor(scan.scan_level)}`}>
                            {scan.scan_level.charAt(0).toUpperCase() + scan.scan_level.slice(1)}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                            {riskScore !== null && riskScore !== undefined
                              ? riskScore.toFixed(1)
                              : '–'}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                            {findingsCount}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm" style={{ color: 'var(--muted)' }}>
                          {scan.completed_at ? formatDate(scan.completed_at) : '–'}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <Link
                              href={`/projects/${projectId}/scans/${scan.id}`}
                              className="text-sm font-medium hover:opacity-80 transition-opacity"
                              style={{ color: 'var(--brand)' }}
                            >
                              View
                            </Link>
                            {(scan.status === 'queued' || scan.status === 'running') && (
                              <button
                                onClick={() => cancelScan(scan.id)}
                                disabled={cancellingScans[scan.id]}
                                className="text-sm font-medium hover:opacity-80 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                                style={{ color: 'var(--destructive)' }}
                                title="Cancel scan"
                              >
                                {cancellingScans[scan.id] ? (
                                  <span className="inline-flex items-center gap-1">
                                    <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                                    Cancelling...
                                  </span>
                                ) : (
                                  'Cancel'
                                )}
                              </button>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleDownloadPdf(scan.id, 'full')}
                              disabled={downloadingPdfs[scan.id]?.full || downloadingPdfs[scan.id]?.executive}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              style={{ 
                                background: 'var(--surface-2)', 
                                color: 'var(--fg)',
                                border: '1px solid var(--border)'
                              }}
                              title="Download Full PDF Report"
                            >
                              {downloadingPdfs[scan.id]?.full ? (
                                <>
                                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                                  <span>Preparing...</span>
                                </>
                              ) : (
                                'Full PDF'
                              )}
                            </button>
                            <button
                              onClick={() => handleDownloadPdf(scan.id, 'executive')}
                              disabled={downloadingPdfs[scan.id]?.full || downloadingPdfs[scan.id]?.executive}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              style={{ 
                                background: 'var(--surface-2)', 
                                color: 'var(--fg)',
                                border: '1px solid var(--border)'
                              }}
                              title="Download Executive Summary PDF"
                            >
                              {downloadingPdfs[scan.id]?.executive ? (
                                <>
                                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                                  <span>Preparing...</span>
                                </>
                              ) : (
                                'Executive PDF'
                              )}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
          </div>
        </main>
      </div>
    </div>
  );
}
