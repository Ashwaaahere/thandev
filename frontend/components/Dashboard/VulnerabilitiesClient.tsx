'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Session } from 'next-auth';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatCategory, getAllCategories, VULN_CATEGORY_LABELS } from '@/lib/vulnCategories';

// Types matching backend response
type FindingStatus = "open" | "acknowledged" | "resolved" | "suppressed";

type FindingListItem = {
  id: string;
  scan_id: string;
  project_id: string;
  project_name: string;
  target_url: string;
  severity: string;
  status: FindingStatus;
  title: string;
  description?: string | null;
  cve_id?: string | null;
  cwe_id?: string | null;
  cvss_score?: number | null;
  tool?: string | null;
  categories?: string[] | null;
  url?: string | null;
  path?: string | null;
  first_seen: string;
  last_seen: string;
};

type FindingListResponse = {
  items: FindingListItem[];
  total: number;
};

type ProjectWithStats = {
  id: string;
  name: string;
  target_url?: string | null;
};

type ProjectListResponse = {
  items: ProjectWithStats[];
  total: number;
};

interface VulnerabilitiesClientProps {
  initialProjectId?: string;
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
        <span className={`${base} border-gray-500/60 bg-gray-900/60 text-gray-200`}>
          {normalized}
        </span>
      );
  }
}

