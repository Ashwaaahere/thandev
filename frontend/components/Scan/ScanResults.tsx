'use client';

import { ScanResult } from './ScanClient';

interface ScanResultsProps {
  scan: ScanResult;
}

export default function ScanResults({ scan }: ScanResultsProps) {
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
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'scanning':
        return (
          <svg className="h-5 w-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        );
      case 'completed':
        return (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'error':
        return (
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/30';
      case 'high': return 'bg-orange-500/20 text-orange-600 dark:text-orange-400 border border-orange-500/30';
      case 'medium': return 'bg-yellow-500/20 text-yellow-600 dark:text-yellow-400 border border-yellow-500/30';
      case 'low': return 'bg-green-500/20 text-green-600 dark:text-green-400 border border-green-500/30';
      case 'info': return 'bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/30';
      default: return 'bg-[var(--muted)]/20 text-[var(--muted)] border border-[var(--muted)]/30';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600 dark:text-green-400';
    if (score >= 60) return 'text-yellow-600 dark:text-yellow-400';
    if (score >= 40) return 'text-orange-600 dark:text-orange-400';
    return 'text-red-600 dark:text-red-400';
  };

  return (
    <div className="space-y-6">
      {/* Scan Summary */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
        
        <div className="relative z-10">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-[var(--fg)]">Scan Results</h3>
            <div className={`flex items-center gap-2 ${getStatusColor(scan.status)}`}>
              {getStatusIcon(scan.status)}
              <span className="font-medium capitalize">{scan.status}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-[var(--fg)]">{scan.url}</div>
              <div className="text-sm text-[var(--muted)]">Target URL</div>
            </div>
            <div className="text-center">
              <div className={`text-2xl font-bold ${getScoreColor(scan.score)}`}>{scan.score}</div>
              <div className="text-sm text-[var(--muted)]">Security Score</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-[var(--fg)]">{scan.vulnerabilities.length}</div>
              <div className="text-sm text-[var(--muted)]">Vulnerabilities</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-[var(--fg)]">{Math.round(scan.scanTime / 1000)}s</div>
              <div className="text-sm text-[var(--muted)]">Scan Time</div>
            </div>
          </div>

          {/* Progress Bar for scanning */}
          {scan.status === 'scanning' && (
            <div className="w-full bg-[var(--surface)] rounded-full h-2 mb-4">
              <div className="bg-gradient-to-r from-blue-500 to-blue-600 h-2 rounded-full animate-pulse" style={{ width: '75%' }}></div>
            </div>
          )}
        </div>
      </div>

      {/* Vulnerabilities List */}
      {scan.status === 'completed' && scan.vulnerabilities.length > 0 && (
        <div className="space-y-4">
          <h4 className="text-lg font-semibold text-[var(--fg)]">Vulnerabilities Found</h4>
          
          {scan.vulnerabilities.map((vuln, index) => (
            <div
              key={vuln.id}
              className="relative overflow-hidden rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg hover:shadow-xl transition-shadow duration-300"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent" />
              
              <div className="relative z-10">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`text-xs px-3 py-1 rounded-full font-semibold ${getSeverityColor(vuln.severity)}`}>
                        {vuln.severity.toUpperCase()}
                      </span>
                      <span className="text-sm text-[var(--muted)]">{vuln.type}</span>
                      {vuln.cvss && (
                        <span className="text-sm text-[var(--muted)]">CVSS: {vuln.cvss}</span>
                      )}
                    </div>
                    <h5 className="text-lg font-semibold text-[var(--fg)] mb-2">{vuln.title}</h5>
                    <p className="text-[var(--muted)] mb-3">{vuln.description}</p>
                  </div>
                </div>

                <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                  <h6 className="font-medium text-blue-700 dark:text-blue-300 mb-2">Recommendation</h6>
                  <p className="text-sm text-blue-600 dark:text-blue-400">{vuln.recommendation}</p>
                </div>

                {vuln.cwe && (
                  <div className="mt-3 text-sm text-[var(--muted)]">
                    <span className="font-medium">CWE:</span> {vuln.cwe}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* No Vulnerabilities */}
      {scan.status === 'completed' && scan.vulnerabilities.length === 0 && (
        <div className="relative overflow-hidden rounded-2xl border border-green-200/50 bg-gradient-to-br from-green-50/50 to-green-100/30 p-8 backdrop-blur-sm dark:border-green-800/50 dark:from-green-950/40 dark:to-green-900/20">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
          <div className="relative z-10 text-center">
            <div className="mb-4 flex items-center justify-center gap-3">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm font-semibold text-green-600 dark:text-green-400">SECURE</span>
            </div>
            <h4 className="text-xl font-bold text-green-800 dark:text-green-200 mb-2">No Vulnerabilities Found</h4>
            <p className="text-green-600 dark:text-green-300">
              Great! No security vulnerabilities were detected in the scan. Keep up the good security practices!
            </p>
          </div>
        </div>
      )}

      {/* Error State */}
      {scan.status === 'error' && (
        <div className="relative overflow-hidden rounded-2xl border border-red-200/50 bg-gradient-to-br from-red-50/50 to-red-100/30 p-8 backdrop-blur-sm dark:border-red-800/50 dark:from-red-950/40 dark:to-red-900/20">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent" />
          <div className="relative z-10 text-center">
            <div className="mb-4 flex items-center justify-center gap-3">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm font-semibold text-red-600 dark:text-red-400">ERROR</span>
            </div>
            <h4 className="text-xl font-bold text-red-800 dark:text-red-200 mb-2">Scan Failed</h4>
            <p className="text-red-600 dark:text-red-300">
              The security scan encountered an error. Please try again or check if the URL is accessible.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
