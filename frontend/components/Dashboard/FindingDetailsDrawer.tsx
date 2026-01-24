'use client';

import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { thandevFetchJSON } from '@/lib/thandevApi';
import CWEDrawer from './CWEDrawer';

type FindingStatus = "open" | "acknowledged" | "resolved" | "suppressed";

type FindingListItem = {
  id: string;
  scan_id: string;
  project_id: string;
  project_name: string;
  target_url: string;
  severity: string;
  status: FindingStatus;
  title: string;
  description?: string | null;
  cve_id?: string | null;
  cwe_id?: string | null;
  cvss_score?: number | null;
  // ZAP-specific metadata
  wasc_id?: number | null;
  plugin_id?: string | null;
  alert_ref?: string | null;
  zap_confidence?: number | null;
  zap_riskcode?: number | null;
  tool?: string | null;
  categories?: string[] | null;
  vuln_type?: string | null;
  http_method?: string | null;
  parameter?: string | null;
  url?: string | null;
  path?: string | null;
  evidence?: string | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  not_seen_in_latest_scan?: boolean | null;
  found_count?: number | null;
  remediation_summary?: string | null;
  remediation_steps?: string | null;
  impact_summary?: string | null;
  raw_data_preview?: Record<string, any> | null;
};

type FindingDetailResponse = FindingListItem & {
  raw_data?: Record<string, any> | null;
};

interface FindingDetailsDrawerProps {
  finding: FindingListItem | null;
  open: boolean;
  onClose: () => void;
  onStatusUpdate?: (findingId: string, newStatus: FindingStatus) => void;
}

function SeverityBadge({ severity }: { severity: string }) {
  const normalized = severity.toLowerCase();
  const base = 'px-2 py-1 rounded text-xs font-semibold';
  
  switch (normalized) {
    case 'critical':
      return <span className={`${base} bg-red-500/20 text-red-400 border border-red-500/40`}>Critical</span>;
    case 'high':
      return <span className={`${base} bg-orange-500/20 text-orange-400 border border-orange-500/40`}>High</span>;
    case 'medium':
      return <span className={`${base} bg-yellow-500/20 text-yellow-400 border border-yellow-500/40`}>Medium</span>;
    case 'low':
      return <span className={`${base} bg-blue-500/20 text-blue-400 border border-blue-500/40`}>Low</span>;
    case 'info':
      return <span className={`${base} bg-gray-500/20 text-gray-400 border border-gray-500/40`}>Info</span>;
    default:
      return <span className={`${base} bg-gray-500/20 text-gray-400 border border-gray-500/40`}>{severity}</span>;
  }
}

function StatusBadge({ status }: { status: FindingStatus | string | null | undefined }) {
  if (!status) return null;
  const normalized = (status as string).toLowerCase() as FindingStatus;
  const base = 'px-2 py-0.5 rounded-full text-xs font-medium border';
  
  switch (normalized) {
    case 'open':
      return <span className={`${base} border-rose-500/60 bg-rose-900/30 text-rose-100`}>Open</span>;
    case 'acknowledged':
      return <span className={`${base} border-amber-500/60 bg-amber-900/30 text-amber-100`}>Acknowledged</span>;
    case 'resolved':
      return <span className={`${base} border-emerald-500/60 bg-emerald-900/30 text-emerald-100`}>Resolved</span>;
    case 'suppressed':
      return <span className={`${base} border-slate-500/60 bg-slate-900/60 text-slate-200`}>Suppressed</span>;
    default:
      return null;
  }
}

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateString;
  }
}

// Helper function to format finding title
function formatFindingTitle(title: string | null | undefined): string {
  if (!title) return 'Untitled finding';
  
  // Remove "Top X Parameters" prefix if present
  const topParamsMatch = title.match(/^Top \d+ Parameters\s*-\s*(.+)$/i);
  if (topParamsMatch) {
    return topParamsMatch[1].trim();
  }
  
  return title;
}

