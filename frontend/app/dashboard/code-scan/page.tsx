'use client';

import Link from 'next/link';
import { useSession } from 'next-auth/react';
import { useState, useEffect } from 'react';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import { thandevFetchJSON } from '@/lib/thandevApi';

type Project = { id: string; name: string; target_url?: string };
type LinkedRepo = {
  id: string;
  project_id: string;
  provider: string;
  repo_full_name: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
};

type CodeScanItem = {
  id: string;
  project_id: string;
  scan_type: string;
  provider: string;
  repo_full_name: string;
  ref?: string;
  sha?: string;
  run_id?: string;
  status: string;
  created_at: string;
  completed_at?: string;
};

const CI_PROVIDERS = [
  { id: 'github', label: 'GitHub Actions', enabled: true },
  { id: 'bitbucket', label: 'Bitbucket Pipelines', enabled: false },
  { id: 'gitlab', label: 'GitLab CI', enabled: false },
  { id: 'circleci', label: 'CircleCI', enabled: false },
  { id: 'azuredevops', label: 'Azure DevOps', enabled: false },
];

const GITHUB_WORKFLOW_SNIPPET = `# Add to .github/workflows/code-scan.yml (or your workflow)
jobs:
  code-scan:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Request OIDC token
        id: oidc
        uses: actions/github-auth@v2
        with:
          audience: thandev

      # Exchange OIDC token for Thandev ingest token
      - name: Get Thandev ingest token
        id: token
        run: |
          RESP=$(curl -s -X POST "\${THANDEV_BASE_URL}/api/code-scans/oidc/exchange/github" \\
            -H "Content-Type: application/json" \\
            -d "{\\"oidc_token\\": \\"\${{ steps.oidc.outputs.id_token }}\\"}")
          echo "access_token=$(echo $RESP | jq -r '.access_token')" >> $GITHUB_OUTPUT

      # Run your code scan tools (Semgrep, Gitleaks, etc.), then upload:
      - name: Ingest to Thandev
        run: |
          # Upload artifacts (example: semgrep JSON) with the ingest token
          curl -X POST "\${THANDEV_BASE_URL}/api/code-scans/ingest" \\
            -H "Authorization: Bearer \${{ steps.token.outputs.access_token }}" \\
            -F "repo=\${{ github.repository }}" \\
            -F "ref=\${{ github.ref }}" \\
            -F "sha=\${{ github.sha }}" \\
            -F "run_id=\${{ github.run_id }}" \\
            -F "run_url=\${{ github.server_url }}/\${{ github.repository }}/actions/runs/\${{ github.run_id }}" \\
            -F "semgrep_json=@semgrep-output.json"
`;

