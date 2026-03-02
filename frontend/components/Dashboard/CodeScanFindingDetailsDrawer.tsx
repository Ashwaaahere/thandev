'use client';

import { useEffect } from 'react';
import Badge from '@/components/ui/Badge';
import JsonViewerPanel from '@/components/ui/JsonViewerPanel';
import SeverityBadge from '@/components/Scans/SeverityBadge';

export type CodeFindingOut = {
  id: string;
  scan_id: string;
  source_tool: string;
  category: string;
  severity: string;
  confidence?: string | null;
  title: string;
  summary?: string | null;
  identifiers: { cve: string[]; ghsa: string[]; osv: string[]; rule_id?: string | null };
  location: {
    file_path?: string | null;
    start_line?: number | null;
    end_line?: number | null;
    start_col?: number | null;
    end_col?: number | null;
    manifest_path?: string | null;
  };
  dependency: {
    package?: string | null;
    ecosystem?: string | null;
    installed_version?: string | null;
    fixed_version?: string | null;
    dependency_chain?: string[] | null;
  };
  remediation: { recommendation?: string | null; command?: string | null };
  references: string[];
  evidence: {
    snippet?: string | null;
    snippet_start_line?: number | null;
    raw?: Record<string, unknown> | null;
  };
};

interface CodeScanFindingDetailsDrawerProps {
  finding: CodeFindingOut | null;
  open: boolean;
  onClose: () => void;
}

