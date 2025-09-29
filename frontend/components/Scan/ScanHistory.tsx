'use client';

import { ScanResult } from './ScanClient';

interface ScanHistoryProps {
  scans: ScanResult[];
  onClear: () => void;
}

export default function ScanHistory({ scans, onClear }: ScanHistoryProps) {
  const getStatusColor = (status: ScanResult['status']) => {
    switch (status) {
      case 'pending': return 'text-yellow-600 dark:text-yellow-400';
      case 'scanning': return 'text-blue-600 dark:text-blue-400';
      case 'completed': return 'text-green-600 dark:text-green-400';
      case 'error': return 'text-red-600 dark:text-red-400';
      default: return 'text-[var(--muted)]';
    }
  };

  const getStatusIcon = (status: ScanResult['status']) => {
    switch (status) {
      case 'pending':
        return (
          <div className="h-2 w-2 rounded-full bg-yellow-500"></div>
        );
      case 'scanning':
        return (
          <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse"></div>
        );
      case 'completed':
        return (
          <div className="h-2 w-2 rounded-full bg-green-500"></div>
        );
      case 'error':
        return (
          <div className="h-2 w-2 rounded-full bg-red-500"></div>
        );
    }
  };

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
    if (score >= 40) return 'text-orange-600 dark:text-orange-400';
    return 'text-red-600 dark:text-red-400';
  };

  if (scans.length === 0) {
    return null;
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
      <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent" />
      
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-[var(--fg)]">Scan History</h3>
          <button
            onClick={onClear}
            className="text-sm text-[var(--muted)] hover:text-[var(--fg)] transition-colors duration-200"
          >
            Clear History
          </button>
        </div>

        <div className="space-y-3">
          {scans.slice(0, 10).map((scan) => (
            <div
              key={scan.id}
              className="flex items-center justify-between p-4 rounded-lg border border-[var(--border)]/30 bg-[var(--surface)]/50 hover:bg-[var(--surface)]/80 transition-colors duration-200"
            >
              <div className="flex items-center gap-4 flex-1">
                <div className="flex items-center gap-2">
                  {getStatusIcon(scan.status)}
                  <span className={`text-sm font-medium capitalize ${getStatusColor(scan.status)}`}>
                    {scan.status}
                  </span>
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[var(--fg)] truncate">
                    {scan.url}
                  </div>
                  <div className="text-xs text-[var(--muted)]">
                    {formatDate(scan.timestamp)}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm">
                {scan.status === 'completed' && (
                  <>
                    <div className="text-center">
                      <div className={`font-semibold ${getScoreColor(scan.score)}`}>
                        {scan.score}
                      </div>
                      <div className="text-xs text-[var(--muted)]">Score</div>
                    </div>
                    <div className="text-center">
                      <div className="font-semibold text-[var(--fg)]">
                        {scan.vulnerabilities.length}
                      </div>
                      <div className="text-xs text-[var(--muted)]">Vulns</div>
                    </div>
                    <div className="text-center">
                      <div className="font-semibold text-[var(--fg)]">
                        {Math.round(scan.scanTime / 1000)}s
                      </div>
                      <div className="text-xs text-[var(--muted)]">Time</div>
                    </div>
                  </>
                )}
                
                {scan.status === 'scanning' && (
                  <div className="flex items-center gap-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
                    <span className="text-sm text-[var(--muted)]">Scanning...</span>
                  </div>
                )}
                
                {scan.status === 'pending' && (
                  <span className="text-sm text-[var(--muted)]">Queued</span>
                )}
                
                {scan.status === 'error' && (
                  <span className="text-sm text-red-600 dark:text-red-400">Failed</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {scans.length > 10 && (
          <div className="mt-4 text-center">
            <span className="text-sm text-[var(--muted)]">
              Showing latest 10 scans of {scans.length} total
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