export default function VulnerabilitiesClient({ initialProjectId }: VulnerabilitiesClientProps) {
  const { data: session, status: sessionStatus } = useSession();
  const searchParams = useSearchParams();
  const initialSearch = searchParams.get('search') ?? '';
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [findings, setFindings] = useState<FindingListItem[]>([]);
  const [projects, setProjects] = useState<ProjectWithStats[]>([]);
  const [total, setTotal] = useState(0);
  const [severity, setSeverity] = useState<string | null>(null);
  const [selectedTool, setSelectedTool] = useState<'all' | 'nuclei' | 'nmap' | 'sslscan' | 'http_headers'>('all');
  const [selectedStatus, setSelectedStatus] = useState<'all' | FindingStatus>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [search, setSearch] = useState(initialSearch);
  const [projectId, setProjectId] = useState<string | undefined>(initialProjectId);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);
  const [toolCounts, setToolCounts] = useState<Map<string, number>>(new Map());
  const limit = 20;

  // Sync URL params with state
  useEffect(() => {
    const urlSearch = searchParams.get('search') ?? '';
    const urlProjectId = searchParams.get('projectId') ?? undefined;
    const urlTool = searchParams.get('tool') ?? 'all';
    
    if (urlSearch !== search) {
      setSearch(urlSearch);
      setPage(0);
    }
    
    if (urlProjectId && urlProjectId !== projectId) {
      setProjectId(urlProjectId);
      setPage(0);
    }
    
    if (urlTool !== 'all' && urlTool !== selectedTool) {
      const validTool = ['nuclei', 'nmap', 'sslscan', 'http_headers'].includes(urlTool) ? urlTool as 'nuclei' | 'nmap' | 'sslscan' | 'http_headers' : 'all';
      setSelectedTool(validTool);
      setPage(0);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Load projects for filter dropdown
  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      if (sessionStatus !== 'authenticated' || !session) return;
      
      try {
        const data = await thandevFetchJSON<ProjectListResponse>('/api/projects', session);
        if (!cancelled) {
          setProjects(data.items || []);
        }
      } catch (e) {
        console.error('Error loading projects:', e);
        // Silently fail - projects filter is optional
      }
    }

    loadProjects();
    return () => {
      cancelled = true;
    };
  }, [sessionStatus, session]);

  useEffect(() => {
    if (sessionStatus !== 'authenticated' || !session) return;
    
    let cancelled = false;

    async function loadFindings() {
      setIsLoading(true);
      setError(null);
      
      try {
        const params = new URLSearchParams();
        params.append('limit', limit.toString());
        params.append('offset', (page * limit).toString());
        if (severity) {
          params.append('severity', severity);
        }
        if (selectedTool !== 'all') {
          params.append('tool', selectedTool);
        }
        if (selectedStatus !== 'all') {
          params.append('status', selectedStatus);
        }
        if (search.trim()) {
          params.append('search', search.trim());
        }
        if (projectId) {
          params.append('project_id', projectId);
        }
        if (selectedCategory !== 'all') {
          params.append('category', selectedCategory);
        }

        const data = await thandevFetchJSON<FindingListResponse>(
          `/api/findings?${params.toString()}`,
          session
        );
        
        if (!cancelled) {
          setFindings(data.items);
          setTotal(data.total);
          
          // Compute tool counts from all findings (not just current page)
          // Only fetch counts when filters change (not on pagination)
          if (page === 0) {
            const allParams = new URLSearchParams();
            if (severity) allParams.append('severity', severity);
            if (selectedStatus !== 'all') allParams.append('status', selectedStatus);
            if (search.trim()) allParams.append('search', search.trim());
            if (projectId) allParams.append('project_id', projectId);
            if (selectedCategory !== 'all') allParams.append('category', selectedCategory);
            allParams.append('limit', '1000'); // Get a large sample for counts
            
            try {
              const allData = await thandevFetchJSON<FindingListResponse>(
                `/api/findings?${allParams.toString()}`,
                session
              );
              
              const counts = new Map<string, number>();
              allData.items.forEach((finding) => {
                if (finding.tool) {
                  const tool = finding.tool.toLowerCase();
                  counts.set(tool, (counts.get(tool) || 0) + 1);
                }
              });
              setToolCounts(counts);
            } catch (e) {
              // Silently fail - tool counts are optional
              console.error('Error computing tool counts:', e);
            }
          }
        }
      } catch (e) {
        console.error('Error loading findings:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load vulnerabilities');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    // Debounce search
    const timeoutId = setTimeout(() => {
      loadFindings();
    }, search ? 300 : 0);

    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [severity, selectedTool, selectedStatus, selectedCategory, search, projectId, page, sessionStatus, session]);

  // Status update handler
  const updateStatus = async (findingId: string, newStatus: FindingStatus) => {
    if (!session) {
      setError('Session required. Please log in again.');
      return;
    }
    
    setUpdatingStatus(findingId);
    try {
      const updated = await thandevFetchJSON<FindingListItem>(
        `/api/findings/${findingId}/status`,
        session,
        {
          method: 'PATCH',
          body: JSON.stringify({ status: newStatus }),
        }
      );
      
      // Update local state
      setFindings((prev) =>
        prev.map((f) => (f.id === updated.id ? { ...f, status: updated.status } : f))
      );
    } catch (e) {
      console.error('Error updating status:', e);
      setError(e instanceof Error ? e.message : 'Failed to update status');
      // Clear error after 3 seconds
      setTimeout(() => setError(null), 3000);
    } finally {
      setUpdatingStatus(null);
    }
  };

  const getSeverityColor = (severity: string) => {
    const s = severity.toLowerCase();
    switch (s) {
      case 'critical':
        return 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/20';
      case 'high':
        return 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-900/20';
      case 'medium':
        return 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/20';
      case 'low':
        return 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/20';
      case 'info':
        return 'text-slate-600 bg-slate-100 dark:text-slate-400 dark:bg-slate-900/20';
      default:
        return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20';
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const severityOptions = [
    { value: null, label: 'All' },
    { value: 'critical', label: 'Critical' },
    { value: 'high', label: 'High' },
    { value: 'medium', label: 'Medium' },
    { value: 'low', label: 'Low' },
    { value: 'info', label: 'Info' },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      
      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <DashboardHeader 
          user={session?.user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        
        {/* Vulnerabilities Content */}
        <main className="flex-1 overflow-y-auto" style={{ background: 'var(--bg)' }}>
          <div className="container mx-auto px-6 py-8">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                Vulnerabilities
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                Track and triage findings across all projects
              </p>
            </div>

            {/* Filters */}
            <div className="mb-6 p-6 rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
                {/* Severity Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Severity
                  </label>
                  <select
                    value={severity || ''}
                    onChange={(e) => {
                      setSeverity(e.target.value || null);
                      setPage(0);
                    }}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="">All severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                    <option value="info">Info</option>
                  </select>
                </div>

                {/* Status Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Status
                  </label>
                  <select
                    value={selectedStatus}
                    onChange={(e) => {
                      setSelectedStatus(e.target.value as 'all' | FindingStatus);
                      setPage(0);
                    }}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="all">All statuses</option>
                    <option value="open">Open</option>
                    <option value="acknowledged">Acknowledged</option>
                    <option value="resolved">Resolved</option>
                    <option value="suppressed">Suppressed</option>
                  </select>
                </div>

                {/* Project Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Project
                  </label>
                  <select
                    value={projectId || ''}
                    onChange={(e) => {
                      setProjectId(e.target.value || undefined);
                      setPage(0);
                    }}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="">All projects</option>
                    {projects.map((project) => (
                      <option key={project.id} value={project.id}>
                        {project.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Tool Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Tool
                  </label>
                  <select
                    value={selectedTool}
                    onChange={(e) => {
                      setSelectedTool(e.target.value as 'all' | 'nuclei' | 'nmap' | 'sslscan' | 'http_headers');
                      setPage(0);
                    }}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="all">All tools</option>
                    <option value="nuclei">Nuclei</option>
                    <option value="nmap">Nmap</option>
                    <option value="sslscan">SSLScan</option>
                  </select>
                </div>

                {/* Category Filter */}
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                    Category
                  </label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => {
                      setSelectedCategory(e.target.value);
                      setPage(0);
                    }}
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  >
                    <option value="all">All categories</option>
                    {getAllCategories().map((cat) => (
                      <option key={cat} value={cat}>
                        {formatCategory(cat)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Search Input */}
              <div className="mb-4">
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                  Search
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPage(0);
                    }}
                    placeholder="Search by title, CVE, CWE, URL, or path…"
                    className="w-full px-4 py-2 pl-10 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                    style={{
                      borderColor: 'var(--border)',
                      background: 'var(--surface-2)',
                      color: 'var(--fg)'
                    }}
                  />
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Clear Filters Button */}
              {(severity || selectedStatus !== 'all' || selectedTool !== 'all' || selectedCategory !== 'all' || projectId || search.trim()) && (
                <div>
                  <button
                    onClick={() => {
                      setSeverity(null);
                      setSelectedStatus('all');
                      setSelectedTool('all');
                      setSelectedCategory('all');
                      setProjectId(undefined);
                      setSearch('');
                      setPage(0);
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
              )}
            </div>

            {/* Error Banner */}
            {error && (
              <div className="mb-6 p-4 rounded-lg border border-red-500/50 bg-red-500/10">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-red-400">{error}</p>
                  <button
                    onClick={() => {
                      setError(null);
                      // Trigger reload by updating a dependency
                      setPage(0);
                    }}
                    className="ml-4 px-3 py-1 rounded text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors"
                  >
                    Retry
                  </button>
                </div>
              </div>
            )}

            {/* By Tool Chip Row */}
            {toolCounts.size > 0 && (
              <div className="mb-4">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium" style={{ color: 'var(--muted)' }}>By Tool:</span>
                  <button
                    onClick={() => {
                      setSelectedTool('all');
                      setPage(0);
                    }}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                      selectedTool === 'all'
                        ? 'bg-[var(--brand)]/20 text-[var(--brand)] border-[var(--brand)]/50'
                        : 'bg-[var(--surface-2)] text-[var(--fg)] border-[var(--border)] hover:bg-[var(--surface)]'
                    }`}
                  >
                    All ({total})
                  </button>
                  {Array.from(toolCounts.entries())
                    .sort((a, b) => b[1] - a[1])
                    .map(([tool, count]) => {
                      const toolKey = tool.toLowerCase() as 'nuclei' | 'nmap' | 'sslscan' | 'http_headers';
                      const isValidTool = ['nuclei', 'nmap', 'sslscan', 'http_headers'].includes(toolKey);
                      if (!isValidTool) return null;
                      
                      // Format tool name for display
                      let toolName = tool.charAt(0).toUpperCase() + tool.slice(1);
                      if (toolKey === 'http_headers') {
                        toolName = 'HTTP Headers';
                      }
                      const isSelected = selectedTool === toolKey;
                      
                      return (
                        <button
                          key={tool}
                          onClick={() => {
                            setSelectedTool(toolKey);
                            setPage(0);
                          }}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                            isSelected
                              ? 'bg-[var(--brand)]/20 text-[var(--brand)] border-[var(--brand)]/50'
                              : 'bg-[var(--surface-2)] text-[var(--fg)] border-[var(--border)] hover:bg-[var(--surface)]'
                          }`}
                        >
                          {toolName} ({count})
                        </button>
                      );
                    })}
                </div>
              </div>
            )}

            {/* Findings Table */}
            <div className="rounded-2xl border shadow-lg overflow-hidden" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              {isLoading ? (
                <div className="p-6">
                  <div className="animate-pulse space-y-4">
                    {[...Array(5)].map((_, i) => (
                      <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
                    ))}
                  </div>
                </div>
              ) : findings.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                    <svg className="w-12 h-12" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>
                    No vulnerabilities found yet
                  </h3>
                  <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
                    Run a scan from Projects to start generating security findings.
                  </p>
                  <Link
                    href="/projects"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
                    style={{ background: 'var(--brand)' }}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                    View Projects
                  </Link>
                </div>
              ) : (
                <>
                  {/* Table Header */}
                  <div className="px-6 py-4 border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                    <div className="flex items-center justify-between">
                      <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
                        Findings ({total})
                      </h2>
                    </div>
                  </div>

                  {/* Table Content */}
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b" style={{ borderColor: 'var(--border)' }}>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Severity
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Finding
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Project
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Tool
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            CVSS
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Status
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Detected
                          </th>
                          <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                            Actions
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                        {findings.map((finding) => (
                          <tr key={finding.id} className="hover:bg-opacity-50 transition-colors" style={{ background: 'var(--surface)' }}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getSeverityColor(finding.severity)}`}>
                                {finding.severity.charAt(0).toUpperCase() + finding.severity.slice(1)}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex flex-col">
                                <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                                  {finding.title}
                                </span>
                                {(finding.cve_id || finding.cwe_id) && (
                                  <div className="flex gap-2 mt-1">
                                    {finding.cve_id && (
                                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                                        CVE: {finding.cve_id}
                                      </span>
                                    )}
                                    {finding.cwe_id && (
                                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                                        CWE: {finding.cwe_id}
                                      </span>
                                    )}
                                  </div>
                                )}
                                {finding.categories && finding.categories.length > 0 && (
                                  <div className="mt-1 flex flex-wrap gap-1">
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
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <Link
                                href={`/projects/${finding.project_id}`}
                                className="text-sm font-medium hover:opacity-80 transition-opacity"
                                style={{ color: 'var(--brand)' }}
                              >
                                {finding.project_name}
                              </Link>
                              <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                                {finding.target_url}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="text-sm" style={{ color: 'var(--fg)' }}>
                                {finding.tool || 'N/A'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                                {finding.cvss_score !== null && finding.cvss_score !== undefined
                                  ? finding.cvss_score.toFixed(1)
                                  : '–'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="flex items-center gap-2">
                                <StatusBadge status={finding.status} />
                                <select
                                  value={finding.status}
                                  onChange={(e) => updateStatus(finding.id, e.target.value as FindingStatus)}
                                  disabled={updatingStatus === finding.id}
                                  className="text-xs rounded border px-1 py-0.5"
                                  style={{
                                    background: 'var(--surface-2)',
                                    borderColor: 'var(--border)',
                                    color: 'var(--fg)'
                                  }}
                                >
                                  <option value="open">Open</option>
                                  <option value="acknowledged">Acknowledged</option>
                                  <option value="resolved">Resolved</option>
                                  <option value="suppressed">Suppressed</option>
                                </select>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="text-sm" style={{ color: 'var(--muted)' }}>
                                {formatDate(finding.first_seen)}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right">
                              <Link
                                href={`/projects/${finding.project_id}/scans/${finding.scan_id}`}
                                className="text-sm font-medium hover:opacity-80 transition-opacity"
                                style={{ color: 'var(--brand)' }}
                              >
                                View Scan
                              </Link>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  {total > limit && (
                    <div className="px-6 py-4 border-t flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
                      <div className="text-sm" style={{ color: 'var(--muted)' }}>
                        Showing {page * limit + 1} to {Math.min((page + 1) * limit, total)} of {total} findings
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setPage(p => Math.max(0, p - 1))}
                          disabled={page === 0}
                          className="px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ background: page === 0 ? 'var(--surface-2)' : 'var(--brand)', color: 'white' }}
                        >
                          Previous
                        </button>
                        <button
                          onClick={() => setPage(p => p + 1)}
                          disabled={(page + 1) * limit >= total}
                          className="px-4 py-2 rounded-lg text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
                          style={{ background: (page + 1) * limit >= total ? 'var(--surface-2)' : 'var(--brand)', color: 'white' }}
                        >
                          Next
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
