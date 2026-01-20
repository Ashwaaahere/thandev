'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Session } from 'next-auth';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';

// Types matching backend response
type RecentScanItem = {
  id: string;
  project_id: string;
  project_name: string;
  target_url: string;
  level: string;
  status: string;
  created_at: string;
  risk_score?: number | null;
  findings_count?: number | null;
};

type DashboardMetrics = {
  // Legacy fields
  total_scans: number;
  security_scans: number;
  performance_scans: number;
  vulnerabilities_found: number;
  avg_security_score: number;
  scans_this_month: number;
  recent_scans: RecentScanItem[];
  // Phase 2 fields
  latest_scans: Array<{
    id: string;
    project_id: string;
    project_name: string;
    target_url: string;
    scan_level: string;
    status: string;
    risk_score?: number | null;
    findings_count?: number | null;
    completed_at?: string | null;
    created_at?: string | null;
  }>;
};

interface RecentScansProps {
  session: Session | null;
}

export default function RecentScans({ session }: RecentScansProps) {
  const [scans, setScans] = useState<RecentScanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadMetrics() {
      if (!session) {
        setLoading(false);
        setError('Session not available');
        return;
      }
      
      setLoading(true);
      setError(null);
      try {
        console.log('RecentScans: Fetching metrics from /api/metrics/overview');
        const data = await thandevFetchJSON<DashboardMetrics>(
          '/api/metrics/overview',
          session
        );
        
        console.log('RecentScans: Received data', {
          has_latest_scans: !!data.latest_scans,
          latest_scans_length: data.latest_scans?.length || 0,
          has_recent_scans: !!data.recent_scans,
          recent_scans_length: data.recent_scans?.length || 0,
          data_keys: Object.keys(data),
          full_data: data
        });
        
        // Log raw scan data for debugging
        if (data.latest_scans && data.latest_scans.length > 0) {
          console.log('RecentScans: Raw latest_scans[0]', JSON.stringify(data.latest_scans[0], null, 2));
        }
        if (data.recent_scans && data.recent_scans.length > 0) {
          console.log('RecentScans: Raw recent_scans[0]', JSON.stringify(data.recent_scans[0], null, 2));
        }
        
        if (!cancelled) {
          // Use latest_scans from Phase 2 metrics, fallback to recent_scans for backward compatibility
          let scansToUse: RecentScanItem[] = [];
          
          // Helper function to convert date to ISO string
          const toISOString = (date: any): string => {
            if (!date) return new Date().toISOString();
            if (typeof date === 'string') return date;
            if (date instanceof Date) return date.toISOString();
            // Handle datetime objects from API
            return new Date(date).toISOString();
          };
          
          // Try latest_scans first
          if (data.latest_scans && Array.isArray(data.latest_scans)) {
            console.log('RecentScans: latest_scans array found', {
              length: data.latest_scans.length,
              firstItem: data.latest_scans[0] || null
            });
            
            if (data.latest_scans.length > 0) {
              scansToUse = data.latest_scans
                .filter(scan => {
                  // Only require id - other fields can be optional
                  const isValid = scan && scan.id;
                  if (!isValid) {
                    console.warn('RecentScans: Filtered out invalid scan (missing id)', scan);
                  }
                  return isValid;
                })
                .map(scan => {
                  const mapped = {
                    id: String(scan.id),
                    project_id: String(scan.project_id || ''),
                    project_name: String(scan.project_name || scan.target_url || 'Unknown Project'),
                    target_url: String(scan.target_url || ''),
                    level: String(scan.scan_level || 'basic'),
                    status: String(scan.status || 'unknown'),
                    created_at: toISOString(scan.completed_at || scan.created_at),
                    risk_score: scan.risk_score ?? null,
                    findings_count: scan.findings_count ?? null,
                  };
                  console.log('RecentScans: Mapped latest_scan', mapped);
                  return mapped;
                });
              
              console.log('RecentScans: Processed latest_scans', scansToUse.length, 'valid scans');
            }
          }
          
          // Fallback to recent_scans if latest_scans is empty or not available
          if (scansToUse.length === 0 && data.recent_scans && Array.isArray(data.recent_scans)) {
            console.log('RecentScans: recent_scans array found', {
              length: data.recent_scans.length,
              firstItem: data.recent_scans[0] || null
            });
            
            if (data.recent_scans.length > 0) {
              scansToUse = data.recent_scans
                .filter(scan => {
                  // Only require id - other fields can be optional
                  const isValid = scan && scan.id;
                  if (!isValid) {
                    console.warn('RecentScans: Filtered out invalid recent_scan (missing id)', scan);
                  }
                  return isValid;
                })
                .map(scan => ({
                  id: String(scan.id),
                  project_id: String(scan.project_id || ''),
                  project_name: String(scan.project_name || scan.target_url || 'Unknown Project'),
                  target_url: String(scan.target_url || ''),
                  level: String((scan as any).level || (scan as any).scan_level || 'basic'),
                  status: String(scan.status || 'unknown'),
                  created_at: toISOString(scan.created_at || (scan as any).completed_at),
                  risk_score: scan.risk_score ?? null,
                  findings_count: scan.findings_count ?? null,
                }));
              
              console.log('RecentScans: Processed recent_scans', scansToUse.length, 'valid scans');
            }
          }
          
          console.log('RecentScans: Final result from metrics API', {
            count: scansToUse.length,
            scans: scansToUse.map(s => ({ 
              id: s.id, 
              project: s.project_name, 
              status: s.status,
              created_at: s.created_at 
            }))
          });
          
          // If no scans from metrics API, try fetching directly from scans API as fallback
          if (scansToUse.length === 0 && data.total_scans > 0) {
            console.log('RecentScans: No scans from metrics API but total_scans > 0, trying scans API fallback');
            try {
              const scansData = await thandevFetchJSON<{ items: Array<{
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
              }>; total: number }>(
                '/api/scans?limit=10',
                session
              );
              
              if (scansData.items && scansData.items.length > 0) {
                console.log('RecentScans: Got scans from fallback API', scansData.items.length);
                scansToUse = scansData.items
                  .filter(scan => scan && scan.id)
                  .map(scan => ({
                    id: String(scan.id),
                    project_id: String(scan.project_id || ''),
                    project_name: String(scan.project_name || scan.target_url || 'Unknown Project'),
                    target_url: String(scan.target_url || ''),
                    level: String(scan.scan_level || 'basic'),
                    status: String(scan.status || 'unknown'),
                    created_at: toISOString(scan.created_at || scan.completed_at),
                    risk_score: scan.risk_score ?? null,
                    findings_count: scan.findings_count ?? null,
                  }));
                console.log('RecentScans: Processed fallback scans', scansToUse.length);
              }
            } catch (fallbackError) {
              console.warn('RecentScans: Fallback API also failed', fallbackError);
              // Continue with empty array
            }
          }
          
          console.log('RecentScans: Final scansToUse after fallback', {
            count: scansToUse.length,
            scans: scansToUse.map(s => ({ 
              id: s.id, 
              project: s.project_name, 
              status: s.status
            }))
          });
          
          setScans(scansToUse);
          setLoading(false);
        }
      } catch (e) {
        console.error('RecentScans: Error loading recent scans:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load recent scans');
          setLoading(false);
        }
      }
    }

    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [session]);

  // Debug: Log render state
  useEffect(() => {
    console.log('RecentScans: Component render state', {
      loading,
      error,
      scansCount: scans.length,
      hasScans: scans.length > 0
    });
  }, [loading, error, scans.length]);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/20';
      case 'high':
        return 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-900/20';
      case 'medium':
        return 'text-yellow-600 bg-yellow-100 dark:text-yellow-400 dark:bg-yellow-900/20';
      case 'low':
        return 'text-blue-600 bg-blue-100 dark:text-blue-400 dark:bg-blue-900/20';
      default:
        return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-red-600 dark:text-red-400';
  };

  // Use formatDateTime from lib/formatDate.ts for consistent timezone handling

  // Format date like "JAN 24, 2026, 11:20 AM"
  const formatScanDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
      const month = months[date.getMonth()];
      const day = date.getDate();
      const year = date.getFullYear();
      const hours = date.getHours();
      const minutes = date.getMinutes();
      const ampm = hours >= 12 ? 'PM' : 'AM';
      const displayHours = hours % 12 || 12;
      const displayMinutes = minutes.toString().padStart(2, '0');
      return `${month} ${day}, ${year}, ${displayHours}:${displayMinutes} ${ampm}`;
    } catch {
      return formatDateTime(dateString);
    }
  };

  const getStatusInfo = (status: string, findingsCount: number) => {
    const s = status.toLowerCase();
    if (s === 'completed') {
      return {
        icon: 'M9 12l2 2 4-4',
        iconColor: 'text-green-400',
        bgColor: 'bg-green-500/20',
        badgeText: 'COMPLETED',
        badgeColor: 'bg-green-500',
        statusText: findingsCount === 0 ? '0 FINDINGS' : `${findingsCount} FINDINGS`,
        isCircular: true
      };
    } else if (s === 'running' || s === 'queued') {
      return {
        icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15',
        iconColor: 'text-blue-400',
        bgColor: 'bg-blue-500/20',
        badgeText: 'IN PROGRESS',
        badgeColor: 'bg-blue-500',
        statusText: 'RUNNING...',
        showProgress: true,
        isCircular: true
      };
    } else if (s === 'failed' || s === 'error') {
      return {
        icon: 'M12 9v2m0 4h.01',
        iconColor: 'text-red-400',
        bgColor: 'bg-red-500/20',
        badgeText: 'FAILED',
        badgeColor: 'bg-red-500',
        statusText: `${findingsCount} FINDINGS`,
        isCircular: true
      };
    } else if (s === 'cancelled' || s === 'canceled') {
      return {
        icon: 'M6 18L18 6M6 6l12 12',
        iconColor: 'text-gray-400',
        bgColor: 'bg-gray-500/20',
        badgeText: 'CANCELLED',
        badgeColor: 'bg-gray-500',
        statusText: findingsCount > 0 ? `${findingsCount} MINOR` : 'CANCELLED',
        isCircular: true
      };
    }
    return {
      icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      iconColor: 'text-gray-400',
      bgColor: 'bg-gray-500/20',
      badgeText: status.toUpperCase(),
      badgeColor: 'bg-gray-500',
      statusText: `${findingsCount} FINDINGS`
    };
  };

  if (loading) {
    return (
      <div className="rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      {/* Header */}
      <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-base font-bold text-white">
              Recent Scans
            </h2>
          </div>
          <Link 
            href="/dashboard/history"
            className="text-[10px] font-bold text-gray-400 hover:text-white transition-colors uppercase tracking-wide"
          >
            VIEW ALL
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="p-5">
        {error ? (
          <div className="text-center py-8">
            <div className="p-3 rounded-lg border border-red-500/50 bg-red-500/10 mb-4">
              <p className="text-sm text-red-400">{error}</p>
            </div>
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              Failed to load recent scans. Please try again later.
            </p>
          </div>
        ) : scans.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-700"></div>
            <h3 className="text-lg font-bold mb-2 text-white">
              No scans yet
            </h3>
            <p className="text-sm mb-4 text-gray-400">
              No scans yet — run your first scan from the Dashboard.
            </p>
            <Link
              href="/projects"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ background: 'var(--brand)' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              View Projects
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {scans.slice(0, 5).map((scan) => {
              const displayUrl = scan.target_url || scan.project_name || 'Unknown target';
              const findingsCount = scan.findings_count ?? 0;
              const statusInfo = getStatusInfo(scan.status, findingsCount);
              const scanDate = formatScanDate(scan.created_at);
              
              return (
                <div key={scan.id} className="p-3 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="flex items-start gap-3">
                    {/* Status Icon */}
                    <div className={`flex-shrink-0 w-6 h-6 rounded-full ${statusInfo.bgColor} flex items-center justify-center`}>
                      <svg className={`w-4 h-4 ${statusInfo.iconColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {statusInfo.isCircular && (
                          <circle cx="12" cy="12" r="10" strokeWidth="2" />
                        )}
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={statusInfo.icon} />
                      </svg>
                    </div>
                    
                    {/* Main Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium mb-1 text-white truncate">
                        {displayUrl}
                      </p>
                      <p className="text-[10px] text-gray-400 mb-1.5">
                        {scanDate}
                      </p>
                      
                      {/* Progress Bar for Running Scans */}
                      {statusInfo.showProgress && (
                        <div className="w-full h-1 rounded-full bg-gray-700 mb-1.5 overflow-hidden">
                          <div 
                            className="h-full bg-blue-500 rounded-full transition-all duration-300"
                            style={{ width: '75%' }}
                          />
                        </div>
                      )}
                      
                      <p className="text-[10px] text-gray-400">
                        {statusInfo.statusText}
                      </p>
                    </div>
                    
                    {/* Status Badge and External Link */}
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold text-white ${statusInfo.badgeColor}`}>
                        {statusInfo.badgeText}
                      </span>
                      {scan.status.toLowerCase() !== 'running' && scan.status.toLowerCase() !== 'queued' && (
                        <Link
                          href={`/projects/${scan.project_id}/scans/${scan.id}`}
                          className="text-gray-400 hover:text-white transition-colors"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
