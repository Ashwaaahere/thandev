'use client';

import { useSession } from 'next-auth/react';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import { thandevFetchJSON } from '@/lib/thandevApi';

type CodeScanDetail = {
  id: string;
  project_id: string;
  scan_type: string;
  provider: string;
  repo_full_name: string;
  ref?: string;
  sha?: string;
  run_id?: string;
  status: string;
  summary_json?: any;
  meta_json?: any;
  created_at: string;
  completed_at?: string;
};

const TOOL_TABS = ['semgrep', 'gitleaks', 'osv', 'trivy', 'sbom', 'sarif'] as const;
type ToolKey = (typeof TOOL_TABS)[number];

export default function CodeScanDetailPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const params = useParams<{ scanId: string }>();
  const scanId = params?.scanId;

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scan, setScan] = useState<CodeScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ToolKey>('semgrep');

  useEffect(() => {
    if (!session || !scanId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const data = await thandevFetchJSON<CodeScanDetail>(`/api/code-scans/scans/${encodeURIComponent(scanId)}`, session);
        if (!cancelled) setScan(data);
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : 'Failed to load code scan';
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session, scanId]);

  const artifacts = (scan?.meta_json && scan.meta_json.artifacts) || {};

  const currentToolData = (activeTab && artifacts && artifacts[activeTab]) || null;

  const issueCount = (() => {
    if (!currentToolData) return 0;
    if (Array.isArray(currentToolData)) return currentToolData.length;
    if (typeof currentToolData === 'object' && currentToolData !== null) {
      if (Array.isArray((currentToolData as any).results)) return (currentToolData as any).results.length;
      if (Array.isArray((currentToolData as any).issues)) return (currentToolData as any).issues.length;
    }
    return 0;
  })();

  const runUrl: string | undefined = scan?.meta_json?.pipeline_run_url;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <DashboardHeader user={session?.user} onMenuClick={() => setSidebarOpen(true)} />
      <div className="flex">
        <DashboardSidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <main className="flex-1 p-8 overflow-y-auto">
          <div className="max-w-5xl mx-auto space-y-6">
            <button
              type="button"
              onClick={() => router.back()}
              className="text-sm text-slate-300 hover:text-white mb-2"
            >
              ← Back to Code Scan
            </button>

            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              Code Scan Details
              {scan && (
                <span className="px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-100">
                  {scan.provider}
                </span>
              )}
            </h1>

            {loading ? (
              <p className="text-slate-300">Loading code scan…</p>
            ) : error ? (
              <p className="text-red-400 text-sm">{error}</p>
            ) : !scan ? (
              <p className="text-slate-300">Code scan not found.</p>
            ) : (
              <>
                {/* Header summary */}
                <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-5 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm text-slate-100">{scan.repo_full_name}</span>
                    {scan.ref && (
                      <span className="text-xs text-slate-400">
                        {scan.ref}
                      </span>
                    )}
                    {scan.sha && (
                      <span
                        className="text-xs font-mono text-slate-500"
                        title={scan.sha}
                      >
                        {scan.sha.slice(0, 7)}
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                    <span>Status: {scan.status}</span>
                    <span>Created: {new Date(scan.created_at).toLocaleString()}</span>
                    {scan.completed_at && <span>Completed: {new Date(scan.completed_at).toLocaleString()}</span>}
                    {runUrl && (
                      <a
                        href={runUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-400 hover:text-blue-300 underline"
                      >
                        View CI run
                      </a>
                    )}
                  </div>
                  {scan.summary_json && Array.isArray(scan.summary_json.sources) && (
                    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
                      <span className="text-slate-400">Sources:</span>
                      {scan.summary_json.sources.map((src: string) => (
                        <span
                          key={src}
                          className="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-600 text-[11px] uppercase tracking-wide"
                        >
                          {src}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Tool tabs */}
                <div className="rounded-xl border border-slate-700 bg-slate-900/60">
                  <div className="border-b border-slate-700 px-4 pt-3">
                    <div className="flex flex-wrap gap-2">
                      {TOOL_TABS.map((tool) => (
                        <button
                          key={tool}
                          type="button"
                          onClick={() => setActiveTab(tool)}
                          className={`px-3 py-2 text-xs font-medium rounded-t-lg ${
                            activeTab === tool
                              ? 'bg-slate-800 text-white border-x border-t border-slate-700'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {tool.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="p-4 space-y-3">
                    {currentToolData ? (
                      <>
                        <div className="flex items-center justify-between text-xs text-slate-300">
                          <span>
                            Issues detected:{' '}
                            <span className="font-semibold text-slate-100">
                              {issueCount}
                            </span>
                          </span>
                          <span className="text-slate-500">
                            Tab shows raw JSON for <span className="font-mono">{activeTab}</span>
                          </span>
                        </div>
                        <div className="max-h-[480px] overflow-auto rounded-lg bg-slate-950 border border-slate-800">
                          <pre className="p-3 text-xs text-slate-100 whitespace-pre-wrap break-all">
                            {JSON.stringify(currentToolData, null, 2)}
                          </pre>
                        </div>
                      </>
                    ) : (
                      <p className="text-sm text-slate-400">
                        No data uploaded for this tool.
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

