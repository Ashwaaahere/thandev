'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

interface Scan {
  id: string;
  url: string;
  timestamp: string;
  score: number;
  status: 'completed' | 'running' | 'failed';
  vulnerabilities: Array<{
    id: string;
    title: string;
    severity: 'critical' | 'high' | 'medium' | 'low';
  }>;
}

export default function RecentScans() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load recent scans from localStorage
    const scanHistory = JSON.parse(localStorage.getItem('thandev-scan-history') || '[]');
    const recentScans = scanHistory
      .sort((a: Scan, b: Scan) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 5);
    
    setScans(recentScans);
    setLoading(false);
  }, []);

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

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'running':
        return 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15';
      case 'failed':
        return 'M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z';
      default:
        return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 dark:text-green-400';
      case 'running':
        return 'text-blue-600 dark:text-blue-400';
      case 'failed':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
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
            href="/dashboard/scans"
            className="text-sm font-medium hover:opacity-80 transition-opacity"
            style={{ color: 'var(--brand)' }}
          >
            View all
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {scans.length === 0 ? (
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
              Start your first security scan to see results here.
            </p>
            <Link
              href="/dashboard/scan"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors hover:opacity-90"
              style={{ background: 'var(--brand)' }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
              </svg>
              Start Scan
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {scans.map((scan) => (
              <div key={scan.id} className="flex items-center justify-between p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-shrink-0">
                      <div className={`w-2 h-2 rounded-full ${getStatusColor(scan.status)}`}></div>
                    </div>
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--fg)' }}>
                      {scan.url}
                    </p>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(scan.vulnerabilities[0]?.severity || 'low')}`}>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getStatusIcon(scan.status)} />
                      </svg>
                      {scan.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                    <span>{new Date(scan.timestamp).toLocaleDateString()}</span>
                    <span className={`font-medium ${getScoreColor(scan.score)}`}>
                      Score: {scan.score}/100
                    </span>
                    <span>
                      {scan.vulnerabilities.length} vulnerabilities
                    </span>
                  </div>
                </div>
                <div className="flex-shrink-0 ml-4">
                  <Link
                    href={`/dashboard/scans/${scan.id}`}
                    className="text-sm font-medium hover:opacity-80 transition-opacity"
                    style={{ color: 'var(--brand)' }}
                  >
                    View Details
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}




