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
      if (!session) return;
      
      setLoading(true);
      setError(null);
      try {
        const data = await thandevFetchJSON<DashboardMetrics>(
          '/api/metrics/overview',
          session
        );
        
        if (!cancelled) {
          // Use latest_scans from Phase 2 metrics, fallback to recent_scans for backward compatibility
          const scansToUse = data.latest_scans && data.latest_scans.length > 0 
            ? data.latest_scans.map(scan => ({
                id: scan.id,
                project_id: scan.project_id,
                project_name: scan.project_name,
                target_url: scan.target_url,
                level: scan.scan_level,
                status: scan.status,
                created_at: scan.completed_at || new Date().toISOString(),
                risk_score: scan.risk_score,
                findings_count: scan.findings_count,
              }))
            : data.recent_scans;
          setScans(scansToUse);
        }
      } catch (e) {
        console.error('Error loading recent scans:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load recent scans');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [session]);

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

  const getStatusIcon = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed') {
      return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
    } else if (s === 'running' || s === 'queued') {
      return 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15';
    } else if (s === 'failed' || s === 'error') {
      return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
    }
    return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
  };

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed') {
      return 'text-green-600 dark:text-green-400';
    } else if (s === 'running' || s === 'queued') {
      return 'text-blue-600 dark:text-blue-400';
    } else if (s === 'failed' || s === 'error') {
      return 'text-red-600 dark:text-red-400';
    }
    return 'text-gray-600 dark:text-gray-400';
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
      <div className="px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
            Recent Scans
          </h2>
          <Link 
            href="/dashboard/history"
            className="text-sm font-medium hover:opacity-80 transition-opacity"
            style={{ color: 'var(--brand)' }}
          >
            View all
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {loading ? (
          <div className="animate-pulse">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
              ))}
            </div>
          </div>
        ) : error ? (
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
            <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--brand)', opacity: 0.1 }}>
              <svg className="w-8 h-8" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium mb-2" style={{ color: 'var(--fg)' }}>
              No scans yet
            </h3>
            <p className="text-sm mb-4" style={{ color: 'var(--muted)' }}>
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
          <div className="space-y-4">
            {scans.map((scan) => {
              const displayUrl = scan.target_url || scan.project_name || 'Unknown target';
              const securityScore = scan.risk_score !== null && scan.risk_score !== undefined 
                ? Math.round(100 - scan.risk_score) 
                : null;
              const findingsCount = scan.findings_count ?? 0;
              
              return (
                <div key={scan.id} className="flex items-center justify-between p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <div className="flex-shrink-0">
                        <div className={`w-2 h-2 rounded-full ${getStatusColor(scan.status)}`}></div>
                      </div>
                      <p className="text-sm font-medium truncate" style={{ color: 'var(--fg)' }}>
                        {displayUrl}
                      </p>
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium capitalize`} style={{ 
                        background: scan.status === 'completed' ? 'rgba(34, 197, 94, 0.1)' : 
                                   scan.status === 'running' || scan.status === 'queued' ? 'rgba(59, 130, 246, 0.1)' :
                                   'rgba(239, 68, 68, 0.1)',
                        color: getStatusColor(scan.status)
                      }}>
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getStatusIcon(scan.status)} />
                        </svg>
                        {scan.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                      <span>{formatDateTime(scan.created_at)}</span>
                      {securityScore !== null && (
                        <span className={`font-medium ${getScoreColor(securityScore)}`}>
                          Score: {securityScore}/100
                        </span>
                      )}
                      {findingsCount > 0 && (
                        <span>
                          {findingsCount} {findingsCount === 1 ? 'finding' : 'findings'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex-shrink-0 ml-4">
                    <Link
                      href={`/projects/${scan.project_id}/scans/${scan.id}`}
                      className="text-sm font-medium hover:opacity-80 transition-opacity"
                      style={{ color: 'var(--brand)' }}
                    >
                      View Details
                    </Link>
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
