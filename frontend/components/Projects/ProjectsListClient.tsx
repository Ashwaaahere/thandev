'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';
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
  total_scans: number;
  open_findings: number;
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        
        if (!cancelled) {
          setProjects(list);
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

  // Use formatDateTime from lib/formatDate.ts for consistent timezone handling

  const getStatusColor = (status: string | null | undefined) => {
    if (!status) return 'text-gray-400';
    const s = status.toLowerCase();
    if (s === 'completed') return 'text-green-400';
    if (s === 'running' || s === 'queued') return 'text-blue-400';
    if (s === 'failed' || s === 'error') return 'text-red-400';
    return 'text-gray-400';
  };

  const getStatusBadge = (status: string | null | undefined) => {
    if (!status) return null;
    const s = status.toLowerCase();
    let bgColor = 'bg-gray-500/10';
    let textColor = 'text-gray-400';
    
    if (s === 'completed') {
      bgColor = 'bg-green-500/10';
      textColor = 'text-green-400';
    } else if (s === 'running' || s === 'queued') {
      bgColor = 'bg-blue-500/10';
      textColor = 'text-blue-400';
    } else if (s === 'failed' || s === 'error') {
      bgColor = 'bg-red-500/10';
      textColor = 'text-red-400';
    }
    
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${bgColor} ${textColor}`}>
        {status}
      </span>
    );
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
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="mb-8">
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-2 animate-pulse"></div>
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 animate-pulse"></div>
          </div>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
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
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto px-6 py-8">
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
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto px-6 py-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                Projects
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                Manage your security scanning targets
              </p>
            </div>
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

          {/* Empty State */}
          <div className="mt-8 rounded-xl border px-6 py-8 text-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <p className="font-medium mb-1" style={{ color: 'var(--fg)' }}>No projects yet</p>
            <p className="mt-1" style={{ color: 'var(--muted)' }}>
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
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
              Projects
            </h1>
            <p className="text-lg" style={{ color: 'var(--muted)' }}>
              Manage your security scanning targets
            </p>
          </div>
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

        {/* Projects List */}
        {projects.length === 0 ? (
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
          <div className="space-y-4">
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="block rounded-xl border p-6 hover:shadow-lg transition-all"
                style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold truncate" style={{ color: 'var(--fg)' }}>
                        {project.name}
                      </h3>
                      {getStatusBadge(project.last_scan_status)}
                    </div>
                    <p className="text-sm font-mono mb-4 truncate" style={{ color: 'var(--muted)' }}>
                      {project.target_url || 'No target URL'}
                    </p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Last scan</p>
                        <p className="font-medium" style={{ color: 'var(--fg)' }}>
                          {formatDateTime(project.last_scan_at)}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Risk score</p>
                        <p className="font-medium" style={{ color: 'var(--fg)' }}>
                          {project.last_risk_score !== null && project.last_risk_score !== undefined
                            ? project.last_risk_score.toFixed(1)
                            : '–'}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Total scans</p>
                        <p className="font-medium" style={{ color: 'var(--fg)' }}>
                          {project.total_scans}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Open findings</p>
                        <p className={`font-medium ${project.open_findings > 0 ? 'text-red-400' : 'text-green-400'}`}>
                          {project.open_findings}
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="flex-shrink-0 ml-4">
                    <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
          </div>
        </main>
      </div>
    </div>
  );
}


