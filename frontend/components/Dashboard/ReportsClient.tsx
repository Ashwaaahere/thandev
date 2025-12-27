'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { thandevFetchJSON, thandevFetchPDF } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

// Types
type ScanItem = {
  id: string;
  project_id: string;
  project_name?: string | null;
  target_url?: string | null;
  scan_level: string;
  status: string;
  risk_score?: number | null;
  findings_count?: number;
  completed_at?: string | null;
  created_at: string;
};

type ScansResponse = {
  items: ScanItem[];
  total: number;
};

type ProjectListItem = {
  id: string;
  name: string;
  target_url?: string | null;
};

// Status badge component for scan status
function ScanStatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const base = 'px-2 py-0.5 rounded-full text-xs font-medium';
  
  switch (normalized) {
    case 'completed':
      return (
        <span className={`${base} bg-green-500/10 text-green-400 border border-green-500/20`}>
          Completed
        </span>
      );
    case 'running':
    case 'queued':
      return (
        <span className={`${base} bg-blue-500/10 text-blue-400 border border-blue-500/20`}>
          {normalized === 'running' ? 'Running' : 'Queued'}
        </span>
      );
    case 'failed':
    case 'error':
      return (
        <span className={`${base} bg-red-500/10 text-red-400 border border-red-500/20`}>
          Failed
        </span>
      );
    case 'pending':
      return (
        <span className={`${base} bg-gray-500/10 text-gray-400 border border-gray-500/20`}>
          Pending
        </span>
      );
    default:
      return (
        <span className={`${base} bg-gray-500/10 text-gray-400 border border-gray-500/20`}>
          {status}
        </span>
      );
  }
}

// Level badge component
function LevelBadge({ level }: { level: string }) {
  const normalized = level.toLowerCase();
  let className = 'px-2 py-0.5 rounded-full text-xs font-medium border';
  
  switch (normalized) {
    case 'advanced':
      className += ' bg-purple-500/10 text-purple-400 border-purple-500/20';
      return <span className={className}>Advanced</span>;
    case 'pro':
      className += ' bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
      return <span className={className}>Pro</span>;
    case 'basic':
      className += ' bg-blue-500/10 text-blue-400 border-blue-500/20';
      return <span className={className}>Basic</span>;
    default:
      className += ' bg-gray-500/10 text-gray-400 border-gray-500/20';
      return <span className={className}>{level}</span>;
  }
}