export default function CodeScanFindingDetailsDrawer({ finding, open, onClose }: CodeScanFindingDetailsDrawerProps) {
  useEffect(() => {
    if (open) {
      const onEscape = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
      document.addEventListener('keydown', onEscape);
      document.body.style.overflow = 'hidden';
      return () => {
        document.removeEventListener('keydown', onEscape);
        document.body.style.overflow = '';
      };
    }
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-40 transition-opacity"
        style={{ background: 'rgba(0,0,0,0.5)' }}
        aria-hidden
        onClick={onClose}
      />
      <div
        className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-lg overflow-y-auto shadow-xl"
        style={{ background: 'var(--card)', borderLeft: '1px solid var(--border)' }}
        role="dialog"
        aria-modal
        aria-labelledby="drawer-title"
      >
        <div className="sticky top-0 flex items-center justify-between border-b px-4 py-3" style={{ background: 'var(--card)', borderColor: 'var(--border)' }}>
          <h2 id="drawer-title" className="text-lg font-semibold truncate pr-4" style={{ color: 'var(--text)' }}>
            Finding details
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg transition-colors hover:opacity-80"
            style={{ color: 'var(--muted)' }}
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-4 space-y-5">
          {!finding ? (
            <p className="text-sm" style={{ color: 'var(--muted)' }}>No finding selected.</p>
          ) : (
            <>
              {/* A) Header: Title + badges */}
              <div>
                <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text)' }}>{finding.title}</h3>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="neutral" size="sm">{finding.source_tool}</Badge>
                  <Badge variant="neutral" size="sm">{finding.category}</Badge>
                  <SeverityBadge severity={finding.severity} size="sm" />
                  {finding.confidence && (
                    <Badge variant="neutral" size="sm">{finding.confidence}</Badge>
                  )}
                </div>
              </div>

              {/* B) Where found */}
              <section>
                <h4 className="text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Where found</h4>
                <div className="rounded-lg border px-3 py-2 text-sm font-mono" style={{ borderColor: 'var(--border)', color: 'var(--text)' }}>
                  {finding.location.file_path && (
                    <div className="truncate" title={finding.location.file_path}>{finding.location.file_path}</div>
                  )}
                  {finding.location.manifest_path && !finding.location.file_path && (
                    <div className="truncate" title={finding.location.manifest_path}>{finding.location.manifest_path}</div>
                  )}
                  {(!finding.location.file_path && !finding.location.manifest_path) && (
                    <span style={{ color: 'var(--muted)' }}>—</span>
                  )}
                  {(finding.location.start_line != null || finding.location.end_line != null) && (
                    <div className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
                      Line {finding.location.start_line ?? '?'}
                      {finding.location.end_line != null && finding.location.end_line !== finding.location.start_line && ` – ${finding.location.end_line}`}
                      {finding.location.start_col != null && `, col ${finding.location.start_col}`}
                    </div>
                  )}
                </div>
              </section>

              {/* C) Evidence: snippet (code block or redacted) */}
              <section>
                <h4 className="text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Evidence</h4>
                {finding.evidence?.snippet != null ? (
                  <div className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border)' }}>
                    <pre className="p-3 text-xs font-mono whitespace-pre-wrap break-words overflow-x-auto" style={{ color: 'var(--text)', background: 'var(--card-2)' }}>
                      {finding.evidence.snippet}
                    </pre>
                    {finding.evidence.snippet_start_line != null && (
                      <div className="px-3 py-1 text-[10px]" style={{ color: 'var(--muted)', borderTop: '1px solid var(--border)' }}>
                        Line {finding.evidence.snippet_start_line}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>No snippet (redacted or not available).</p>
                )}
              </section>

              {/* D) Impact / Summary */}
              {finding.summary && (
                <section>
                  <h4 className="text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Summary</h4>
                  <p className="text-sm" style={{ color: 'var(--text)' }}>{finding.summary}</p>
                </section>
              )}

              {/* E) Dependency */}
              {(finding.dependency?.package || finding.dependency?.installed_version || finding.dependency?.fixed_version) && (
                <section>
                  <h4 className="text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Dependency</h4>
                  <div className="rounded-lg border px-3 py-2 text-sm space-y-1" style={{ borderColor: 'var(--border)', color: 'var(--text)' }}>
                    {finding.dependency.package && <div><span style={{ color: 'var(--muted)' }}>Package:</span> {finding.dependency.package}</div>}
                    {finding.dependency.installed_version && <div><span style={{ color: 'var(--muted)' }}>Installed:</span> {finding.dependency.installed_version}</div>}
                    {finding.dependency.fixed_version && <div><span style={{ color: 'var(--muted)' }}>Fixed:</span> {finding.dependency.fixed_version}</div>}
                    {finding.dependency.dependency_chain && finding.dependency.dependency_chain.length > 0 && (
                      <div><span style={{ color: 'var(--muted)' }}>Chain:</span> {finding.dependency.dependency_chain.join(' → ')}</div>
                    )}
                  </div>
                </section>
              )}

              {/* F) Remediation */}
              {(finding.remediation?.recommendation || finding.remediation?.command) && (
                <section>
                  <h4 className="text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Remediation</h4>
                  <div className="rounded-lg border px-3 py-2 text-sm space-y-1" style={{ borderColor: 'var(--border)', color: 'var(--text)' }}>
                    {finding.remediation.recommendation && <p>{finding.remediation.recommendation}</p>}
                    {finding.remediation.command && (
                      <pre className="font-mono text-xs mt-1 p-2 rounded" style={{ background: 'var(--card-2)' }}>{finding.remediation.command}</pre>
                    )}
                  </div>
                </section>
              )}

              {/* G) Identifiers + References */}
              <section>
                <h4 className="text-xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: 'var(--muted)' }}>Identifiers & references</h4>
                <div className="flex flex-wrap gap-2 mb-2">
                  {finding.identifiers.rule_id && <Badge variant="neutral" size="sm">{finding.identifiers.rule_id}</Badge>}
                  {[...(finding.identifiers.cve || []), ...(finding.identifiers.ghsa || []), ...(finding.identifiers.osv || [])].map((id) => (
                    <a
                      key={id}
                      href={id.startsWith('CVE-') ? `https://nvd.nist.gov/vuln/detail/${id}` : id.includes('GHSA') ? `https://github.com/advisories/${id}` : `https://osv.dev/vulnerability/${id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-mono px-2 py-0.5 rounded border transition-colors hover:opacity-90"
                      style={{ borderColor: 'var(--border)', color: 'var(--brand)' }}
                    >
                      {id}
                    </a>
                  ))}
                </div>
                {finding.references && finding.references.length > 0 && (
                  <ul className="list-disc list-inside text-sm space-y-0.5" style={{ color: 'var(--text)' }}>
                    {finding.references.slice(0, 10).map((url, i) => (
                      <li key={i}>
                        <a href={url} target="_blank" rel="noreferrer" className="underline break-all" style={{ color: 'var(--brand)' }}>{url}</a>
                      </li>
                    ))}
                    {finding.references.length > 10 && <li style={{ color: 'var(--muted)' }}>+{finding.references.length - 10} more</li>}
                  </ul>
                )}
              </section>

              {/* H) Raw evidence (collapsible) */}
              {finding.evidence?.raw != null && (
                <JsonViewerPanel data={finding.evidence.raw} title="Raw evidence" defaultOpen={false} maxHeight="300px" />
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
