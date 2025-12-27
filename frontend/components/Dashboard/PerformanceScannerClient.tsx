'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { thandevFetchJSON } from '@/lib/thandevApi';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

// Types
type ProjectListItem = {
  id: string;
  name: string;
  target_url?: string | null;
};

export default function PerformanceScannerClient() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedMode, setSelectedMode] = useState<'existing' | 'new'>('existing');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [targetUrl, setTargetUrl] = useState<string>('');
  const [scanLevel, setScanLevel] = useState<'basic' | 'pro' | 'advanced'>('pro');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    if (!session) return;
    
    setLoadingProjects(true);
    try {
      const res = await thandevFetchJSON<{ items: ProjectListItem[] }>(
        '/api/projects',
        session
      );
      const projectsList = res.items ?? [];
      setProjects(projectsList);
      
      // Default to first project if available
      if (projectsList.length > 0 && !selectedProjectId) {
        setSelectedProjectId(projectsList[0].id);
      }
    } catch (e) {
      console.error('Failed to load projects', e);
    } finally {
      setLoadingProjects(false);
    }
  }, [session, selectedProjectId]);

  useEffect(() => {
    if (sessionStatus === 'unauthenticated') {
      router.push('/auth/signin');
      return;
    }
    if (sessionStatus !== 'authenticated') return;
    loadProjects();
  }, [sessionStatus, loadProjects, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) {
      setError('Session required. Please log in again.');
      return;
    }

    // Validation
    if (selectedMode === 'existing') {
      if (!selectedProjectId) {
        setError('Please select a project');
        return;
      }
    } else {
      const trimmed = targetUrl.trim();
      if (!trimmed) {
        setError('Please enter a target URL');
        return;
      }
      if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
        setError('URL must start with http:// or https://');
        return;
      }
    }

    setSubmitting(true);
    setError(null);

    try {
      const body: any = {
        scan_level: scanLevel,
      };

      if (selectedMode === 'existing') {
        body.project_id = selectedProjectId;
      } else {
        body.target_url = targetUrl.trim();
      }

      const scan = await thandevFetchJSON<{ project_id: string | null; scan_id: string }>(
        '/api/performance/quick',
        session,
        {
          method: 'POST',
          body: JSON.stringify(body),
        }
      );

      // On success: navigate to history or project
      if (scan?.scan_id) {
        if (scan.project_id) {
          // Navigate to project or performance history
          router.push('/dashboard/performance/history');
        } else {
          // Navigate to performance history
          router.push('/dashboard/performance/history');
        }
      } else {
        // fallback: go to performance history
        router.push('/dashboard/performance/history');
      }
    } catch (err: any) {
      console.error('Failed to start scan', err);
      setError(err?.message || 'Failed to start scan. Please try again.');
    } finally {
      setSubmitting(false);
    }
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
            <div className="max-w-3xl mx-auto">
              <div className="rounded-xl border p-8 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-8"></div>
                <div className="space-y-4">
                  <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  <div className="h-12 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
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
          <div className="max-w-3xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                Performance Scanner
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                Run performance checks on your targets.
              </p>
            </div>

            {/* Scanner Card */}
            <div className="rounded-xl border p-8" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <form onSubmit={handleSubmit}>
                {/* Mode Selector Tabs */}
                <div className="mb-6">
                  <div className="flex gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedMode('existing');
                        setError(null);
                      }}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        selectedMode === 'existing'
                          ? 'border-b-2 text-white'
                          : 'text-gray-400 hover:text-gray-300'
                      }`}
                      style={{
                        borderColor: selectedMode === 'existing' ? 'var(--brand)' : 'transparent',
                        color: selectedMode === 'existing' ? 'white' : 'var(--muted)'
                      }}
                    >
                      Existing project
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedMode('new');
                        setError(null);
                      }}
                      className={`px-4 py-2 text-sm font-medium transition-colors ${
                        selectedMode === 'new'
                          ? 'border-b-2 text-white'
                          : 'text-gray-400 hover:text-gray-300'
                      }`}
                      style={{
                        borderColor: selectedMode === 'new' ? 'var(--brand)' : 'transparent',
                        color: selectedMode === 'new' ? 'white' : 'var(--muted)'
                      }}
                    >
                      New target
                    </button>
                  </div>
                </div>

                {/* Existing Project Mode */}
                {selectedMode === 'existing' && (
                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                      Select Project
                    </label>
                    {loadingProjects ? (
                      <div className="px-3 py-2 rounded-lg border animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                      </div>
                    ) : projects.length === 0 ? (
                      <div className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--muted)' }}>
                        No projects available. Switch to "New target" to create one.
                      </div>
                    ) : (
                      <select
                        value={selectedProjectId}
                        onChange={(e) => setSelectedProjectId(e.target.value)}
                        required
                        className="w-full px-3 py-2 rounded-lg border text-sm"
                        style={{
                          borderColor: 'var(--border)',
                          background: 'var(--surface-2)',
                          color: 'var(--fg)'
                        }}
                      >
                        <option value="">Select a project...</option>
                        {projects.map((project) => (
                          <option key={project.id} value={project.id}>
                            {project.name} {project.target_url ? `(${project.target_url})` : ''}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}

                {/* New Target Mode */}
                {selectedMode === 'new' && (
                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                      Target URL
                    </label>
                    <input
                      type="url"
                      value={targetUrl}
                      onChange={(e) => setTargetUrl(e.target.value)}
                      placeholder="https://example.com"
                      required
                      className="w-full px-3 py-2 rounded-lg border text-sm"
                      style={{
                        borderColor: 'var(--border)',
                        background: 'var(--surface-2)',
                        color: 'var(--fg)'
                      }}
                    />
                    <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
                      Example: https://example.com
                    </p>
                  </div>
                )}

                {/* Scan Level Selector */}
                <div className="mb-6">
                  <label className="block text-sm font-medium mb-3" style={{ color: 'var(--fg)' }}>
                    Scan Level
                  </label>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      type="button"
                      onClick={() => setScanLevel('basic')}
                      className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                        scanLevel === 'basic'
                          ? 'text-white shadow-sm'
                          : 'hover:opacity-80'
                      }`}
                      style={{
                        background: scanLevel === 'basic' ? 'var(--brand)' : 'var(--surface-2)',
                        borderColor: scanLevel === 'basic' ? 'var(--brand)' : 'var(--border)',
                        color: scanLevel === 'basic' ? 'white' : 'var(--fg)'
                      }}
                    >
                      <div className="font-semibold mb-1">Basic</div>
                      <div className="text-xs opacity-80">Fast metrics</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setScanLevel('pro')}
                      className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                        scanLevel === 'pro'
                          ? 'text-white shadow-sm'
                          : 'hover:opacity-80'
                      }`}
                      style={{
                        background: scanLevel === 'pro' ? 'var(--brand)' : 'var(--surface-2)',
                        borderColor: scanLevel === 'pro' ? 'var(--brand)' : 'var(--border)',
                        color: scanLevel === 'pro' ? 'white' : 'var(--fg)'
                      }}
                    >
                      <div className="font-semibold mb-1">Pro</div>
                      <div className="text-xs opacity-80">Core Web Vitals</div>
                    </button>
                    <button
                      type="button"
                      onClick={() => setScanLevel('advanced')}
                      className={`px-4 py-3 rounded-lg border text-sm font-medium transition-all ${
                        scanLevel === 'advanced'
                          ? 'text-white shadow-sm'
                          : 'hover:opacity-80'
                      }`}
                      style={{
                        background: scanLevel === 'advanced' ? 'var(--brand)' : 'var(--surface-2)',
                        borderColor: scanLevel === 'advanced' ? 'var(--brand)' : 'var(--border)',
                        color: scanLevel === 'advanced' ? 'white' : 'var(--fg)'
                      }}
                    >
                      <div className="font-semibold mb-1">Advanced</div>
                      <div className="text-xs opacity-80">Full audit</div>
                    </button>
                  </div>
                </div>

                {/* Error State */}
                {error && (
                  <div className="mb-6 p-4 rounded-lg border border-red-500/50 bg-red-500/10">
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                )}

                {/* Actions */}
                <div className="flex items-center justify-between gap-4">
                  <button
                    type="submit"
                    disabled={submitting || (selectedMode === 'existing' && !selectedProjectId) || (selectedMode === 'new' && !targetUrl.trim())}
                    className="px-6 py-3 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90"
                    style={{ background: 'var(--brand)' }}
                  >
                    {submitting ? (
                      <span className="flex items-center gap-2">
                        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></span>
                        Starting scan...
                      </span>
                    ) : (
                      'Start scan'
                    )}
                  </button>
                  <Link
                    href="/dashboard/performance/history"
                    className="text-sm font-medium hover:opacity-80 transition-opacity"
                    style={{ color: 'var(--brand)' }}
                  >
                    View scan history
                  </Link>
                </div>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