export default function CodeScanPage() {
  const { data: session } = useSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [provider, setProvider] = useState<string>('github');
  const [repoFullName, setRepoFullName] = useState('');
  const [linkedRepos, setLinkedRepos] = useState<LinkedRepo[]>([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingLinked, setLoadingLinked] = useState(false);
  const [linking, setLinking] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [codeScans, setCodeScans] = useState<CodeScanItem[]>([]);
  const [loadingScans, setLoadingScans] = useState(false);
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');
  const [creatingProject, setCreatingProject] = useState(false);
  const [unlinkConfirm, setUnlinkConfirm] = useState<LinkedRepo | null>(null);
  const [unlinking, setUnlinking] = useState(false);

  const fetchProjects = async () => {
    if (!session) return;
    setLoadingProjects(true);
    try {
      const data = await thandevFetchJSON<{ items: Project[] }>('/api/projects', session);
      setProjects(data?.items ?? []);
      if (data?.items?.length && !selectedProjectId) setSelectedProjectId(data.items[0].id);
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to load projects' });
    } finally {
      setLoadingProjects(false);
    }
  };

  useEffect(() => {
    if (!session) return;
    fetchProjects();
  }, [session]);

  useEffect(() => {
    if (!session || !selectedProjectId) {
      setLinkedRepos([]);
      return;
    }
    let cancelled = false;
    setLoadingLinked(true);
    (async () => {
      try {
        const data = await thandevFetchJSON<{ items: LinkedRepo[] }>(
          `/api/code-scans/linked-repos?project_id=${encodeURIComponent(selectedProjectId)}`,
          session
        );
        if (!cancelled) setLinkedRepos(data?.items ?? []);
      } catch {
        if (!cancelled) setLinkedRepos([]);
      } finally {
        if (!cancelled) setLoadingLinked(false);
      }
    })();
    return () => { cancelled = true; };
  }, [session, selectedProjectId]);

  useEffect(() => {
    if (!session || !selectedProjectId) {
      setCodeScans([]);
      return;
    }
    let cancelled = false;
    setLoadingScans(true);

    const loadScans = async () => {
      try {
        const data = await thandevFetchJSON<{ items: CodeScanItem[] }>(
          `/api/code-scans/scans?project_id=${encodeURIComponent(selectedProjectId)}&limit=10`,
          session
        );
        const next = data?.items ?? [];
        if (cancelled) return;
        setCodeScans((prev) => {
          if (prev.length === next.length && JSON.stringify(prev) === JSON.stringify(next)) {
            return prev;
          }
          return next;
        });
      } catch {
        if (!cancelled) setCodeScans([]);
      } finally {
        if (!cancelled) setLoadingScans(false);
      }
    };

    // Initial load + gentle polling for new data
    loadScans();
    const intervalId = window.setInterval(loadScans, 30000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [session, selectedProjectId]);

  const handleLinkRepo = async () => {
    if (!session || !selectedProjectId || !repoFullName.trim()) {
      setMessage({ type: 'error', text: 'Select a project and enter repo (e.g. owner/repo)' });
      return;
    }
    setLinking(true);
    setMessage(null);
    try {
      await thandevFetchJSON('/api/code-scans/link-repo', session, {
        method: 'POST',
        body: JSON.stringify({
          project_id: selectedProjectId,
          provider,
          repo_full_name: repoFullName.trim(),
        }),
        headers: { 'Content-Type': 'application/json' },
      });
      setMessage({ type: 'success', text: 'Repo linked. You can now run code scans from CI.' });
      setRepoFullName('');
      const data = await thandevFetchJSON<{ items: LinkedRepo[] }>(
        `/api/code-scans/linked-repos?project_id=${encodeURIComponent(selectedProjectId)}`,
        session
      );
      setLinkedRepos(data?.items ?? []);
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to link repo' });
    } finally {
      setLinking(false);
    }
  };

  const handleCreateProject = async () => {
    const name = newProjectName.trim();
    if (!session || !name) {
      setMessage({ type: 'error', text: 'Project name is required' });
      return;
    }
    setCreatingProject(true);
    setMessage(null);
    try {
      const created = await thandevFetchJSON<{ id: string }>('/api/projects/quick', session, {
        method: 'POST',
        body: JSON.stringify({ name, description: newProjectDescription.trim() || undefined }),
        headers: { 'Content-Type': 'application/json' },
      });
      await fetchProjects();
      setSelectedProjectId(created.id);
      setNewProjectOpen(false);
      setNewProjectName('');
      setNewProjectDescription('');
      setMessage({ type: 'success', text: 'Project created. You can now link a repo.' });
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Failed to create project' });
    } finally {
      setCreatingProject(false);
    }
  };

  const handleUnlink = async () => {
    if (!session || !unlinkConfirm) return;
    setUnlinking(true);
    setMessage(null);
    const body = JSON.stringify({ linked_repo_id: unlinkConfirm.id });
    const tryUnlink = async (url: string): Promise<void> => {
      await thandevFetchJSON(url, session, { method: 'POST', body });
    };
    try {
      try {
        await tryUnlink('/api/code-scans/unlink-repo');
      } catch (first: unknown) {
        const is404 =
          first instanceof Error &&
          (first.message.includes('404') || first.message.includes('Not Found'));
        if (is404 && typeof window !== 'undefined') {
          const proxyUrl = `${window.location.origin}/api/code-scans/unlink-repo`;
          await tryUnlink(proxyUrl);
        } else {
          throw first;
        }
      }
      setLinkedRepos((prev) => prev.filter((r) => r.id !== unlinkConfirm.id));
      setUnlinkConfirm(null);
      setMessage({ type: 'success', text: 'Repo unlinked.' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to unlink repo';
      setMessage({ type: 'error', text: msg });
    } finally {
      setUnlinking(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950">
      <DashboardHeader user={session?.user} onMenuClick={() => setSidebarOpen(true)} />
      <div className="flex">
        <DashboardSidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-5xl mx-auto px-8 py-8 space-y-8">
            <div>
              <h1 className="text-3xl font-bold text-white">Code Security Scans</h1>
              <p className="mt-2 text-slate-300 max-w-2xl">
                Turn every CI run into a security gate. Connect your pipelines once, and Thandev will
                continuously ingest, normalize, and surface code vulnerabilities for every push.
              </p>
            </div>

            {/* CI Provider */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3 mb-3">
                <h2 className="text-lg font-semibold text-white">Connect your CI</h2>
                <p className="text-xs text-slate-400">
                  Select where your pipelines run. GitHub Actions is fully supported today.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                {CI_PROVIDERS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => p.enabled && setProvider(p.id)}
                    className={`px-4 py-2 rounded-lg border text-sm font-medium ${
                      provider === p.id
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : p.enabled
                          ? 'bg-slate-700 border-slate-600 text-slate-200 hover:border-slate-500'
                          : 'bg-slate-800 border-slate-700 text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    {p.label}
                    {!p.enabled && ' (Coming soon)'}
                  </button>
                ))}
              </div>
            </div>

            {/* Link repo */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3 mb-4">
                <h2 className="text-lg font-semibold text-white">Authorize repositories</h2>
                <p className="text-xs text-slate-400 max-w-sm text-right">
                  Only linked repos can send findings. This prevents noise from untrusted projects and
                  keeps your code security data clean.
                </p>
              </div>
              {loadingProjects ? (
                <p className="text-slate-400">Loading projects...</p>
              ) : projects.length === 0 ? (
                <div className="rounded-lg border border-slate-600 bg-slate-900/50 p-6 text-center">
                  <p className="text-slate-300 mb-4">No projects yet. Create a project to link repos and ingest code scans.</p>
                  <button
                    type="button"
                    onClick={() => setNewProjectOpen(true)}
                    className="px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500"
                  >
                    Create Project
                  </button>
                </div>
              ) : (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">Project</label>
                      <div className="flex gap-2">
                        <select
                          value={selectedProjectId}
                          onChange={(e) => setSelectedProjectId(e.target.value)}
                          className="flex-1 px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                        >
                          {projects.map((proj) => (
                            <option key={proj.id} value={proj.id}>{proj.name}</option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => setNewProjectOpen(true)}
                          className="px-3 py-2 rounded-lg border border-slate-600 text-slate-200 text-sm font-medium hover:bg-slate-700"
                          title="New Project"
                        >
                          + New Project
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">Repo (e.g. owner/repo)</label>
                      <input
                        type="text"
                        value={repoFullName}
                        onChange={(e) => setRepoFullName(e.target.value)}
                        placeholder="acme/cool-app"
                        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleLinkRepo}
                    disabled={linking || !repoFullName.trim()}
                    className="mt-4 px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {linking ? 'Linking...' : 'Link repo'}
                  </button>
                </>
              )}
              {message && (
                <p className={`mt-3 text-sm ${message.type === 'success' ? 'text-green-400' : 'text-red-400'}`}>
                  {message.text}
                </p>
              )}
            </div>

            {/* Recent code scans (provider badge) */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-white mb-3">Recent code scans</h2>
              {loadingScans ? (
                <p className="text-slate-400">Loading...</p>
              ) : codeScans.length === 0 ? (
                <p className="text-slate-400">
                  No code scans yet. Link a repository and run your CI pipeline to establish a baseline.
                </p>
              ) : (
                <ul className="space-y-2">
                  {codeScans.map((s) => (
                    <li key={s.id}>
                      <Link
                        href={`/dashboard/code-scan/${encodeURIComponent(s.id)}`}
                        className="flex items-center justify-between gap-4 rounded-lg border border-slate-800/80 bg-slate-900/80 px-4 py-3 text-slate-200 hover:border-slate-500 hover:bg-slate-800/80 transition-colors"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-50">
                              {s.provider}
                            </span>
                            <span className="font-mono text-sm truncate max-w-[220px]">
                              {s.repo_full_name}
                            </span>
                          </div>
                          <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-400">
                            <span>
                              Started: {new Date(s.created_at).toLocaleString()}
                            </span>
                            {s.completed_at && (
                              <span>
                                Completed: {new Date(s.completed_at).toLocaleString()}
                              </span>
                            )}
                            {s.ref && <span>Ref: {s.ref}</span>}
                            {s.sha && (
                              <span className="font-mono" title={s.sha}>
                                SHA: {s.sha.slice(0, 7)}
                              </span>
                            )}
                          </div>
                        </div>
                        <span
                          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${
                            s.status === 'completed'
                              ? 'bg-emerald-900/60 text-emerald-200 border border-emerald-600/70'
                              : s.status === 'running'
                                ? 'bg-blue-900/60 text-blue-200 border border-blue-600/70'
                                : s.status === 'failed'
                                  ? 'bg-red-900/60 text-red-200 border border-red-600/70'
                                  : 'bg-slate-800 text-slate-200 border border-slate-600/70'
                          }`}
                        >
                          {s.status}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Linked repos list */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-white mb-3">Linked repos</h2>
              {loadingLinked ? (
                <p className="text-slate-400">Loading...</p>
              ) : linkedRepos.length === 0 ? (
                <p className="text-slate-400">No repos linked for this project. Link one above.</p>
              ) : (
                <ul className="space-y-2">
                  {linkedRepos.map((r) => (
                    <li key={r.id} className="flex items-center justify-between gap-2 py-1.5">
                      <div className="flex items-center gap-2 text-slate-200 min-w-0">
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-600 shrink-0">{r.provider}</span>
                        <span className="font-mono text-sm truncate">{r.repo_full_name}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setUnlinkConfirm(r)}
                        className="shrink-0 px-2 py-1 text-xs font-medium rounded border border-slate-600 text-slate-300 hover:bg-slate-700 hover:border-slate-500"
                      >
                        Unlink
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* New Project modal */}
            {newProjectOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={() => !creatingProject && setNewProjectOpen(false)}>
                <div className="rounded-xl border border-slate-700 bg-slate-800 p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-lg font-semibold text-white mb-4">New Project</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">Project name (required)</label>
                      <input
                        type="text"
                        value={newProjectName}
                        onChange={(e) => setNewProjectName(e.target.value)}
                        placeholder="My App"
                        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500"
                        autoFocus
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-300 mb-1">Description (optional)</label>
                      <input
                        type="text"
                        value={newProjectDescription}
                        onChange={(e) => setNewProjectDescription(e.target.value)}
                        placeholder="Code scan project"
                        className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white placeholder-slate-500"
                      />
                    </div>
                  </div>
                  <div className="flex gap-2 mt-6 justify-end">
                    <button
                      type="button"
                      onClick={() => !creatingProject && setNewProjectOpen(false)}
                      className="px-4 py-2 rounded-lg border border-slate-600 text-slate-200 hover:bg-slate-700"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleCreateProject}
                      disabled={creatingProject || !newProjectName.trim()}
                      className="px-4 py-2 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {creatingProject ? 'Creating...' : 'Create'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Unlink confirm modal */}
            {unlinkConfirm && (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={() => !unlinking && setUnlinkConfirm(null)}>
                <div className="rounded-xl border border-slate-700 bg-slate-800 p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-lg font-semibold text-white mb-2">Unlink repo?</h3>
                  <p className="text-slate-300 text-sm mb-4">
                    This will remove <span className="font-mono text-slate-200">{unlinkConfirm.repo_full_name}</span> from the allowlist. Code scans from CI for this repo will no longer be accepted. Existing scan data is kept.
                  </p>
                  <div className="flex gap-2 justify-end">
                    <button
                      type="button"
                      onClick={() => !unlinking && setUnlinkConfirm(null)}
                      className="px-4 py-2 rounded-lg border border-slate-600 text-slate-200 hover:bg-slate-700"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleUnlink}
                      disabled={unlinking}
                      className="px-4 py-2 rounded-lg bg-red-600/90 text-white font-medium hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {unlinking ? 'Unlinking...' : 'Unlink'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* GitHub workflow snippet */}
            {provider === 'github' && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-white mb-3">GitHub Actions workflow</h2>
                <p className="text-slate-400 text-sm mb-3">
                  Set <code className="bg-slate-900 px-1 rounded">THANDEV_BASE_URL</code> in your repo secrets (e.g. https://api.thandev.com).
                  For local testing with <code className="bg-slate-900 px-1 rounded">act</code>, use <code className="bg-slate-900 px-1 rounded">CODE_SCAN_OIDC_MODE=dev</code> and <code className="bg-slate-900 px-1 rounded">oidc_token: &quot;dev-local&quot;</code> with <code className="bg-slate-900 px-1 rounded">repo_full_name</code> in the request.
                </p>
                <pre className="p-4 rounded-lg bg-slate-900 border border-slate-700 text-slate-300 text-xs overflow-x-auto whitespace-pre">
                  {GITHUB_WORKFLOW_SNIPPET}
                </pre>
              </div>
            )}

            {/* Placeholder for other providers */}
            {provider !== 'github' && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-6 shadow-sm">
                <h2 className="text-lg font-semibold text-white mb-2">Setup for {CI_PROVIDERS.find((p) => p.id === provider)?.label ?? provider}</h2>
                <p className="text-slate-400">Coming soon. Use GitHub Actions for now.</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