export default function ReportsClient() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [allScans, setAllScans] = useState<ScanItem[]>([]);
  const [scans, setScans] = useState<ScanItem[]>([]);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedProjectId, setSelectedProjectId] = useState<string>('all');
  const [selectedLevel, setSelectedLevel] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [search, setSearch] = useState('');
  
  // PDF download state per scan: { scanId: { full: boolean, executive: boolean } }
  const [downloadingPdfs, setDownloadingPdfs] = useState<Record<string, { full: boolean; executive: boolean }>>({});

  const loadProjects = useCallback(async () => {
    if (!session) return;
    
    try {
      const res = await thandevFetchJSON<{ items: ProjectListItem[] }>(
        '/api/projects',
        session
      );
      setProjects(res.items ?? []);
    } catch (err) {
      // Fail soft; reports can still load
      console.error('Failed to load projects', err);
    }
  }, [session]);

  const loadScans = useCallback(async () => {
    if (!session) return;
    
    setLoading(true);
    setError(null);

    try {
      // Fetch all scans with pagination (backend max limit is 100)
      const allScansData: ScanItem[] = [];
      let offset = 0;
      const limit = 100; // Backend maximum
      let hasMore = true;

      while (hasMore) {
        const params = new URLSearchParams();
        params.set('limit', limit.toString());
        params.set('offset', offset.toString());

        const url = `/api/scans?${params.toString()}`;
        const res = await thandevFetchJSON<ScansResponse>(url, session);
        
        if (res.items && res.items.length > 0) {
          allScansData.push(...res.items);
          offset += res.items.length;
          // If we got fewer items than the limit, we've reached the end
          hasMore = res.items.length === limit;
        } else {
          hasMore = false;
        }
      }

      setAllScans(allScansData);
    } catch (err: any) {
      console.error('Failed to load reports', err);
      setError(err?.message || 'Failed to load reports.');
    } finally {
      setLoading(false);
    }
  }, [session]);

  // Apply filters client-side
  useEffect(() => {
    let filtered = [...allScans];

    // Filter by project
    if (selectedProjectId !== 'all') {
      filtered = filtered.filter(scan => scan.project_id === selectedProjectId);
    }

    // Filter by level
    if (selectedLevel !== 'all') {
      filtered = filtered.filter(scan => scan.scan_level.toLowerCase() === selectedLevel.toLowerCase());
    }

    // Filter by status
    if (selectedStatus !== 'all') {
      filtered = filtered.filter(scan => scan.status.toLowerCase() === selectedStatus.toLowerCase());
    }

    // Filter by search (URL or scan ID)
    if (search.trim()) {
      const searchLower = search.trim().toLowerCase();
      filtered = filtered.filter(scan => 
        (scan.target_url?.toLowerCase().includes(searchLower)) ||
        scan.id.toLowerCase().includes(searchLower)
      );
    }

    setScans(filtered);
  }, [allScans, selectedProjectId, selectedLevel, selectedStatus, search]);

  useEffect(() => {
    if (sessionStatus === 'unauthenticated') {
      router.push('/auth/signin');
      return;
    }
    if (sessionStatus !== 'authenticated') return;
    loadProjects();
  }, [sessionStatus, loadProjects, router]);

  useEffect(() => {
    if (sessionStatus !== 'authenticated') return;
    loadScans();
  }, [sessionStatus, loadScans]);

  // PDF download handler
  const handleDownloadPdf = async (scanId: string, mode: 'full' | 'executive') => {
    if (!session) {
      setError('Session required. Please log in again.');
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
      setError(e instanceof Error ? e.message : 'Failed to download PDF. Please try again.');
      setTimeout(() => setError(null), 5000);
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

  // Use formatDateTime from lib/formatDate.ts for consistent timezone handling

  const clearFilters = () => {
    setSelectedProjectId('all');
    setSelectedLevel('all');
    setSelectedStatus('all');
    setSearch('');
  };

  // Loading state
  if (sessionStatus === 'loading') {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader 
            user={undefined} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
              <div className="space-y-4">
                {[...Array(4)].map((_, i) => (
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

  // Unauthenticated state (will redirect)
  if (sessionStatus === 'unauthenticated') {
    router.push('/auth');
    return null;
  }

  if (!session) {
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader 
          user={session.user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                Reports
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                Access detailed security scan reports.
              </p>
            </div>

            {/* Filters */}
            <div className="mb-6 p-6 rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                {/* Project Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Project
                  </label>
                  <select
                    value={selectedProjectId}
                    onChange={(e) => setSelectedProjectId(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="all">All projects</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Level Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Level
                  </label>
                  <select
                    value={selectedLevel}
                    onChange={(e) => setSelectedLevel(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="all">All levels</option>
                    <option value="basic">Basic</option>
                    <option value="pro">Pro</option>
                    <option value="advanced">Advanced</option>
                  </select>
                </div>

                {/* Status Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Status
                  </label>
                  <select
                    value={selectedStatus}
                    onChange={(e) => setSelectedStatus(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="all">All</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="running">Running</option>
                    <option value="queued">Queued</option>
                    <option value="pending">Pending</option>
                  </select>
                </div>

                {/* Search */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Search
                  </label>
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by URL or scan ID…"
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={loadScans}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
                  style={{ background: 'var(--brand)', color: 'white' }}
                >
                  Apply filters
                </button>
                <button
                  onClick={() => {
                    clearFilters();
                    // Trigger reload after clearing
                    setTimeout(() => loadScans(), 0);
                  }}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-80"
                  style={{
                    background: 'var(--surface-2)',
                    color: 'var(--fg)',
                    border: '1px solid var(--border)'
                  }}
                >
                  Clear filters
                </button>
              </div>
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mb-6 p-4 rounded-lg border border-red-500/50 bg-red-500/10">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-red-400">{error}</p>
                  <button
                    onClick={() => {
                      setError(null);
                      loadScans();
                    }}
                    className="ml-4 px-3 py-1 rounded text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors"
                  >
                    Retry
                  </button>
                </div>
              </div>
            )}

            {/* Reports Table */}
            <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              {loading ? (
                <div className="p-6">
                  <div className="animate-pulse space-y-4">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="h-16 rounded-lg" style={{ background: 'var(--surface-2)' }}></div>
                    ))}
                  </div>
                </div>
              ) : scans.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                    <svg className="w-12 h-12" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>
                    No reports yet
                  </h3>
                  <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
                    Run a scan from the Security Scanner to generate your first report.
                  </p>
                  <Link
                    href="/dashboard/scan"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
                    style={{ background: 'var(--brand)' }}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                    </svg>
                    Run Security Scan
                  </Link>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead style={{ background: 'var(--surface-2)' }}>
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                          Project
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                          Target
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                          Level
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                          Status
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
                        <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                      {scans.map((scan) => (
                        <tr key={scan.id} className="hover:opacity-80 transition-opacity" style={{ background: 'var(--surface)' }}>
                          <td className="px-6 py-4">
                            <Link
                              href={`/projects/${scan.project_id}`}
                              className="text-sm font-medium hover:opacity-80 transition-opacity"
                              style={{ color: 'var(--brand)' }}
                            >
                              {scan.project_name || 'Unknown Project'}
                            </Link>
                          </td>
                          <td className="px-6 py-4">
                            <span className="text-sm font-mono" style={{ color: 'var(--fg)' }}>
                              {scan.target_url || '–'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <LevelBadge level={scan.scan_level} />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <ScanStatusBadge status={scan.status} />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                              {scan.risk_score !== null && scan.risk_score !== undefined
                                ? scan.risk_score.toFixed(1)
                                : '–'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                              {scan.findings_count ?? 0}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className="text-sm" style={{ color: 'var(--muted)' }}>
                              {formatDateTime(scan.completed_at)}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Link
                                href={`/projects/${scan.project_id}/scans/${scan.id}`}
                                className="text-xs font-medium hover:opacity-80 transition-opacity"
                                style={{ color: 'var(--brand)' }}
                              >
                                View details
                              </Link>
                              <button
                                onClick={() => handleDownloadPdf(scan.id, 'full')}
                                disabled={downloadingPdfs[scan.id]?.full || downloadingPdfs[scan.id]?.executive}
                                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                      ))}
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