// Helper function to format URL for display
function formatUrlForDisplay(url: string | null | undefined, maxLength: number = 120): string {
  if (!url) return '';
  
  try {
    const urlObj = new URL(url);
    const baseUrl = `${urlObj.protocol}//${urlObj.host}${urlObj.pathname}`;
    const params = urlObj.searchParams;
    const paramCount = params.toString().split('&').filter(p => p).length;
    
    // If URL is short enough, show it fully
    if (url.length <= maxLength) {
      return url;
    }
    
    // If base URL is already long, truncate it
    if (baseUrl.length > maxLength - 20) {
      return `${baseUrl.substring(0, maxLength - 20)}...${paramCount > 0 ? ` (+${paramCount} params)` : ''}`;
    }
    
    // Show base URL + parameter count
    return `${baseUrl}${paramCount > 0 ? ` (+${paramCount} parameter${paramCount > 1 ? 's' : ''})` : ''}`;
  } catch {
    // If URL parsing fails, just truncate
    return url.length > maxLength ? `${url.substring(0, maxLength)}...` : url;
  }
}

// Helper function to get full URL with expandable parameters
function getUrlDisplay(url: string | null | undefined): { base: string; paramCount: number; full: string } {
  if (!url) return { base: '', paramCount: 0, full: '' };
  
  try {
    const urlObj = new URL(url);
    const baseUrl = `${urlObj.protocol}//${urlObj.host}${urlObj.pathname}`;
    const params = urlObj.searchParams;
    const paramCount = params.toString().split('&').filter(p => p).length;
    
    return {
      base: baseUrl,
      paramCount,
      full: url
    };
  } catch {
    return { base: url, paramCount: 0, full: url };
  }
}

function getImpactSummary(vulnType: string | null | undefined, impactSummary: string | null | undefined): string | null {
  // Use backend-provided impact_summary if available
  if (impactSummary) return impactSummary;
  
  // Fallback: derive from vuln_type
  if (!vulnType) return null;
  
  const vulnTypeLower = vulnType.toLowerCase();
  const impactMap: Record<string, string> = {
    'xss': "An attacker can execute JavaScript in the user's browser, potentially stealing session cookies, redirecting users, or performing actions on their behalf.",
    'sqli': "An attacker can read or modify database data, potentially accessing sensitive information like user credentials or personal data.",
    'ssrf': "An attacker can make requests to internal services or external servers, potentially accessing internal resources or performing port scans.",
    'ssti': "An attacker can execute code on the server by injecting template syntax, potentially gaining full server control.",
    'xxe': "An attacker can read files from the server or perform server-side request forgery attacks.",
    'dir_traversal': "An attacker can read arbitrary files from the server filesystem, potentially accessing configuration files or sensitive data.",
    'csrf': "An attacker can trick authenticated users into performing unintended actions on the application.",
    'cors': "An attacker can make requests from a malicious website that appear to come from your domain, potentially accessing user data.",
    'command_injection': "An attacker can execute arbitrary commands on the server, potentially gaining full system control.",
    'idor': "An attacker can access resources belonging to other users by manipulating object identifiers.",
    'open_port': "Exposed services can be attacked or misconfigured, potentially allowing unauthorized access.",
    'weak_ssl': "Encrypted connections may be vulnerable to interception or downgrade attacks.",
  };
  
  return impactMap[vulnTypeLower] || null;
}

