'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { thandevFetchJSON } from '@/lib/thandevApi';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';

// Types matching backend response
type ProjectWithStats = {
  id: string;
  name: string;
  target_url?: string | null;
  description?: string | null;
  created_at: string;
  last_scan_at?: string | null;
  last_scan_status?: string | null;
  last_risk_score?: number | null;
  total_scans?: number | null; // Made optional to handle missing values
  open_findings?: number | null; // Made optional to handle missing values
};

type ProjectListWithStatsResponse = {
  items: ProjectWithStats[];
  total: number;
};

export default function ProjectsListClient() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectWithStats[]>([]);
  const [filteredProjects, setFilteredProjects] = useState<ProjectWithStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [riskFilter, setRiskFilter] = useState('all');
  const [sortBy, setSortBy] = useState('recently-active');

  useEffect(() => {
    if (status !== 'authenticated') return;
    
    let cancelled = false;

    async function loadProjects() {
      if (!session) return;
      
      setLoading(true);
      setError(null);
      
      try {
        const res = await thandevFetchJSON<ProjectListWithStatsResponse>(
          '/api/projects',
          session
        );
        
        // Accept either res.items or res.projects for backward compatibility
        const list = (res as any).items ?? (res as any).projects ?? [];
        
        console.log('ProjectsListClient: Raw API response', res);
        console.log('ProjectsListClient: Response structure', {
          has_items: 'items' in res,
          has_projects: 'projects' in res,
          items_type: typeof (res as any).items,
          items_length: Array.isArray((res as any).items) ? (res as any).items.length : 'not array',
          full_response_keys: Object.keys(res)
        });
        
        // Normalize the data - ensure all required fields exist
        const normalizedList = list.map((p: any) => {
          // Ensure numeric values are properly converted
          const totalScans = (p.total_scans !== undefined && p.total_scans !== null) ? Number(p.total_scans) : 0;
          const openFindings = (p.open_findings !== undefined && p.open_findings !== null) ? Number(p.open_findings) : 0;
          
          return {
            id: String(p.id || ''),
            name: String(p.name || ''),
            target_url: p.target_url || null,
            description: p.description || null,
            created_at: p.created_at || new Date().toISOString(),
            last_scan_at: p.last_scan_at || null,
            last_scan_status: p.last_scan_status || null,
            last_risk_score: p.last_risk_score !== undefined && p.last_risk_score !== null ? Number(p.last_risk_score) : null,
            total_scans: totalScans,
            open_findings: openFindings,
          };
        });
        
        console.log('ProjectsListClient: Normalized projects', {
          total: normalizedList.length,
          projects: normalizedList.map((p: any) => ({
            id: p.id,
            name: p.name,
            total_scans: p.total_scans,
            open_findings: p.open_findings,
            last_scan_at: p.last_scan_at,
            last_risk_score: p.last_risk_score,
            last_scan_status: p.last_scan_status,
          }))
        });
        
        if (!cancelled) {
          console.log('ProjectsListClient: Setting projects state', {
            count: normalizedList.length,
            first_project: normalizedList[0] ? {
              id: normalizedList[0].id,
              name: normalizedList[0].name,
              total_scans: normalizedList[0].total_scans,
              open_findings: normalizedList[0].open_findings
            } : null
          });
          setProjects(normalizedList);
          // Also set filteredProjects initially - filter effect will update it if needed
          setFilteredProjects(normalizedList);
        }
      } catch (err: any) {
        if (!cancelled) {
          console.error('Failed to load projects', err);
          setError(
            err?.message ?? 'Failed to load projects. Please try again or refresh.'
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadProjects();
    return () => {
      cancelled = true;
    };
  }, [status, session]);

  // Filter and sort projects
  useEffect(() => {
    console.log('ProjectsListClient: Filter effect running', {
      projects_count: projects.length,
      searchQuery,
      riskFilter,
      sortBy
    });
    
    if (projects.length === 0) {
      console.log('ProjectsListClient: No projects to filter, setting empty array');
      setFilteredProjects([]);
      return;
    }
    
    let filtered = [...projects];
    console.log('ProjectsListClient: Starting with', filtered.length, 'projects');

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(p => 
        p.name.toLowerCase().includes(query) ||
        (p.target_url && p.target_url.toLowerCase().includes(query))
      );
      console.log('ProjectsListClient: After search filter:', filtered.length);
    }

    // Apply risk filter
    if (riskFilter !== 'all') {
      filtered = filtered.filter(p => {
        const riskLevel = getRiskLevel(p.last_risk_score);
        return riskLevel.toLowerCase() === riskFilter.toLowerCase();
      });
      console.log('ProjectsListClient: After risk filter:', filtered.length);
    }

    // Apply sorting
    if (sortBy === 'recently-active') {
      filtered.sort((a, b) => {
        const dateA = a.last_scan_at ? new Date(a.last_scan_at).getTime() : 0;
        const dateB = b.last_scan_at ? new Date(b.last_scan_at).getTime() : 0;
        return dateB - dateA;
      });
    } else if (sortBy === 'name') {
      filtered.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortBy === 'risk-high') {
      filtered.sort((a, b) => {
        const riskA = a.last_risk_score ?? 0;
        const riskB = b.last_risk_score ?? 0;
        return riskB - riskA;
      });
    }

    console.log('ProjectsListClient: Setting filtered projects', {
      count: filtered.length,
      first_project: filtered[0] ? {
        id: filtered[0].id,
        name: filtered[0].name,
        total_scans: filtered[0].total_scans,
        open_findings: filtered[0].open_findings
      } : null
    });
    
    setFilteredProjects(filtered);
  }, [projects, searchQuery, riskFilter, sortBy]);

  // Format date like "JAN 24, 2026"
  const formatScanDate = (dateString: string | null | undefined) => {
    if (!dateString) return 'Never';
    try {
      const date = new Date(dateString);
      const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
      const month = months[date.getMonth()];
      const day = date.getDate();
      const year = date.getFullYear();
      return `${month} ${day}, ${year}`;
    } catch {
      return 'Never';
    }
  };

  // Get risk level from risk score
  const getRiskLevel = (riskScore: number | null | undefined): string => {
    if (riskScore === null || riskScore === undefined || isNaN(Number(riskScore))) return 'UNKNOWN';
    const score = Number(riskScore);
    if (score >= 80) return 'CRITICAL';
    if (score >= 60) return 'HIGH';
    if (score >= 40) return 'MEDIUM';
    if (score >= 20) return 'LOW';
    return 'SECURE';
  };

  // Get risk level color
  const getRiskLevelColor = (riskLevel: string) => {
    const level = riskLevel.toUpperCase();
    if (level === 'CRITICAL') return { dot: 'bg-red-500', text: 'text-red-500' };
    if (level === 'HIGH') return { dot: 'bg-orange-500', text: 'text-orange-500' };
    if (level === 'MEDIUM') return { dot: 'bg-yellow-500', text: 'text-yellow-500' };
    if (level === 'LOW') return { dot: 'bg-green-500', text: 'text-green-500' };
    if (level === 'SECURE') return { dot: 'bg-green-500', text: 'text-green-500' };
    return { dot: 'bg-gray-500', text: 'text-gray-500' };
  };

  // Show skeleton only when loading and no error
  if (loading && !error) {
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
          <main className="flex-1 overflow-y-auto p-5" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-1.5 animate-pulse"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 animate-pulse"></div>
          </div>
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="rounded-xl border p-5 animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                <div className="h-5 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-1.5"></div>
                <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-4"></div>
                <div className="grid grid-cols-4 gap-4">
                  {[...Array(4)].map((_, j) => (
                    <div key={j}>
                      <div className="h-2.5 bg-gray-200 dark:bg-gray-700 rounded w-16 mb-1"></div>
                      <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-12"></div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
      </div>
    </div>
    );
  }

  // Show error state
  if (error && !loading) {
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
          <main className="flex-1 overflow-y-auto p-5" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <h1 className="text-3xl font-bold mb-1.5 text-white">
              Projects
            </h1>
            <p className="text-base text-white">
              Manage your security scanning targets
            </p>
          </div>
          <div className="mt-8 flex flex-col items-center text-sm">
            <p className="text-red-400 mb-3">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-3 rounded-md px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 transition-opacity"
              style={{ background: 'var(--brand)' }}
            >
              Retry
            </button>
          </div>
        </div>
      </main>
      </div>
    </div>
    );
  }

  // Show empty state
  if (!loading && !error && projects.length === 0) {
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
          <main className="flex-1 overflow-y-auto p-5" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-3xl font-bold mb-1.5 text-white">
              Projects
            </h1>
            <p className="text-base text-white">
              Manage your security scanning targets
            </p>
          </div>

          {/* Search and Filters */}
          <div className="mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            {/* Search Bar */}
            <div className="relative flex-1 max-w-lg">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search projects by name or URL..."
                className="w-full pl-10 pr-4 py-2.5 text-sm rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent placeholder:text-gray-500"
                style={{
                  borderColor: 'var(--border)',
                  background: 'var(--surface-2)',
                  color: 'var(--fg)'
                }}
              />
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
            </div>

            {/* Filters and Add Button */}
            <div className="flex items-center gap-3">
              {/* Risk Filter */}
              <select
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                className="px-3 py-2.5 text-sm rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent"
                style={{
                  borderColor: 'var(--border)',
                  background: 'var(--surface-2)',
                  color: 'var(--fg)'
                }}
              >
                <option value="all">Risk: All Levels</option>
                <option value="critical">Risk: Critical</option>
                <option value="high">Risk: High</option>
                <option value="medium">Risk: Medium</option>
                <option value="low">Risk: Low</option>
                <option value="secure">Risk: Secure</option>
              </select>

              {/* Sort Filter */}
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-2.5 text-sm rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent"
                style={{
                  borderColor: 'var(--border)',
                  background: 'var(--surface-2)',
                  color: 'var(--fg)'
                }}
              >
                <option value="recently-active">Sort: Recently Active</option>
                <option value="name">Sort: Name</option>
                <option value="risk-high">Sort: Risk (High to Low)</option>
              </select>

              {/* Add New Project Button */}
              <Link
                href="/dashboard/scan"
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
                style={{ background: '#60a5fa' }}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Add New Project
              </Link>
            </div>
          </div>

          {/* Empty State */}
          <div className="mt-8 rounded-xl border px-6 py-8 text-sm" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
            <p className="font-medium mb-1 text-white">No projects yet</p>
            <p className="mt-1 text-gray-400">
              Create a project or run a quick scan from the dashboard to get started.
            </p>
          </div>
        </div>
      </main>
      </div>
    </div>
    );
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
          user={session?.user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-5" style={{ background: 'var(--bg)' }}>
          <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-1.5 text-white">
            Projects
          </h1>
          <p className="text-base text-white">
            Manage your security scanning targets
          </p>
        </div>

        {/* Search and Filters */}
        <div className="mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          {/* Search Bar */}
          <div className="relative flex-1 max-w-lg">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search projects by name or URL..."
              className="w-full pl-10 pr-4 py-2.5 text-sm rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent placeholder:text-gray-500"
              style={{
                borderColor: 'var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--fg)'
              }}
            />
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
          </div>

          {/* Filters and Add Button */}
          <div className="flex items-center gap-3">
            {/* Risk Filter */}
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="px-3 py-2.5 text-sm rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent"
              style={{
                borderColor: 'var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--fg)'
              }}
            >
              <option value="all">Risk: All Levels</option>
              <option value="critical">Risk: Critical</option>
              <option value="high">Risk: High</option>
              <option value="medium">Risk: Medium</option>
              <option value="low">Risk: Low</option>
              <option value="secure">Risk: Secure</option>
            </select>

            {/* Sort Filter */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-3 py-2.5 text-sm rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent"
              style={{
                borderColor: 'var(--border)',
                background: 'var(--surface-2)',
                color: 'var(--fg)'
              }}
            >
              <option value="recently-active">Sort: Recently Active</option>
              <option value="name">Sort: Name</option>
              <option value="risk-high">Sort: Risk (High to Low)</option>
            </select>

            {/* Add New Project Button */}
            <Link
              href="/dashboard/scan"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ background: '#60a5fa' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              Add New Project
            </Link>
          </div>
        </div>

        {/* Projects List */}
        {filteredProjects.length === 0 ? (
          <div className="rounded-xl border p-12 text-center" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--brand)', opacity: 0.1 }}>
              <svg className="w-8 h-8" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--fg)' }}>
              No projects yet
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              No projects yet — run a scan from the Dashboard or create a project.
            </p>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ background: 'var(--brand)' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              Run new scan
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredProjects.map((project) => {
              // Debug: Log each project's data
              console.log('Rendering project:', {
                id: project.id,
                name: project.name,
                total_scans: project.total_scans,
                open_findings: project.open_findings,
                last_scan_at: project.last_scan_at,
                last_risk_score: project.last_risk_score,
                project_obj: project
              });
              
              const riskLevel = getRiskLevel(project.last_risk_score);
              const riskColors = getRiskLevelColor(riskLevel);
              
              return (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="block rounded-xl border p-5 hover:shadow-lg transition-all"
                  style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      {/* Project Name */}
                      <h3 className="text-base font-bold mb-1.5 text-white truncate">
                        {project.name}
                      </h3>
                      
                      {/* URL */}
                      <p className="text-xs font-mono mb-4 text-gray-400 truncate">
                        {project.target_url || 'No target URL'}
                      </p>
                      
                      {/* Metrics Grid */}
                      <div className="grid grid-cols-4 gap-4">
                        {/* LAST SCAN */}
                        <div>
                          <p className="text-[10px] font-medium mb-1 text-gray-500 uppercase tracking-wide">
                            LAST SCAN
                          </p>
                          <p className="text-xs font-medium text-white">
                            {formatScanDate(project.last_scan_at)}
                          </p>
                        </div>
                        
                        {/* RISK SCORE */}
                        <div>
                          <p className="text-[10px] font-medium mb-1 text-gray-500 uppercase tracking-wide">
                            RISK SCORE
                          </p>
                          <div className="flex items-center gap-1.5">
                            <div className={`w-2 h-2 rounded-full ${riskColors.dot}`}></div>
                            <p className={`text-xs font-medium ${riskColors.text}`}>
                              {riskLevel}
                            </p>
                          </div>
                        </div>
                        
                        {/* TOTAL SCANS */}
                        <div>
                          <p className="text-[10px] font-medium mb-1 text-gray-500 uppercase tracking-wide">
                            TOTAL SCANS
                          </p>
                          <p className="text-xs font-medium text-white">
                            {Number(project.total_scans) || 0}
                          </p>
                        </div>
                        
                        {/* OPEN FINDINGS */}
                        <div>
                          <p className="text-[10px] font-medium mb-1 text-gray-500 uppercase tracking-wide">
                            OPEN FINDINGS
                          </p>
                          <p className={`text-xs font-medium ${(Number(project.open_findings) || 0) > 0 ? 'text-red-500' : 'text-white'}`}>
                            {Number(project.open_findings) || 0}
                          </p>
                        </div>
                      </div>
                    </div>
                    
                    {/* Arrow Icon */}
                    <div className="flex-shrink-0 ml-4">
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
          </div>
        </main>
      </div>
    </div>
  );
}


