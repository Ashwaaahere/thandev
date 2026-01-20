'use client';

import React, { useState } from 'react';

type Package = {
  ecosystem: string;
  name: string;
  version: string;
  paths: string[];
};

type Finding = {
  type: string;
  ecosystem: string;
  package: string;
  version: string;
  vuln_id: string;
  severity: string;
  fixed?: string | null;
  paths: string[];
  references: string[];
};

type RepoSCAArtifact = {
  mode: string;
  repo: {
    provider: string;
    full_name: string;
    commit?: string | null;
    branch: string;
  };
  packages: Package[];
  findings: Finding[];
  meta: {
    tool_versions: Record<string, string>;
    duration_ms: number;
  };
};

interface RepoDependenciesPanelProps {
  artifact: RepoSCAArtifact | null;
  loading: boolean;
}

export default function RepoDependenciesPanel({ artifact, loading }: RepoDependenciesPanelProps) {
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [ecosystemFilter, setEcosystemFilter] = useState<string>('all');

  if (loading) {
    return (
      <div className="p-6 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2" style={{ borderColor: 'var(--fg)' }}></div>
          <p style={{ color: 'var(--fg)' }}>Scanning repository dependencies...</p>
        </div>
        <p className="text-sm mt-2" style={{ color: 'var(--muted)' }}>
          Analyzing lockfiles and manifests from the connected repository.
        </p>
      </div>
    );
  }

  if (!artifact) {
    return (
      <div className="p-6 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
          ℹ️ Scanned using lockfiles/manifests from connected repository.
        </p>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No repository dependency scan results available for this scan.
        </p>
        <p className="text-sm mt-2" style={{ color: 'var(--muted)' }}>
          If the scan is still running, results will appear here when the repository scan completes.
        </p>
      </div>
    );
  }

  const { repo, packages, findings } = artifact;

  // Filter findings
  const filteredFindings = findings.filter(f => {
    if (severityFilter !== 'all' && f.severity !== severityFilter) return false;
    if (ecosystemFilter !== 'all' && f.ecosystem !== ecosystemFilter) return false;
    return true;
  });

  // Get unique ecosystems and severities
  const ecosystems = Array.from(new Set(findings.map(f => f.ecosystem)));
  const severities = Array.from(new Set(findings.map(f => f.severity)));

  return (
    <div className="space-y-6">
      {/* Disclaimer */}
      <div className="p-4 rounded-lg border bg-blue-50 dark:bg-blue-900/20" style={{ borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
          ℹ️ Scanned using lockfiles/manifests from connected repository.
        </p>
      </div>

      {/* Repository Info */}
      <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Repository</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Repository</p>
            <p style={{ color: 'var(--fg)' }}>{repo.full_name}</p>
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Branch</p>
            <p style={{ color: 'var(--fg)' }}>{repo.branch}</p>
          </div>
        </div>
      </div>

      {/* Summary */}
      <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Summary</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{packages.length}</p>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>Packages</p>
          </div>
          <div>
            <p className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{findings.length}</p>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>Vulnerabilities</p>
          </div>
          <div>
            <p className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>{ecosystems.length}</p>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>Ecosystems</p>
          </div>
        </div>
      </div>

      {/* Filters */}
      {findings.length > 0 && (
        <div className="rounded-lg border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <div className="flex gap-4">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Severity</label>
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="px-3 py-2 rounded border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--fg)' }}
              >
                <option value="all">All</option>
                {severities.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Ecosystem</label>
              <select
                value={ecosystemFilter}
                onChange={(e) => setEcosystemFilter(e.target.value)}
                className="px-3 py-2 rounded border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--fg)' }}
              >
                <option value="all">All</option>
                {ecosystems.map(e => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Findings */}
      {filteredFindings.length > 0 ? (
        <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>
            Vulnerabilities ({filteredFindings.length})
          </h3>
          <div className="space-y-3">
            {filteredFindings.map((finding, idx) => (
              <div key={idx} className="p-4 rounded border" style={{ borderColor: 'var(--border)' }}>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="font-medium" style={{ color: 'var(--fg)' }}>
                      {finding.package} {finding.version} ({finding.ecosystem})
                    </p>
                    <p className="text-sm" style={{ color: 'var(--muted)' }}>Vuln ID: {finding.vuln_id}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {finding.fixed && (
                      <span className="text-sm px-2 py-1 rounded bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                        Fixed in {finding.fixed}
                      </span>
                    )}
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        finding.severity === 'critical' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                        finding.severity === 'high' ? 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200' :
                        finding.severity === 'medium' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                        'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
                      }`}
                    >
                      {finding.severity}
                    </span>
                  </div>
                </div>
                <div className="mt-2">
                  <p className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Paths:</p>
                  <ul className="list-disc list-inside text-sm" style={{ color: 'var(--muted)' }}>
                    {finding.paths.map((path, pathIdx) => (
                      <li key={pathIdx}>{path}</li>
                    ))}
                  </ul>
                </div>
                {finding.references && finding.references.length > 0 && (
                  <div className="mt-2">
                    <p className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>References:</p>
                    <ul className="list-disc list-inside text-sm" style={{ color: 'var(--muted)' }}>
                      {finding.references.map((ref, refIdx) => (
                        <li key={refIdx}>
                          <a href={ref} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400">
                            {ref}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : findings.length > 0 ? (
        <div className="p-6 rounded-lg border text-center" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <p style={{ color: 'var(--muted)' }}>No vulnerabilities match the selected filters.</p>
        </div>
      ) : (
        <div className="p-6 rounded-lg border text-center" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <p style={{ color: 'var(--muted)' }}>No vulnerabilities detected in repository dependencies.</p>
        </div>
      )}
    </div>
  );
}
