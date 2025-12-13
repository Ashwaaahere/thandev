'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Session } from 'next-auth';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';

// Types matching backend response
type LatestScanTool = {
  tool_name: string;
  exit_code: number | null;
};

type ProjectOverviewStats = {
  total_scans: number;
  last_scan_at: string | null;
  last_scan_status: string | null;
  last_risk_score: number | null;
  open_findings_total: number;
  open_findings_by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  tools_used: string[];
  latest_scan_tools: LatestScanTool[];
};

type ProjectOverview = {
  id: string;
  name: string;
  target_url: string;
  created_at: string;
  stats: ProjectOverviewStats;
};

type ScanListItem = {
  id: string;
  project_id: string;
  scan_level: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  summary?: {
    risk_score?: number | null;
    findings_count?: number | null;
  } | null;
};

interface ProjectOverviewClientProps {
  projectId: string;
  session: Session | null;
}

export default function ProjectOverviewClient({ projectId, session }: ProjectOverviewClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [overview, setOverview] = useState<ProjectOverview | null>(null);
  const [recentScans, setRecentScans] = useState<ScanListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadOverview() {
      if (!session) return;
      
      setLoading(true);
      setError(null);

      try {
        const data = await thandevFetchJSON<ProjectOverview>(
          `/api/projects/${projectId}/overview`,
          session
        );

        if (!cancelled) {
          setOverview(data);
        }
      } catch (e) {
        console.error('Error loading project overview:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load project overview');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadOverview();

    return () => {
      cancelled = true;
    };
  }, [projectId, session]);

  useEffect(() => {
    let cancelled = false;

    async function loadRecentScans() {
      if (!session) return;
      
      try {
        const data = await thandevFetchJSON<{ items: ScanListItem[]; total: number }>(
          `/api/scans/project/${projectId}?limit=5`,
          session
        );

        if (!cancelled && data.items) {
          setRecentScans(data.items);
        }
      } catch (e) {
        console.error('Error loading recent scans:', e);
        // Silently fail, recent scans are optional
      }
    }

    if (projectId) {
      loadRecentScans();
    }

    return () => {
      cancelled = true;
    };
  }, [projectId, session]);

  // Use formatDateTime from lib/formatDate.ts for consistent timezone handling

  const getStatusColor = (status: string | null) => {
    if (!status) return 'text-slate-400';
    const s = status.toLowerCase();
    if (s === 'completed') return 'text-emerald-400';
    if (s === 'running' || s === 'queued') return 'text-blue-400';
    if (s === 'failed') return 'text-red-400';
    return 'text-slate-400';
  };

  const getSeverityColor = (severity: string) => {
    const s = severity.toLowerCase();
    if (s === 'critical') return 'text-red-400';
    if (s === 'high') return 'text-orange-400';
    if (s === 'medium') return 'text-yellow-400';
    if (s === 'low') return 'text-green-400';
    return 'text-slate-400';
  };

  const getLevelColor = (level: string) => {
    const l = level.toLowerCase();
    if (l === 'advanced') return 'bg-purple-900/40 text-purple-200 border-purple-500/50';
    if (l === 'pro') return 'bg-indigo-900/40 text-indigo-200 border-indigo-500/50';
    return 'bg-blue-900/40 text-blue-200 border-blue-500/50';
  };

  if (loading) {
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
            <div className="max-w-6xl mx-auto px-6 py-8">
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

  if (error || !overview) {
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
            <div className="max-w-6xl mx-auto px-6 py-8">
              <div className="rounded-xl border p-6 mb-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>
                  {error || 'Project not found'}
                </p>
              </div>
              <Link
                href="/projects"
                className="text-sm font-medium hover:opacity-80 transition-opacity"
                style={{ color: 'var(--brand)' }}
              >
                ← Back to Projects
              </Link>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const securityPosture = overview.stats.last_risk_score !== null && overview.stats.last_risk_score !== undefined
    ? overview.stats.last_risk_score < 30
      ? 'Excellent'
      : overview.stats.last_risk_score < 60
      ? 'Good'
      : overview.stats.last_risk_score < 80
      ? 'Fair'
      : 'Needs Attention'
    : 'Not Assessed';

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
        <main className="flex-1 overflow-y-auto p-6 bg-slate-950 text-slate-100">
          <div className="mx-auto max-w-6xl px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Project</p>
            <h1 className="mt-1 text-2xl font-semibold text-slate-50">{overview.name}</h1>
            {overview.target_url && (
              <p className="mt-1 text-sm text-slate-400 font-mono">{overview.target_url}</p>
            )}
          </div>
          <div className="flex items-center gap-3">
            <Link
              href={`/projects/${projectId}/scans`}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ background: 'var(--brand)' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Run quick scan
            </Link>
            <Link
              href={`/projects/${projectId}/scans`}
              className="inline-flex items-center rounded-full border border-slate-700 bg-slate-900/70 px-3 py-1.5 text-xs font-medium text-slate-100 hover:border-slate-500 hover:bg-slate-900 transition-colors"
            >
              View scans history
            </Link>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg shadow-black/30">
            <p className="text-xs text-slate-400">Total scans</p>
            <p className="mt-2 text-2xl font-semibold text-slate-50">{overview.stats.total_scans}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg shadow-black/30">
            <p className="text-xs text-slate-400">Open findings</p>
            <p className="mt-2 text-2xl font-semibold text-slate-50">{overview.stats.open_findings_total}</p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg shadow-black/30">
            <p className="text-xs text-slate-400">Last risk score</p>
            <p className="mt-2 text-2xl font-semibold text-slate-50">
              {overview.stats.last_risk_score !== null && overview.stats.last_risk_score !== undefined
                ? overview.stats.last_risk_score.toFixed(1)
                : 'N/A'}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg shadow-black/30">
            <p className="text-xs text-slate-400">Last scan</p>
            <p className="mt-2 text-sm font-medium text-slate-50">
              {overview.stats.last_scan_at ? formatDateTime(overview.stats.last_scan_at) : 'No scans yet'}
            </p>
            {overview.stats.last_scan_status && (
              <p className={`mt-1 text-xs ${getStatusColor(overview.stats.last_scan_status)}`}>
                {overview.stats.last_scan_status}
              </p>
            )}
          </div>
        </div>

        {/* Security engines row */}
        {overview.stats.latest_scan_tools && overview.stats.latest_scan_tools.length > 0 && (
          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4 shadow-lg shadow-black/30">
            <div className="flex items-center justify-between">
              <p className="text-xs text-slate-400 mb-0">Security engines</p>
              <div className="flex items-center gap-2">
                {overview.stats.latest_scan_tools.map((tool) => {
                  const toolName = tool.tool_name.charAt(0).toUpperCase() + tool.tool_name.slice(1);
                  const isSuccess = tool.exit_code === 0;
                  const hasError = tool.exit_code !== null && tool.exit_code !== 0;
                  const isUnknown = tool.exit_code === null;
                  
                  // Color based on exit code: green (0), yellow (null/unknown), red (non-zero)
                  let badgeClass = 'px-2.5 py-1 text-xs font-medium rounded-full border cursor-pointer transition-opacity hover:opacity-80';
                  if (isSuccess) {
                    badgeClass += ' bg-emerald-900/40 text-emerald-200 border-emerald-500/50';
                  } else if (hasError) {
                    badgeClass += ' bg-red-900/40 text-red-200 border-red-500/50';
                  } else {
                    badgeClass += ' bg-amber-900/40 text-amber-200 border-amber-500/50';
                  }
                  
                  return (
                    <Link
                      key={tool.tool_name}
                      href={`/dashboard/vulnerabilities?projectId=${projectId}&tool=${tool.tool_name}`}
                      className={badgeClass}
                    >
                      {toolName}
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Two-column main content */}
        <div className="grid gap-6 md:grid-cols-3">
          {/* Left column */}
          <div className="md:col-span-2 space-y-6">
            {/* Security posture card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 shadow-lg shadow-black/30 p-6">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Security Posture</h2>
              <div className="space-y-3">
                <div>
                  <p className="text-sm text-slate-400 mb-1">Overall Status</p>
                  <p className="text-xl font-semibold text-slate-50">{securityPosture}</p>
                </div>
                {overview.stats.last_risk_score !== null && overview.stats.last_risk_score !== undefined && (
                  <div>
                    <p className="text-sm text-slate-400 mb-1">Risk Score</p>
                    <p className="text-2xl font-bold text-slate-50">{overview.stats.last_risk_score.toFixed(1)}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Lower is better (0 = no issues, 100 = critical issues)
                    </p>
                  </div>
                )}
                {overview.stats.open_findings_total > 0 && (
                  <div>
                    <p className="text-sm text-slate-400 mb-2">Open Findings</p>
                    <p className="text-sm text-slate-300">
                      {overview.stats.open_findings_total} finding{overview.stats.open_findings_total !== 1 ? 's' : ''} detected across all scans.
                      {overview.stats.open_findings_by_severity.critical > 0 && (
                        <span className="text-red-400 ml-1">
                          {overview.stats.open_findings_by_severity.critical} critical
                        </span>
                      )}
                    </p>
                  </div>
                )}
                {overview.stats.open_findings_total === 0 && (
                  <p className="text-sm text-emerald-400">No open findings detected.</p>
                )}
              </div>
            </div>

            {/* Recent scans card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 shadow-lg shadow-black/30 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-slate-100">Recent Scans</h2>
                <Link
                  href={`/projects/${projectId}/scans`}
                  className="text-xs text-indigo-400 hover:text-indigo-300 underline"
                >
                  View all →
                </Link>
              </div>
              {recentScans.length === 0 ? (
                <div className="text-sm text-slate-400 text-center py-8">
                  No scans yet. <Link href={`/projects/${projectId}/scans`} className="text-indigo-400 hover:text-indigo-300 underline">Start your first scan</Link>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentScans.map((scan) => {
                    const riskScore = scan.summary?.risk_score;
                    const findingsCount = scan.summary?.findings_count ?? 0;
                    
                    return (
                      <Link
                        key={scan.id}
                        href={`/projects/${projectId}/scans/${scan.id}`}
                        className="block p-4 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-900/60 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3 mb-2">
                              <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getLevelColor(scan.scan_level)}`}>
                                {scan.scan_level.toUpperCase()}
                              </span>
                              <span className={`text-xs ${getStatusColor(scan.status)}`}>
                                {scan.status}
                              </span>
                            </div>
                            <p className="text-xs text-slate-400">{formatDateTime(scan.created_at)}</p>
                          </div>
                          <div className="text-right">
                            {riskScore !== null && riskScore !== undefined && (
                              <p className="text-sm font-semibold text-slate-100">{riskScore.toFixed(1)}</p>
                            )}
                            <p className="text-xs text-slate-400">{findingsCount} findings</p>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-6">
            {/* Findings overview card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 shadow-lg shadow-black/30 p-6">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Findings Overview</h2>
              <div className="space-y-3">
                {(['critical', 'high', 'medium', 'low', 'info'] as const).map((severity) => {
                  const count = overview.stats.open_findings_by_severity[severity] || 0;
                  return (
                    <div key={severity} className="flex items-center justify-between">
                      <span className={`text-sm font-medium capitalize ${getSeverityColor(severity)}`}>
                        {severity}
                      </span>
                      <span className="text-sm font-semibold text-slate-100">{count}</span>
                    </div>
                  );
                })}
              </div>
              {overview.stats.open_findings_total === 0 && (
                <p className="mt-4 text-xs text-slate-400 text-center">No findings detected</p>
              )}
            </div>

            {/* Tools used card */}
            <div className="rounded-2xl border border-slate-800 bg-slate-950/60 shadow-lg shadow-black/30 p-6">
              <h2 className="text-lg font-semibold text-slate-100 mb-4">Tools Used</h2>
              {overview.stats.tools_used.length === 0 ? (
                <p className="text-sm text-slate-400">No tools have been used yet</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {overview.stats.tools_used.map((tool) => (
                    <span
                      key={tool}
                      className="inline-flex items-center rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1 text-xs font-medium text-slate-200"
                    >
                      {tool.toUpperCase()}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
          </div>
        </main>
      </div>
    </div>
  );
}


