'use client';

import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { thandevFetchJSON } from '@/lib/thandevApi';

interface IntegrationConnectGitHubProps {
  projectId: string;
  onConnected?: () => void;
}

type IntegrationStatus = {
  connected: boolean;
  provider: string;
  installation_id?: string | null;
};

type RepoInfo = {
  id: string;
  full_name: string;
  default_branch: string;
  private: boolean;
};

type RepoConnection = {
  id: string;
  project_id: string;
  provider: string;
  provider_repo_id: string;
  full_name: string;
  default_branch?: string | null;
  is_enabled: boolean;
  created_at: string;
};

export default function IntegrationConnectGitHub({ projectId, onConnected }: IntegrationConnectGitHubProps) {
  const { data: session } = useSession();
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [connections, setConnections] = useState<RepoConnection[]>([]);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    loadStatus();
    loadConnections();
  }, [session, projectId]);

  const loadStatus = async () => {
    if (!session) return;
    
    try {
      setLoading(true);
      const data = await thandevFetchJSON<IntegrationStatus>('/api/integrations/github/status', session);
      setStatus(data);
      
      if (data.connected) {
        loadRepos();
      }
    } catch (err) {
      console.error('Failed to load GitHub status:', err);
      setError('Failed to load GitHub integration status');
    } finally {
      setLoading(false);
    }
  };

  const loadRepos = async () => {
    if (!session || !status?.connected) return;
    
    try {
      setReposLoading(true);
      const data = await thandevFetchJSON<{ repos: RepoInfo[] }>('/api/integrations/github/repos', session);
      setRepos(data.repos || []);
    } catch (err) {
      console.error('Failed to load repositories:', err);
      // Don't set error - repos list might be empty
    } finally {
      setReposLoading(false);
    }
  };

  const loadConnections = async () => {
    if (!session) return;
    
    try {
      const data = await thandevFetchJSON<{ items: RepoConnection[] }>(`/api/projects/${projectId}/repos`, session);
      setConnections(data.items || []);
    } catch (err) {
      console.error('Failed to load repo connections:', err);
    }
  };

  const handleInstall = async () => {
    // For MVP, we'll use a simple callback approach
    // In production, this would redirect to GitHub App installation flow
    const installationId = prompt('Enter GitHub App Installation ID:');
    if (!installationId) return;
    
    if (!session) {
      setError('Session required');
      return;
    }
    
    try {
      setConnecting(true);
      await thandevFetchJSON(
        '/api/integrations/github/install-callback',
        session,
        {
          method: 'POST',
          body: JSON.stringify({ installation_id: installationId }),
        }
      );
      
      await loadStatus();
      if (onConnected) {
        onConnected();
      }
    } catch (err) {
      console.error('Failed to install GitHub App:', err);
      setError(err instanceof Error ? err.message : 'Failed to install GitHub App');
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectRepo = async (repo: RepoInfo) => {
    if (!session) {
      setError('Session required');
      return;
    }
    
    try {
      setConnecting(true);
      await thandevFetchJSON(
        `/api/projects/${projectId}/repos/connect`,
        session,
        {
          method: 'POST',
          body: JSON.stringify({
            provider_repo_id: repo.id,
            full_name: repo.full_name,
          }),
        }
      );
      
      await loadConnections();
      if (onConnected) {
        onConnected();
      }
    } catch (err) {
      console.error('Failed to connect repository:', err);
      setError(err instanceof Error ? err.message : 'Failed to connect repository');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisableConnection = async (connectionId: string) => {
    if (!session) return;
    
    try {
      await thandevFetchJSON(
        `/api/projects/${projectId}/repos/${connectionId}/disable`,
        session,
        { method: 'POST' }
      );
      
      await loadConnections();
    } catch (err) {
      console.error('Failed to disable connection:', err);
      setError(err instanceof Error ? err.message : 'Failed to disable connection');
    }
  };

  if (loading) {
    return (
      <div className="p-4">
        <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading GitHub integration status...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-4 rounded-lg border bg-red-50 dark:bg-red-900/20" style={{ borderColor: 'var(--border)' }}>
          <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
        </div>
      )}

      {!status?.connected ? (
        <div className="p-6 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>Connect GitHub</h3>
          <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
            Connect your GitHub account to enable repository dependency scanning.
          </p>
          <button
            onClick={handleInstall}
            disabled={connecting}
            className="px-4 py-2 rounded-lg border font-medium transition disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-80"
            style={{ background: 'var(--brand)', borderColor: 'var(--brand)', color: 'white' }}
          >
            {connecting ? 'Connecting...' : 'Connect GitHub'}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-4 rounded-lg border bg-green-50 dark:bg-green-900/20" style={{ borderColor: 'var(--border)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
              ✅ GitHub connected (Installation ID: {status.installation_id})
            </p>
          </div>

          {/* Connected Repositories */}
          {connections.length > 0 && (
            <div className="p-4 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--fg)' }}>Connected Repositories</h3>
              <div className="space-y-2">
                {connections.map((conn) => (
                  <div key={conn.id} className="flex items-center justify-between p-3 rounded border" style={{ borderColor: 'var(--border)' }}>
                    <div>
                      <p className="font-medium text-sm" style={{ color: 'var(--fg)' }}>{conn.full_name}</p>
                      {conn.default_branch && (
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>Branch: {conn.default_branch}</p>
                      )}
                    </div>
                    <button
                      onClick={() => handleDisableConnection(conn.id)}
                      className="px-3 py-1 text-xs rounded border transition hover:opacity-80"
                      style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--fg)' }}
                    >
                      Disable
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Available Repositories */}
          <div className="p-4 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold" style={{ color: 'var(--fg)' }}>Available Repositories</h3>
              <button
                onClick={loadRepos}
                disabled={reposLoading}
                className="px-3 py-1 text-xs rounded border transition disabled:opacity-50 hover:opacity-80"
                style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--fg)' }}
              >
                {reposLoading ? 'Loading...' : 'Refresh'}
              </button>
            </div>
            
            {reposLoading ? (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>Loading repositories...</p>
            ) : repos.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                No repositories available. Make sure the GitHub App has access to your repositories.
              </p>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {repos.map((repo) => {
                  const isConnected = connections.some(c => c.provider_repo_id === repo.id);
                  return (
                    <div
                      key={repo.id}
                      className="flex items-center justify-between p-3 rounded border"
                      style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}
                    >
                      <div>
                        <p className="font-medium text-sm" style={{ color: 'var(--fg)' }}>{repo.full_name}</p>
                        <p className="text-xs" style={{ color: 'var(--muted)' }}>
                          {repo.private ? 'Private' : 'Public'} • Branch: {repo.default_branch}
                        </p>
                      </div>
                      {isConnected ? (
                        <span className="px-2 py-1 text-xs rounded bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                          Connected
                        </span>
                      ) : (
                        <button
                          onClick={() => handleConnectRepo(repo)}
                          disabled={connecting}
                          className="px-3 py-1 text-xs rounded border transition disabled:opacity-50 hover:opacity-80"
                          style={{ background: 'var(--brand)', borderColor: 'var(--brand)', color: 'white' }}
                        >
                          Connect
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
