'use client';

import { useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { thandevFetchJSON } from '@/lib/thandevApi';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

// Types
type ScanItem = {
  id: string;
  project_id: string;
  scan_level: string;
  status: string;
  risk_score?: number | null;
};

type ProjectListItem = {
  id: string;
  name: string;
  target_url?: string | null;
  root_domain?: string | null;
};

type DomainVerificationStatus = {
  id: string;
  project_id: string;
  domain: string;
  status: string;
  challenge_name: string;
  challenge_value: string;
  last_checked_at?: string;
};

type AllowedDomain = {
  id: string;
  domain: string;
  scope: 'global' | 'tenant';
  tenant_id?: string | null;
  enabled: boolean;
  notes?: string | null;
};

// Rough registrable-domain matcher: compare hostname against allowed domain (eTLD+1).
// Backend enforces exact registrable domain; here we treat host or any parent ending with allowed domain as allowed.
const isHostAllowedByDomain = (host: string | null, allowedDomain: string) => {
  if (!host) return false;
  const h = host.toLowerCase();
  const d = allowedDomain.toLowerCase();
  return h === d || h.endsWith(`.${d}`);
};

const getHostFromUrl = (url: string): string | null => {
  try {
    const u = new URL(url);
    return u.hostname || null;
  } catch {
    return null;
  }
};

export default function SecurityScannerClient() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [selectedMode, setSelectedMode] = useState<'existing' | 'new'>('existing');
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [targetUrl, setTargetUrl] = useState<string>('https://');
  const [scanLevel, setScanLevel] = useState<'basic' | 'pro' | 'advanced'>('pro');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dvStatus, setDvStatus] = useState<DomainVerificationStatus | null>(null);
  const [dvLoading, setDvLoading] = useState(false);
  const [preparedProjectId, setPreparedProjectId] = useState<string>('');
  const [allowedDomains, setAllowedDomains] = useState<AllowedDomain[]>([]);
  
  // New state for URL selection in existing project mode
  const [existingUrls, setExistingUrls] = useState<string[]>([]);
  const [loadingUrls, setLoadingUrls] = useState(false);
  const [urlSelectionMode, setUrlSelectionMode] = useState<'existing' | 'new'>('existing');
  const [selectedUrl, setSelectedUrl] = useState<string>('');
  const [newUrlForProject, setNewUrlForProject] = useState<string>('');

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

  // Load existing URLs for selected project
  const loadExistingUrls = useCallback(async (projectId: string) => {
    if (!session || !projectId) {
      setExistingUrls([]);
      setSelectedUrl('');
      return;
    }

    setLoadingUrls(true);
    try {
      // Get project details to fetch its target_url
      const projectRes = await thandevFetchJSON<ProjectListItem>(
        `/api/projects/${projectId}`,
        session
      );
      
      const urls: string[] = [];
      
      // Add project's default target_url if available
      if (projectRes?.target_url) {
        urls.push(projectRes.target_url);
      }
      
      // Try to fetch scan history to get other URLs that were scanned
      try {
        const scansRes = await thandevFetchJSON<{ items: ScanItem[] }>(
          `/api/scans?project_id=${projectId}&limit=50`,
          session
        );
        
        // Note: Scan items might not have target_url directly in the response
        // For now, we primarily use the project's target_url
        // The API can handle both project_id and target_url when creating scans
      } catch (scanErr) {
        // Ignore scan fetch errors, we'll still use project target_url
        console.debug('Could not fetch scan history for URLs', scanErr);
      }
      
      setExistingUrls(urls);
      
      // If we have URLs, select the first one by default
      if (urls.length > 0) {
        setSelectedUrl(urls[0]);
        setUrlSelectionMode('existing');
      } else {
        // No existing URLs, default to new URL mode
        setUrlSelectionMode('new');
        setNewUrlForProject('https://');
      }
    } catch (e) {
      console.error('Failed to load existing URLs', e);
      setExistingUrls([]);
      setSelectedUrl('');
      setUrlSelectionMode('new');
      setNewUrlForProject('https://');
    } finally {
      setLoadingUrls(false);
    }
  }, [session]);

  // Load URLs when project is selected
  useEffect(() => {
    if (selectedMode === 'existing' && selectedProjectId) {
      loadExistingUrls(selectedProjectId);
    } else {
      // Reset URL-related state when switching modes
      setExistingUrls([]);
      setSelectedUrl('');
      setNewUrlForProject('');
      setUrlSelectionMode('existing');
    }
  }, [selectedProjectId, selectedMode, loadExistingUrls]);

  const loadAllowedDomains = useCallback(async () => {
    if (!session) return;
    try {
      const res = await thandevFetchJSON<AllowedDomain[]>(
        '/api/access/allowed-domains',
        session
      );
      setAllowedDomains(res || []);
    } catch (e) {
      console.warn('Allowed domains fetch failed', e);
      setAllowedDomains([]);
    }
  }, [session]);

  const loadDomainVerification = useCallback(async (projectId: string) => {
    if (!session || !projectId) {
      setDvStatus(null);
      return;
    }
    setDvLoading(true);
    setError(null);
    try {
      const res = await thandevFetchJSON<DomainVerificationStatus>(
        `/api/projects/${projectId}/domain-verification`,
        session
      );
      setDvStatus(res);
    } catch (err) {
      // If not found, request token
      try {
        const req = await thandevFetchJSON<DomainVerificationStatus>(
          `/api/projects/${projectId}/domain-verification/request`,
          session,
          { method: 'POST' }
        );
        setDvStatus(req);
      } catch (e) {
        console.error('DV load failed', e);
        setDvStatus(null);
      }
    } finally {
      setDvLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (sessionStatus === 'unauthenticated') {
      router.push('/auth/signin');
      return;
    }
    if (sessionStatus !== 'authenticated') return;
    loadProjects();
    loadAllowedDomains();
  }, [sessionStatus, loadProjects, loadAllowedDomains, router]);

  useEffect(() => {
    if (selectedProjectId) {
      loadDomainVerification(selectedProjectId);
    } else {
      setDvStatus(null);
    }
  }, [selectedProjectId, loadDomainVerification]);

  // New target flow removed for all users

  const deriveProjectName = (url: string) => {
    try {
      const u = new URL(url);
      return u.hostname.replace(/^www\./, '') || 'New Project';
    } catch {
      return 'New Project';
    }
  };

  const prepareNewTarget = async () => {
    if (!session) return;
    const trimmed = targetUrl.trim();
    if (!trimmed) {
      setError('Please enter a target URL');
      return;
    }
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      setError('URL must start with http:// or https://');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        name: deriveProjectName(trimmed),
        target_url: trimmed,
      };
      const project = await thandevFetchJSON<{ id: string }>(
        '/api/projects',
        session,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );
      setPreparedProjectId(project.id);
      setSelectedProjectId(project.id);
      await loadDomainVerification(project.id);
      loadProjects();
      setSelectedMode('existing'); // move to existing once prepared
    } catch (e: any) {
      setError(e?.message || 'Failed to prepare target or fetch verification');
    } finally {
      setSubmitting(false);
    }
  };

  const refreshVerification = useCallback(async () => {
    if (!session) return;
    const pid = selectedProjectId;
    if (!pid) return;
    setDvLoading(true);
    try {
      await loadDomainVerification(pid);
    } finally {
      setDvLoading(false);
    }
  }, [session, selectedProjectId, loadDomainVerification]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!session) {
      setError('Session required. Please log in again.');
      return;
    }

    const isAdmin = Boolean(session.user?.isAdmin);

    // Validation
    if (selectedMode === 'existing') {
      if (!selectedProjectId) {
        setError('Please select a project');
        return;
      }
      
      // Validate URL selection
      if (urlSelectionMode === 'existing' && !selectedUrl) {
        setError('Please select an existing URL or switch to "New URL" tab');
        return;
      }
      if (urlSelectionMode === 'new') {
        const trimmed = newUrlForProject.trim();
        if (!trimmed) {
          setError('Please enter a target URL');
          return;
        }
        if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
          setError('URL must start with http:// or https://');
          return;
        }
      }
      
      if (!isAdmin && !allowedForSelectedProject && dvStatus && dvStatus.status !== 'verified') {
        setError('Domain not verified. Please add DNS TXT and verify.');
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
      if (!isAdmin) {
        if (!preparedProjectId || preparedProjectId !== selectedProjectId) {
          setError('Prepare domain verification first.');
          return;
        }
        if (!allowedForTargetUrl && dvStatus && dvStatus.status !== 'verified') {
          setError('Domain not verified. Please add DNS TXT and verify.');
          return;
        }
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
        // Add target_url if user selected a specific URL
        if (urlSelectionMode === 'existing' && selectedUrl) {
          body.target_url = selectedUrl;
        } else if (urlSelectionMode === 'new' && newUrlForProject.trim()) {
          body.target_url = newUrlForProject.trim();
        }
      } else {
        if (isAdmin) {
        body.target_url = targetUrl.trim();
        } else {
          body.project_id = preparedProjectId;
        }
      }

      const scan = await thandevFetchJSON<{ project_id: string; scan_id: string }>(
        '/api/scans/quick',
        session,
        {
          method: 'POST',
          body: JSON.stringify(body),
        }
      );

      // On success: go to scan detail
      if (scan?.scan_id && scan?.project_id) {
        router.push(`/projects/${scan.project_id}/scans/${scan.scan_id}`);
      } else {
        // fallback: go to scan history
        router.push('/dashboard/history');
      }
    } catch (err: any) {
      console.error('Failed to start scan', err);
      // Safely extract error message
      let errorMessage = 'Failed to start scan. Please try again.';
      if (err) {
        if (typeof err === 'string') {
          errorMessage = err;
        } else if (err?.message && typeof err.message === 'string') {
          errorMessage = err.message;
        } else if (err?.error && typeof err.error === 'string') {
          errorMessage = err.error;
        } else if (typeof err === 'object') {
          // Try to stringify if it's an object, but limit length
          try {
            const errorStr = JSON.stringify(err);
            errorMessage = errorStr.length > 200 ? errorStr.substring(0, 200) + '...' : errorStr;
          } catch {
            errorMessage = 'Failed to start scan. Please try again.';
          }
        }
      }
      setError(errorMessage);
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

  const tenantId = (session.user as any)?.tenantId || (session.user as any)?.tenant_id;
  const currentProject = projects.find((p) => p.id === selectedProjectId);
  const currentRootDomain = currentProject?.root_domain || (currentProject?.target_url ? getHostFromUrl(currentProject.target_url) : null);
  const targetHost = getHostFromUrl(targetUrl);

  const isAllowedDomain = (domain: string | null) =>
    !!domain &&
    allowedDomains.some((ad) => {
      if (!ad.enabled) return false;
      if (ad.scope === 'tenant' && ad.tenant_id && tenantId && ad.tenant_id !== tenantId) return false;
      return isHostAllowedByDomain(domain, ad.domain);
    });

  const allowedForSelectedProject = isAllowedDomain(currentRootDomain);
  const allowedForTargetUrl = isAllowedDomain(targetHost);
  const allowedDomainMatch = allowedDomains.find((ad) => ad.enabled && targetHost && isHostAllowedByDomain(targetHost, ad.domain));

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
                Security Scanner
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                Launch a new security assessment for your website or API.
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
                        setDvStatus(null);
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
                        setDvStatus(null);
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
                  <div className="space-y-6">
                    {/* Project Selection */}
                    <div>
                      <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                        Select Project
                      </label>
                      {loadingProjects ? (
                        <div className="px-3 py-2 rounded-lg border animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                        </div>
                      ) : projects.length === 0 ? (
                        <div className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--muted)' }}>
                          No projects available. Please create a project first.
                        </div>
                      ) : (
                        <select
                          value={selectedProjectId}
                          onChange={(e) => {
                            setSelectedProjectId(e.target.value);
                            setSelectedUrl('');
                            setNewUrlForProject('');
                            setUrlSelectionMode('existing');
                          }}
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

                    {/* URL Selection - Only show if project is selected */}
                    {selectedProjectId && (
                      <div>
                        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                          Select or Enter URL
                        </label>
                        
                        {/* URL Selection Mode Tabs */}
                        <div className="mb-3">
                          <div className="flex gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
                            <button
                              type="button"
                              onClick={() => {
                                setUrlSelectionMode('existing');
                                setNewUrlForProject('');
                              }}
                              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                                urlSelectionMode === 'existing'
                                  ? 'border-b-2'
                                  : ''
                              }`}
                              style={{
                                borderColor: urlSelectionMode === 'existing' ? 'var(--brand)' : 'transparent',
                                color: urlSelectionMode === 'existing' ? 'white' : 'var(--muted)'
                              }}
                            >
                              Existing URLs
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setUrlSelectionMode('new');
                                setSelectedUrl('');
                                setNewUrlForProject('https://');
                              }}
                              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                                urlSelectionMode === 'new'
                                  ? 'border-b-2'
                                  : ''
                              }`}
                              style={{
                                borderColor: urlSelectionMode === 'new' ? 'var(--brand)' : 'transparent',
                                color: urlSelectionMode === 'new' ? 'white' : 'var(--muted)'
                              }}
                            >
                              New URL
                            </button>
                          </div>
                        </div>

                        {/* Existing URLs Selection */}
                        {urlSelectionMode === 'existing' && (
                          <div>
                            {loadingUrls ? (
                              <div className="px-3 py-2 rounded-lg border animate-pulse" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                              </div>
                            ) : existingUrls.length === 0 ? (
                              <div className="px-3 py-2 rounded-lg border text-sm" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--muted)' }}>
                                No existing URLs found. Use "New URL" tab to add one.
                              </div>
                            ) : (
                              <select
                                value={selectedUrl}
                                onChange={(e) => setSelectedUrl(e.target.value)}
                                required
                                className="w-full px-3 py-2 rounded-lg border text-sm"
                                style={{
                                  borderColor: 'var(--border)',
                                  background: 'var(--surface-2)',
                                  color: 'var(--fg)'
                                }}
                              >
                                <option value="">Select an existing URL...</option>
                                {existingUrls.map((url, index) => (
                                  <option key={index} value={url}>
                                    {url}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                        )}

                        {/* New URL Input */}
                        {urlSelectionMode === 'new' && (
                          <div>
                            <input
                              type="url"
                              value={newUrlForProject}
                              onChange={(e) => setNewUrlForProject(e.target.value)}
                              placeholder="https://example.com/path"
                              required
                              className="w-full px-3 py-2 rounded-lg border text-sm"
                              style={{
                                borderColor: 'var(--border)',
                                background: 'var(--surface-2)',
                                color: 'var(--fg)'
                              }}
                            />
                            <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
                              Enter a new URL to scan under this project.
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* New Target Mode */}
                {selectedMode === 'new' && (
                  <div className="mb-6">
                    <label className="block text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                      Target URL (prepare DNS verification first)
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
                      Example: https://example.com. We will create or reuse a project and issue a DNS TXT token.
                    </p>
                    {!session.user?.isAdmin && (
                      <button
                        type="button"
                        onClick={prepareNewTarget}
                        disabled={submitting}
                        className="mt-4 px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
                      >
                        {submitting ? 'Verifying...' : 'Verify domain ownership'}
                      </button>
                    )}
                    {/* Admin allowlist visible to all users */}
                    {allowedDomains.length > 0 && (
                      <div className="mt-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                        <div className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
                          Admin allowlist (pre-approved domains)
                        </div>
                        <div className="space-y-1 text-xs" style={{ color: 'var(--muted)' }}>
                          {allowedDomains.map((ad) => (
                            <div key={ad.id} className="flex items-center justify-between">
                              <span className="font-mono text-sm text-gray-200">{ad.domain}</span>
                              <span className="px-2 py-0.5 rounded border" style={{ borderColor: 'var(--border)', color: 'var(--fg)' }}>
                                {ad.scope}
                              </span>
                            </div>
                          ))}
                        </div>
                        {allowedDomainMatch && (
                          <div className="mt-2 text-emerald-300 text-xs">
                            This target matches an allowlisted domain; DNS verification not required.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Domain verification status */}
                {!session.user?.isAdmin && !allowedForSelectedProject && !allowedForTargetUrl && dvStatus && (
                  <div className="mb-4 p-3 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                        Domain verification
                      </div>
                      <span
                        className="text-xs px-2 py-1 rounded"
                        style={{
                          background: dvStatus.status === 'verified' ? '#065f46' : '#92400e',
                          color: 'white',
                        }}
                      >
                        {dvStatus.status}
                      </span>
                    </div>
                    {dvStatus.status !== 'verified' && (
                      <div className="text-xs space-y-1" style={{ color: 'var(--muted)' }}>
                        <div>Add this TXT record to verify:</div>
                        <div className="font-mono text-sm text-gray-200">{dvStatus.challenge_name}</div>
                        <div className="font-mono text-sm text-gray-200">{dvStatus.challenge_value}</div>
                        <div className="text-yellow-400 text-xs mt-1">Scanning is disabled until domain is verified.</div>
                        <button
                          type="button"
                          onClick={refreshVerification}
                          className="text-blue-400 hover:text-blue-300 mt-2 disabled:opacity-60"
                          disabled={dvLoading}
                        >
                          {dvLoading ? 'Checking...' : 'Refresh status'}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {/* Scan Level Selector */}
                {!(selectedMode === 'new' && !session.user?.isAdmin) && (
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
                        <div className="text-xs opacity-80">Fast surface scan</div>
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
                        <div className="text-xs opacity-80">Deeper coverage</div>
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
                        <div className="text-xs opacity-80">Full-stack probes</div>
                      </button>
                    </div>
                  </div>
                )}

                {/* Error State */}
                {error && (
                  <div className="mb-6 p-4 rounded-lg border border-red-500/50 bg-red-500/10">
                    <p className="text-sm text-red-400">{error}</p>
                  </div>
                )}

                {/* Actions (hidden for non-admin new target) */}
                {!(!session.user?.isAdmin && selectedMode === 'new') && (
                  <div className="flex items-center justify-between gap-4">
                    <button
                      type="submit"
                      disabled={
                        submitting ||
                        (selectedMode === 'existing'
                          ? (!selectedProjectId || (!session.user?.isAdmin && !allowedForSelectedProject && dvStatus && dvStatus.status !== 'verified'))
                          : (
                              session.user?.isAdmin
                                ? !targetUrl.trim()
                                : (!preparedProjectId || (!allowedForTargetUrl && dvStatus && dvStatus.status !== 'verified'))
                            ))
                      }
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
                      href="/dashboard/history"
                      className="text-sm font-medium hover:opacity-80 transition-opacity"
                      style={{ color: 'var(--brand)' }}
                    >
                      View scan history
                    </Link>
                  </div>
                )}
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
