'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import Link from 'next/link';
import { thandevFetchJSON } from '@/lib/thandevApi';

type FindingListItem = {
  id: string;
  scan_id: string;
  project_id: string;
  project_name: string;
  target_url: string;
  severity: string;
  status: string;
  title: string;
  description?: string | null;
  cve_id?: string | null;
  cwe_id?: string | null;
  cvss_score?: number | null;
  tool?: string | null;
  categories?: string[] | null;
  url?: string | null;
  path?: string | null;
  vuln_type?: string | null;
  remediation_summary?: string | null;
  remediation_steps?: string | null;
  impact_summary?: string | null;
};

type FindingsResponse = {
  items: FindingListItem[];
  total: number;
};

export default function CVEDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { data: session, status: sessionStatus } = useSession();
  const [findings, setFindings] = useState<FindingListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cveId = params?.cveId as string;

  useEffect(() => {
    async function loadFindings() {
      if (sessionStatus !== 'authenticated' || !session || !cveId) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Try to search by CVE ID first (if backend supports it)
        // Otherwise fetch all and filter client-side
        let data: FindingsResponse;
        try {
          data = await thandevFetchJSON<FindingsResponse>(
            `/api/findings?limit=1000&search=${encodeURIComponent(cveId)}`,
            session
          );
        } catch {
          // Fallback: fetch all and filter
          data = await thandevFetchJSON<FindingsResponse>(
            `/api/findings?limit=1000`,
            session
          );
        }

        // Filter findings for this CVE (case-insensitive)
        const cveFindings = data.items.filter(
          (finding) => finding.cve_id?.toUpperCase() === cveId.toUpperCase()
        );

        setFindings(cveFindings);
      } catch (e) {
        console.error('Error loading CVE findings:', e);
        setError('Failed to load vulnerability details');
      } finally {
        setLoading(false);
      }
    }

    loadFindings();
  }, [sessionStatus, session, cveId]);

  if (sessionStatus === 'loading' || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--brand)]"></div>
          <p className="mt-4 text-sm" style={{ color: 'var(--muted)' }}>Loading vulnerability details...</p>
        </div>
      </div>
    );
  }

  if (error || !cveId) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        <div className="text-center max-w-md">
          <h1 className="text-2xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Vulnerability Not Found</h1>
          <p className="mb-6" style={{ color: 'var(--muted)' }}>
            {error || 'Invalid CVE ID'}
          </p>
          <Link
            href="/dashboard/vulnerabilities"
            className="inline-block px-4 py-2 rounded-lg font-semibold transition-colors"
            style={{ background: 'var(--brand)', color: 'white' }}
          >
            ← Back to Vulnerabilities
          </Link>
        </div>
      </div>
    );
  }

  // Aggregate data from all findings
  const uniqueFindings = Array.from(
    new Map(findings.map((f) => [f.id, f])).values()
  );

  const severityCounts = uniqueFindings.reduce(
    (acc, f) => {
      acc[f.severity] = (acc[f.severity] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  const maxSeverity = uniqueFindings.reduce((max, f) => {
    const severityOrder = { critical: 5, high: 4, medium: 3, low: 2, info: 1 };
    return severityOrder[f.severity as keyof typeof severityOrder] >
      severityOrder[max.severity as keyof typeof severityOrder]
      ? f
      : max;
  }, uniqueFindings[0]);

  const avgCvssScore =
    uniqueFindings
      .filter((f) => f.cvss_score != null)
      .reduce((sum, f) => sum + (f.cvss_score || 0), 0) /
    uniqueFindings.filter((f) => f.cvss_score != null).length;

  const affectedProjects = Array.from(
    new Set(uniqueFindings.map((f) => f.project_name))
  );

  const affectedUrls = Array.from(
    new Set(uniqueFindings.map((f) => f.target_url).filter(Boolean))
  );

  const tools = Array.from(
    new Set(uniqueFindings.map((f) => f.tool).filter(Boolean))
  );

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link
            href="/dashboard/vulnerabilities"
            className="inline-flex items-center gap-2 text-sm mb-4 hover:underline"
            style={{ color: 'var(--muted)' }}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Vulnerabilities
          </Link>

          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold mb-2 font-mono" style={{ color: 'var(--fg)' }}>
                {cveId.toUpperCase()}
              </h1>
              {maxSeverity && (
                <div className="flex items-center gap-3">
                  <span
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      maxSeverity.severity === 'critical'
                        ? 'bg-red-900/40 text-red-200 border border-red-500/50'
                        : maxSeverity.severity === 'high'
                        ? 'bg-orange-900/40 text-orange-200 border border-orange-500/50'
                        : maxSeverity.severity === 'medium'
                        ? 'bg-yellow-900/40 text-yellow-200 border border-yellow-500/50'
                        : maxSeverity.severity === 'low'
                        ? 'bg-green-900/40 text-green-200 border border-green-500/50'
                        : 'bg-blue-900/40 text-blue-200 border border-blue-500/50'
                    }`}
                  >
                    {maxSeverity.severity.toUpperCase()}
                  </span>
                  {avgCvssScore > 0 && (
                    <span className="text-sm" style={{ color: 'var(--muted)' }}>
                      CVSS: {avgCvssScore.toFixed(1)}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="rounded-lg border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="text-sm mb-1" style={{ color: 'var(--muted)' }}>Total Findings</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
              {uniqueFindings.length}
            </div>
          </div>
          <div className="rounded-lg border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="text-sm mb-1" style={{ color: 'var(--muted)' }}>Affected Projects</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
              {affectedProjects.length}
            </div>
          </div>
          <div className="rounded-lg border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="text-sm mb-1" style={{ color: 'var(--muted)' }}>Affected URLs</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
              {affectedUrls.length}
            </div>
          </div>
          <div className="rounded-lg border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="text-sm mb-1" style={{ color: 'var(--muted)' }}>Detection Tools</div>
            <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
              {tools.length}
            </div>
          </div>
        </div>

        {/* Vulnerability Details */}
        {maxSeverity && (
          <div className="rounded-lg border p-6 mb-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Vulnerability Details</h2>

            <div className="space-y-4">
              {maxSeverity.title && (
                <div>
                  <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Title</div>
                  <div style={{ color: 'var(--fg)' }}>{maxSeverity.title}</div>
                </div>
              )}

              {maxSeverity.description && (
                <div>
                  <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Description</div>
                  <div className="whitespace-pre-wrap" style={{ color: 'var(--fg)' }}>
                    {maxSeverity.description}
                  </div>
                </div>
              )}

              {maxSeverity.impact_summary && (
                <div>
                  <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Impact</div>
                  <div style={{ color: 'var(--fg)' }}>{maxSeverity.impact_summary}</div>
                </div>
              )}

              {maxSeverity.cwe_id && (
                <div>
                  <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>CWE ID</div>
                  <div className="font-mono" style={{ color: 'var(--fg)' }}>{maxSeverity.cwe_id}</div>
                </div>
              )}

              {maxSeverity.categories && maxSeverity.categories.length > 0 && (
                <div>
                  <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Categories</div>
                  <div className="flex flex-wrap gap-2">
                    {maxSeverity.categories.map((cat) => (
                      <span
                        key={cat}
                        className="px-2 py-1 rounded text-xs"
                        style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}
                      >
                        {cat}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Remediation */}
        {maxSeverity?.remediation_summary && (
          <div className="rounded-lg border p-6 mb-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Remediation</h2>
            <div style={{ color: 'var(--fg)' }}>{maxSeverity.remediation_summary}</div>
            {maxSeverity.remediation_steps && (
              <div className="mt-4">
                <div className="text-sm font-medium mb-2" style={{ color: 'var(--muted)' }}>Steps</div>
                <div className="whitespace-pre-wrap" style={{ color: 'var(--fg)' }}>
                  {maxSeverity.remediation_steps}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Affected Assets */}
        <div className="rounded-lg border p-6 mb-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Affected Assets</h2>

          {affectedProjects.length > 0 && (
            <div className="mb-4">
              <div className="text-sm font-medium mb-2" style={{ color: 'var(--muted)' }}>Projects</div>
              <div className="space-y-1">
                {affectedProjects.map((project) => (
                  <Link
                    key={project}
                    href={`/dashboard/vulnerabilities?project=${encodeURIComponent(project)}`}
                    className="block text-sm hover:underline"
                    style={{ color: 'var(--brand)' }}
                  >
                    {project}
                  </Link>
                ))}
              </div>
            </div>
          )}

          {affectedUrls.length > 0 && (
            <div>
              <div className="text-sm font-medium mb-2" style={{ color: 'var(--muted)' }}>Target URLs</div>
              <div className="space-y-1">
                {affectedUrls.map((url) => (
                  <div key={url} className="text-sm font-mono" style={{ color: 'var(--fg)' }}>
                    {url}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Findings List */}
        <div className="rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="p-6 border-b" style={{ borderColor: 'var(--border)' }}>
            <h2 className="text-xl font-bold" style={{ color: 'var(--fg)' }}>
              All Findings ({uniqueFindings.length})
            </h2>
          </div>

          <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {uniqueFindings.map((finding) => (
              <Link
                key={finding.id}
                href={`/dashboard/vulnerabilities?id=${finding.id}`}
                className="block p-6 hover:bg-[var(--surface-2)] transition-colors"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          finding.severity === 'critical'
                            ? 'bg-red-900/40 text-red-200'
                            : finding.severity === 'high'
                            ? 'bg-orange-900/40 text-orange-200'
                            : finding.severity === 'medium'
                            ? 'bg-yellow-900/40 text-yellow-200'
                            : finding.severity === 'low'
                            ? 'bg-green-900/40 text-green-200'
                            : 'bg-blue-900/40 text-blue-200'
                        }`}
                      >
                        {finding.severity.toUpperCase()}
                      </span>
                      {finding.tool && (
                        <span className="text-xs px-2 py-1 rounded" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                          {finding.tool}
                        </span>
                      )}
                    </div>
                    <h3 className="font-semibold mb-1" style={{ color: 'var(--fg)' }}>{finding.title}</h3>
                    {finding.url && (
                      <div className="text-sm font-mono truncate" style={{ color: 'var(--muted)' }}>
                        {finding.url}
                      </div>
                    )}
                    {finding.project_name && (
                      <div className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                        Project: {finding.project_name}
                      </div>
                    )}
                  </div>
                  <svg className="w-5 h-5 flex-shrink-0" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

