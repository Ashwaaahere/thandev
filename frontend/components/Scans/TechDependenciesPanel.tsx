'use client';

import React from 'react';

type Technology = {
  name: string;
  version?: string | null;
  confidence: number;
};

type ClientDependency = {
  name: string;
  version: string;
  evidence: string;
  confidence: number;
};

type Finding = {
  type: string;
  package: string;
  version: string;
  severity: string;
  evidence: string;
  references?: string[];
  confidence: number;
};

type URLSCAArtifact = {
  mode: string;
  target: string;
  fingerprint: {
    status: number;
    title: string;
    server: string;
    cdn: string;
    technologies: Technology[];
    confidence: number;
  };
  client_dependencies: ClientDependency[];
  findings: Finding[];
  meta: {
    tool_versions: Record<string, string>;
    duration_ms: number;
  };
};

interface TechDependenciesPanelProps {
  artifact: URLSCAArtifact | null;
  loading: boolean;
}

export default function TechDependenciesPanel({ artifact, loading }: TechDependenciesPanelProps) {
  if (loading) {
    return (
      <div className="p-6 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2" style={{ borderColor: 'var(--fg)' }}></div>
          <p style={{ color: 'var(--fg)' }}>Collecting tech signals and dependencies...</p>
        </div>
        <p className="text-sm mt-2" style={{ color: 'var(--muted)' }}>
          This may take a few moments. Scanning headers, technologies, and client-side JavaScript.
        </p>
      </div>
    );
  }

  if (!artifact) {
    return (
      <div className="p-6 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium mb-2" style={{ color: 'var(--fg)' }}>
          ℹ️ Externally observable only. Backend dependencies require repo connection.
        </p>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          No dependency scan results available for this scan.
        </p>
        <p className="text-sm mt-2" style={{ color: 'var(--muted)' }}>
          If the scan is still running, results will appear here when the dependency scan completes.
        </p>
      </div>
    );
  }

  const { fingerprint, client_dependencies, findings } = artifact;

  return (
    <div className="space-y-6">
      {/* Disclaimer */}
      <div className="p-4 rounded-lg border bg-yellow-50 dark:bg-yellow-900/20" style={{ borderColor: 'var(--border)' }}>
        <p className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
          ℹ️ Externally observable only. Backend dependencies require repo connection.
        </p>
      </div>

      {/* Fingerprint */}
      <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Target Fingerprint</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Status</p>
            <p style={{ color: 'var(--fg)' }}>{fingerprint.status}</p>
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Title</p>
            <p style={{ color: 'var(--fg)' }}>{fingerprint.title || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Server</p>
            <p style={{ color: 'var(--fg)' }}>{fingerprint.server || 'N/A'}</p>
          </div>
          <div>
            <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>CDN</p>
            <p style={{ color: 'var(--fg)' }}>{fingerprint.cdn || 'N/A'}</p>
          </div>
        </div>
      </div>

      {/* Technologies */}
      {fingerprint.technologies && fingerprint.technologies.length > 0 && (
        <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Technologies Detected</h3>
          <div className="space-y-2">
            {fingerprint.technologies.map((tech, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 rounded border" style={{ borderColor: 'var(--border)' }}>
                <div>
                  <p className="font-medium" style={{ color: 'var(--fg)' }}>{tech.name}</p>
                  {tech.version && (
                    <p className="text-sm" style={{ color: 'var(--muted)' }}>Version: {tech.version}</p>
                  )}
                </div>
                <div className="text-sm" style={{ color: 'var(--muted)' }}>
                  {(tech.confidence * 100).toFixed(0)}% confidence
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Client Dependencies */}
      {client_dependencies && client_dependencies.length > 0 && (
        <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Client-Side Dependencies</h3>
          <div className="space-y-2">
            {client_dependencies.map((dep, idx) => (
              <div key={idx} className="p-3 rounded border" style={{ borderColor: 'var(--border)' }}>
                <p className="font-medium" style={{ color: 'var(--fg)' }}>{dep.name} {dep.version}</p>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>{dep.evidence}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Findings */}
      {findings && findings.length > 0 && (
        <div className="rounded-lg border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Vulnerabilities</h3>
          <div className="space-y-3">
            {findings.map((finding, idx) => (
              <div key={idx} className="p-4 rounded border" style={{ borderColor: 'var(--border)' }}>
                <div className="flex items-center justify-between mb-2">
                  <p className="font-medium" style={{ color: 'var(--fg)' }}>{finding.package} {finding.version}</p>
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
                <p className="text-sm mb-2" style={{ color: 'var(--muted)' }}>Evidence: {finding.evidence}</p>
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
      )}

      {(!findings || findings.length === 0) && (!client_dependencies || client_dependencies.length === 0) && (
        <div className="p-6 rounded-lg border text-center" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <p style={{ color: 'var(--muted)' }}>No vulnerabilities or dependencies detected.</p>
        </div>
      )}
    </div>
  );
}