export default function FindingDetailsDrawer({ finding, open, onClose, onStatusUpdate }: FindingDetailsDrawerProps) {
  const { data: session } = useSession();
  const [fullFinding, setFullFinding] = useState<FindingDetailResponse | null>(null);
  const [loadingFull, setLoadingFull] = useState(false);
  const [showRawData, setShowRawData] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [cweDrawerOpen, setCweDrawerOpen] = useState(false);
  const [selectedCweId, setSelectedCweId] = useState<string | null>(null);

  // Load full finding data when drawer opens
  useEffect(() => {
    if (open && finding && session) {
      setLoadingFull(true);
      thandevFetchJSON<FindingDetailResponse>(`/api/findings/${finding.id}`, session)
        .then(data => {
          setFullFinding(data);
        })
        .catch(err => {
          console.error('Failed to load full finding details', err);
          // Fallback to the finding from list
          setFullFinding(finding as FindingDetailResponse);
        })
        .finally(() => {
          setLoadingFull(false);
        });
    } else if (!open) {
      setFullFinding(null);
      setShowRawData(false);
      setCweDrawerOpen(false);
      setSelectedCweId(null);
    }
  }, [open, finding, session]);

  // Handle Esc key to close
  useEffect(() => {
    if (!open) return;
    
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [open, onClose]);

  const displayFinding = fullFinding || finding;
  if (!displayFinding) return null;

  const handleStatusUpdate = async (newStatus: FindingStatus) => {
    if (!displayFinding || !session) return;
    
    setUpdatingStatus(true);
    try {
      await thandevFetchJSON(`/api/findings/${displayFinding.id}/status`, session, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      });
      
      if (onStatusUpdate) {
        onStatusUpdate(displayFinding.id, newStatus);
      }
      
      // Update local state
      if (fullFinding) {
        setFullFinding({ ...fullFinding, status: newStatus });
      }
    } catch (err) {
      console.error('Failed to update status', err);
    } finally {
      setUpdatingStatus(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-40 transition-opacity"
          onClick={onClose}
        />
      )}
      
      {/* Drawer */}
      <div
        className={`fixed top-0 right-0 h-full w-full max-w-2xl z-50 transform transition-transform duration-300 ease-in-out ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ background: 'var(--bg)' }}
      >
        <div className="h-full flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--border)' }}>
            <div className="flex items-center gap-3">
              <SeverityBadge severity={displayFinding.severity} />
              {displayFinding.vuln_type && (
                <span className="px-2 py-1 rounded text-xs font-medium uppercase" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                  {displayFinding.vuln_type}
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-opacity-20 transition-colors"
              style={{ background: 'var(--surface-2)' }}
              aria-label="Close"
            >
              <svg className="w-5 h-5" style={{ color: 'var(--fg)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6" style={{ position: 'relative', zIndex: 1 }}>
            {loadingFull ? (
              <div className="text-center py-8" style={{ color: 'var(--muted)' }}>
                Loading details...
              </div>
            ) : (
              <>
                {/* Title */}
                <div>
                  <h2 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>
                    {formatFindingTitle(displayFinding.title)}
                  </h2>
                  
                  {/* Location */}
                  {(displayFinding.http_method || displayFinding.url || displayFinding.parameter) && (
                    <div className="mt-2 space-y-1 text-sm" style={{ color: 'var(--muted)' }}>
                      {displayFinding.http_method && displayFinding.url && (
                        <div className="break-all">
                          <span className="font-medium" style={{ color: 'var(--fg)' }}>{displayFinding.http_method}</span>{' '}
                          <span className="font-mono text-xs">{formatUrlForDisplay(displayFinding.url, 150)}</span>
                          {(() => {
                            const urlInfo = getUrlDisplay(displayFinding.url);
                            if (urlInfo.paramCount > 0 && displayFinding.url && displayFinding.url.length > 150) {
                              return (
                                <details className="mt-1">
                                  <summary className="text-xs cursor-pointer" style={{ color: 'var(--brand)' }}>
                                    Show full URL
                                  </summary>
                                  <div className="mt-1 p-2 rounded text-xs font-mono break-all" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                                    {displayFinding.url}
                                  </div>
                                </details>
                              );
                            }
                            return null;
                          })()}
                        </div>
                      )}
                      {displayFinding.parameter && (
                        <div>
                          Parameter: <span className="font-mono font-medium" style={{ color: 'var(--fg)' }}>{displayFinding.parameter}</span>
                          {(() => {
                            const urlInfo = getUrlDisplay(displayFinding.url);
                            if (urlInfo.paramCount > 1) {
                              return (
                                <span className="ml-2 text-xs" style={{ color: 'var(--muted)' }}>
                                  ({urlInfo.paramCount} total parameters)
                                </span>
                              );
                            }
                            return null;
                          })()}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Status and lifecycle */}
                  <div className="flex items-center gap-3 mt-3 flex-wrap">
                    <StatusBadge status={displayFinding.status} />
                    {displayFinding.not_seen_in_latest_scan !== null && (
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        displayFinding.not_seen_in_latest_scan 
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                          : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                      }`}>
                        {displayFinding.not_seen_in_latest_scan ? 'Not seen in latest scan' : 'Present in latest scan'}
                      </span>
                    )}
                  </div>
                </div>

                {/* What was found */}
                {displayFinding.description && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>What we found</h3>
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                      {displayFinding.description}
                    </p>
                  </div>
                )}

                {/* Why it matters */}
                {getImpactSummary(displayFinding.vuln_type, displayFinding.impact_summary) && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Why it matters</h3>
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                      {getImpactSummary(displayFinding.vuln_type, displayFinding.impact_summary)}
                    </p>
                  </div>
                )}

                {/* Evidence */}
                {(displayFinding.evidence || displayFinding.raw_data_preview) && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Evidence</h3>
                    {displayFinding.evidence && (
                      <p className="text-sm mb-3 font-mono p-3 rounded" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                        {displayFinding.evidence}
                      </p>
                    )}
                    {displayFinding.raw_data_preview && Object.keys(displayFinding.raw_data_preview).length > 0 && (
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs border-collapse">
                          <tbody>
                            {Object.entries(displayFinding.raw_data_preview).map(([key, value]) => (
                              <tr key={key} className="border-b" style={{ borderColor: 'var(--border)' }}>
                                <td className="py-2 px-3 font-medium" style={{ color: 'var(--fg)' }}>{key}</td>
                                <td className="py-2 px-3 font-mono" style={{ color: 'var(--muted)' }}>
                                  {typeof value === 'string' ? value : JSON.stringify(value)}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* How to fix */}
                {(displayFinding.remediation_summary || displayFinding.remediation_steps) && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>How to fix</h3>
                    {displayFinding.remediation_summary && (
                      <p className="text-sm mb-2" style={{ color: 'var(--muted)' }}>
                        {displayFinding.remediation_summary}
                      </p>
                    )}
                    {displayFinding.remediation_steps && (
                      <ul className="text-sm list-disc list-inside space-y-1" style={{ color: 'var(--muted)' }}>
                        {displayFinding.remediation_steps.split('\n').filter(s => s.trim()).map((step, idx) => (
                          <li key={idx}>{step.trim()}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}

                {/* Lifecycle info */}
                {(displayFinding.first_seen_at || displayFinding.last_seen_at || displayFinding.found_count) && (
                  <div>
                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Lifecycle</h3>
                    <div className="text-sm space-y-1" style={{ color: 'var(--muted)' }}>
                      {displayFinding.first_seen_at && (
                        <div>First seen: {formatDate(displayFinding.first_seen_at)}</div>
                      )}
                      {displayFinding.last_seen_at && (
                        <div>Last seen: {formatDate(displayFinding.last_seen_at)}</div>
                      )}
                      {displayFinding.found_count !== null && displayFinding.found_count !== undefined && (
                        <div>Seen in {displayFinding.found_count} scan{displayFinding.found_count !== 1 ? 's' : ''}</div>
                      )}
                    </div>
                  </div>
                )}

                {/* CVE/CWE/References */}
                {(displayFinding.cve_id || displayFinding.cwe_id || displayFinding.wasc_id || displayFinding.plugin_id || displayFinding.alert_ref) && (
                  <div style={{ position: 'relative', zIndex: 1 }}>
                    <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>References</h3>
                    <div className="flex flex-wrap gap-2" style={{ position: 'relative', zIndex: 1 }}>
                      {displayFinding.cve_id && (
                        <a
                          href={`https://nvd.nist.gov/vuln/detail/${displayFinding.cve_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-2 py-1 rounded text-xs font-semibold border transition-colors"
                          style={{ 
                            borderColor: 'var(--border)', 
                            color: 'var(--fg)',
                            background: 'var(--surface-2)',
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'var(--surface-3)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'var(--surface-2)';
                          }}
                        >
                          {displayFinding.cve_id}
                        </a>
                      )}
                      {displayFinding.cwe_id && (() => {
                        const cweIdValue = displayFinding.cwe_id.replace(/^CWE-/i, '');
                        const cweId = displayFinding.cwe_id;
                        return (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              setSelectedCweId(cweId);
                              setCweDrawerOpen(true);
                            }}
                            className="px-2 py-1 rounded text-xs font-semibold border transition-colors cursor-pointer"
                            style={{ 
                              borderColor: 'var(--brand)', 
                              color: 'var(--brand)',
                              background: 'var(--surface-2)',
                              zIndex: 9999,
                              position: 'relative',
                              pointerEvents: 'auto',
                              cursor: 'pointer',
                              userSelect: 'none',
                              touchAction: 'manipulation',
                            }}
                            onMouseEnter={(e) => {
                              e.currentTarget.style.background = 'var(--surface-3)';
                              e.currentTarget.style.borderColor = 'var(--brand-hover)';
                              e.currentTarget.style.opacity = '0.9';
                            }}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = 'var(--surface-2)';
                              e.currentTarget.style.borderColor = 'var(--brand)';
                              e.currentTarget.style.opacity = '1';
                            }}
                            aria-label={`View CWE-${cweIdValue} details`}
                            tabIndex={0}
                            data-testid="cwe-badge-button"
                          >
                            CWE-{cweIdValue}
                          </button>
                        );
                      })()}
                      {displayFinding.wasc_id && (
                        <span className="px-2 py-1 rounded text-xs font-semibold border" style={{ borderColor: 'var(--border)', color: 'var(--muted)', background: 'var(--surface-2)' }}>
                          WASC-{displayFinding.wasc_id}
                        </span>
                      )}
                      {displayFinding.plugin_id && (
                        <span className="px-2 py-1 rounded text-xs font-mono border" style={{ borderColor: 'var(--border)', color: 'var(--muted)', background: 'var(--surface-2)' }}>
                          Plugin: {displayFinding.plugin_id}
                        </span>
                      )}
                      {displayFinding.alert_ref && (
                        <span className="px-2 py-1 rounded text-xs font-mono border" style={{ borderColor: 'var(--border)', color: 'var(--muted)', background: 'var(--surface-2)' }}>
                          Alert: {displayFinding.alert_ref}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Technical details (advanced) */}
                <details className="mt-4">
                  <summary className="text-sm cursor-pointer font-medium mb-2" style={{ color: 'var(--brand)' }}>
                    Technical details
                  </summary>
                  <div className="mt-2 space-y-3">
                    {displayFinding.tool && (
                      <div>
                        <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Detected by: </span>
                        <span className="text-xs font-mono" style={{ color: 'var(--fg)' }}>{displayFinding.tool}</span>
                      </div>
                    )}
                    
                    {/* ZAP-specific metadata */}
                    {(displayFinding.zap_confidence !== null && displayFinding.zap_confidence !== undefined) && (
                      <div>
                        <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>Confidence: </span>
                        <span className="text-xs font-mono" style={{ color: 'var(--fg)' }}>
                          {displayFinding.zap_confidence === 0 ? 'Low' :
                           displayFinding.zap_confidence === 1 ? 'Medium' :
                           displayFinding.zap_confidence === 2 ? 'High' :
                           displayFinding.zap_confidence === 3 ? 'Confirmed' :
                           `Unknown (${displayFinding.zap_confidence})`}
                        </span>
                      </div>
                    )}
                    
                    {/* ZAP riskcode (optional, can be hidden behind debug toggle) */}
                    {displayFinding.zap_riskcode !== null && displayFinding.zap_riskcode !== undefined && (
                      <div>
                        <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>ZAP Riskcode: </span>
                        <span className="text-xs font-mono" style={{ color: 'var(--fg)' }}>
                          {displayFinding.zap_riskcode} ({displayFinding.zap_riskcode === 0 ? 'Info' :
                           displayFinding.zap_riskcode === 1 ? 'Low' :
                           displayFinding.zap_riskcode === 2 ? 'Medium' :
                           displayFinding.zap_riskcode === 3 ? 'High' :
                           displayFinding.zap_riskcode === 4 ? 'Critical' :
                           'Unknown'})
                        </span>
                      </div>
                    )}
                    
                    {fullFinding?.raw_data && (
                      <div>
                        <button
                          onClick={() => setShowRawData(!showRawData)}
                          className="text-xs font-medium mb-2" style={{ color: 'var(--brand)' }}
                        >
                          {showRawData ? 'Hide' : 'Show'} raw JSON
                        </button>
                        {showRawData && (
                          <pre className="text-xs p-3 rounded overflow-x-auto" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                            {JSON.stringify(fullFinding.raw_data, null, 2)}
                          </pre>
                        )}
                      </div>
                    )}
                  </div>
                </details>
              </>
            )}
          </div>

          {/* Footer with status update */}
          <div className="p-6 border-t flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
            <div className="text-xs" style={{ color: 'var(--muted)' }}>
              Project: {displayFinding.project_name}
            </div>
            <select
              value={displayFinding.status}
              onChange={(e) => handleStatusUpdate(e.target.value as FindingStatus)}
              disabled={updatingStatus}
              className="text-sm rounded border px-3 py-1.5"
              style={{
                background: 'var(--surface-2)',
                borderColor: 'var(--border)',
                color: 'var(--fg)'
              }}
            >
              <option value="open">Open</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="resolved">Resolved</option>
              <option value="suppressed">Suppressed</option>
            </select>
          </div>
        </div>
      </div>

      {/* CWE Drawer */}
      {selectedCweId && (
        <CWEDrawer
          cweId={selectedCweId}
          open={cweDrawerOpen}
          onClose={() => {
            setCweDrawerOpen(false);
            setSelectedCweId(null);
          }}
        />
      )}
    </>
  );
}

