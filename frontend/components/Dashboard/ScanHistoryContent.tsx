'use client';

import { useState, useEffect } from 'react';
import { User, Session } from 'next-auth';
import Link from 'next/link';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';

// Backend scan types
type ScanJobListItem = {
  id: string;
  project_id: string;
  project_name?: string | null;
  target_url?: string | null;
  scan_level: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  risk_score?: number | null;
  findings_count?: number | null;
};

type ScanJobListResponse = {
  items: ScanJobListItem[];
  total: number;
};

interface ScanHistoryContentProps {
  user: any;
  session: Session | null;
}

export default function ScanHistoryContent({ user, session }: ScanHistoryContentProps) {
  const [realSecurityScans, setRealSecurityScans] = useState<ScanJobListItem[]>([]);
  const [securityTotal, setSecurityTotal] = useState(0);
  const [isLoadingSecurity, setIsLoadingSecurity] = useState(false);
  const [errorSecurity, setErrorSecurity] = useState<string | null>(null);
  const [cancellingScans, setCancellingScans] = useState<Record<string, boolean>>({});

  // Fetch real security scans from backend
  useEffect(() => {
    async function fetchSecurityScans() {
      if (!session) return;
      
      setIsLoadingSecurity(true);
      setErrorSecurity(null);
      
      try {
        const data = await thandevFetchJSON<ScanJobListResponse>(
          '/api/scans?limit=50&offset=0',
          session
        );
        
        setRealSecurityScans(data.items);
        setSecurityTotal(data.total);
      } catch (err) {
        console.error('Error fetching security scans:', err);
        setErrorSecurity(err instanceof Error ? err.message : 'Failed to load security scans');
      } finally {
        setIsLoadingSecurity(false);
      }
    }

    fetchSecurityScans();
  }, [session]);

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'text-red-500 bg-red-500/10 border border-red-500/20';
      case 'high': return 'text-orange-500 bg-orange-500/10 border border-orange-500/20';
      case 'medium': return 'text-yellow-500 bg-yellow-500/10 border border-yellow-500/20';
      case 'low': return 'text-blue-500 bg-blue-500/10 border border-blue-500/20';
      case 'info': return 'text-gray-500 bg-gray-500/10 border border-gray-500/20';
      default: return 'text-gray-500 bg-gray-500/10 border border-gray-500/20';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed': return 'bg-green-500/10 text-green-400 border border-green-500/20';
      case 'running': return 'bg-blue-500/10 text-blue-400 border border-blue-500/20';
      case 'queued': return 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20';
      case 'failed': return 'bg-red-500/10 text-red-400 border border-red-500/20';
      case 'cancelled': return 'bg-gray-500/10 text-gray-400 border border-gray-500/20';
      default: return 'bg-gray-500/10 text-gray-400 border border-gray-500/20';
    }
  };

  const cancelScan = async (scanId: string) => {
    if (!session) {
      setErrorSecurity('Session required. Please log in again.');
      return;
    }
    
    if (!confirm('Are you sure you want to cancel this scan?')) {
      return;
    }
    
    setCancellingScans(prev => ({ ...prev, [scanId]: true }));
    setErrorSecurity(null);

    try {
      await thandevFetchJSON(
        `/api/scans/${scanId}/cancel`,
        session,
        {
          method: 'PATCH',
        }
      );
      
      // Refresh scans to get updated status
      const data = await thandevFetchJSON<ScanJobListResponse>(
        '/api/scans?limit=50&offset=0',
        session
      );
      setRealSecurityScans(data.items);
      setSecurityTotal(data.total);
    } catch (err) {
      console.error('Error cancelling scan:', err);
      const errorMessage = err instanceof Error ? err.message : 'Failed to cancel scan';
      setErrorSecurity(errorMessage);
      alert(`Failed to cancel scan: ${errorMessage}`);
    } finally {
      setCancellingScans(prev => {
        const next = { ...prev };
        delete next[scanId];
        return next;
      });
    }
  };

  // Use formatDateTime from lib/formatDate.ts for consistent timezone handling

  return (
    <div>
      {/* Error Banner */}
      {errorSecurity && (
        <div className="mb-6 p-4 rounded-lg border border-red-500/50 bg-red-500/10">
          <div className="flex items-center justify-between">
            <p className="text-sm text-red-400">{errorSecurity}</p>
            <button
              onClick={() => {
                setErrorSecurity(null);
                if (session) {
                  thandevFetchJSON<ScanJobListResponse>('/api/scans?limit=50&offset=0', session)
                    .then(data => {
                      setRealSecurityScans(data.items);
                      setSecurityTotal(data.total);
                    })
                    .catch(err => setErrorSecurity(err.message));
                }
              }}
              className="ml-4 px-3 py-1 rounded text-xs font-medium text-red-400 hover:bg-red-500/20 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Scans Table */}
      <div className="rounded-xl border overflow-hidden" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        {isLoadingSecurity ? (
          <div className="p-6">
            <div className="animate-pulse space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-16 rounded-lg" style={{ background: 'var(--surface-2)' }}></div>
              ))}
            </div>
          </div>
        ) : realSecurityScans.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
              <svg className="w-12 h-12" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>
              No security scans yet
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
              Run a security scan to see results here.
            </p>
            <Link
              href="/dashboard/scan"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ background: 'var(--brand)' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              Run Security Scan
            </Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead style={{ background: 'var(--surface-2)' }}>
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Project
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Target
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Level
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Risk Score
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Findings
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Completed
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--muted)' }}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                {realSecurityScans.map((scan) => (
                  <tr key={scan.id} className="hover:opacity-80 transition-opacity" style={{ background: 'var(--surface)' }}>
                    <td className="px-6 py-4">
                      {scan.project_id ? (
                        <Link
                          href={`/projects/${scan.project_id}`}
                          className="text-sm font-medium hover:opacity-80 transition-opacity"
                          style={{ color: 'var(--brand)' }}
                        >
                          {scan.project_name || 'Unknown Project'}
                        </Link>
                      ) : (
                        <span className="text-sm" style={{ color: 'var(--muted)' }}>–</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm font-mono" style={{ color: 'var(--fg)' }}>
                        {scan.target_url || '–'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium border" style={{ 
                        background: scan.scan_level === 'advanced' ? 'var(--purple-500/10)' : scan.scan_level === 'pro' ? 'var(--indigo-500/10)' : 'var(--blue-500/10)',
                        color: scan.scan_level === 'advanced' ? 'var(--purple-400)' : scan.scan_level === 'pro' ? 'var(--indigo-400)' : 'var(--blue-400)',
                        borderColor: scan.scan_level === 'advanced' ? 'var(--purple-500/20)' : scan.scan_level === 'pro' ? 'var(--indigo-500/20)' : 'var(--blue-500/20)'
                      }}>
                        {scan.scan_level.charAt(0).toUpperCase() + scan.scan_level.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(scan.status)}`}>
                        {scan.status.charAt(0).toUpperCase() + scan.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                        {scan.risk_score !== null && scan.risk_score !== undefined
                          ? scan.risk_score.toFixed(1)
                          : '–'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm" style={{ color: 'var(--fg)' }}>
                        {scan.findings_count !== null && scan.findings_count !== undefined
                          ? scan.findings_count
                          : '–'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="text-sm" style={{ color: 'var(--muted)' }}>
                        {formatDateTime(scan.completed_at)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      <div className="flex items-center justify-end gap-2">
                        {scan.project_id ? (
                          <Link
                            href={`/projects/${scan.project_id}/scans/${scan.id}`}
                            className="text-xs font-medium hover:opacity-80 transition-opacity"
                            style={{ color: 'var(--brand)' }}
                          >
                            View details
                          </Link>
                        ) : (
                          <span className="text-xs" style={{ color: 'var(--muted)' }}>–</span>
                        )}
                        {(scan.status === 'queued' || scan.status === 'running') && (
                          <button
                            onClick={() => cancelScan(scan.id)}
                            disabled={cancellingScans[scan.id]}
                            className="text-xs font-medium hover:opacity-80 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
                            style={{ color: 'var(--destructive)' }}
                            title="Cancel scan"
                          >
                            {cancellingScans[scan.id] ? (
                              <span className="inline-flex items-center gap-1">
                                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"></span>
                                Cancelling...
                              </span>
                            ) : (
                              'Cancel'
                            )}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}




