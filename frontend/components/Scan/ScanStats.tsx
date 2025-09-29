'use client';

import { ScanResult } from './ScanClient';

interface ScanStatsProps {
  scans: ScanResult[];
}

export default function ScanStats({ scans }: ScanStatsProps) {
  const completedScans = scans.filter(scan => scan.status === 'completed');
  const totalVulnerabilities = completedScans.reduce((sum, scan) => sum + scan.vulnerabilities.length, 0);
  const averageScore = completedScans.length > 0 
    ? Math.round(completedScans.reduce((sum, scan) => sum + scan.score, 0) / completedScans.length)
    : 0;

  const severityCounts = completedScans.reduce((counts, scan) => {
    scan.vulnerabilities.forEach(vuln => {
      counts[vuln.severity] = (counts[vuln.severity] || 0) + 1;
    });
    return counts;
  }, {} as Record<string, number>);

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 dark:text-red-400';
      case 'high': return 'text-orange-600 dark:text-orange-400';
      case 'medium': return 'text-yellow-600 dark:text-yellow-400';
      case 'low': return 'text-green-600 dark:text-green-400';
      case 'info': return 'text-blue-600 dark:text-blue-400';
      default: return 'text-[var(--muted)]';
    }
  };

  const getSeverityBgColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/10';
      case 'high': return 'bg-orange-500/10';
      case 'medium': return 'bg-yellow-500/10';
      case 'low': return 'bg-green-500/10';
      case 'info': return 'bg-blue-500/10';
      default: return 'bg-[var(--muted)]/10';
    }
  };

  if (scans.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-8 shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
        <div className="relative z-10 text-center">
          <div className="mb-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-500/20 to-blue-600/20 flex items-center justify-center">
              <div className="text-2xl">🔍</div>
            </div>
            <h3 className="text-xl font-bold text-[var(--fg)] mb-2">Ready to Scan</h3>
            <p className="text-[var(--muted)]">Start your first security scan to see statistics here</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {/* Total Scans */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-3xl font-bold text-blue-600 dark:text-blue-400 mb-2">{scans.length}</div>
          <div className="text-sm text-[var(--muted)] font-medium">Total Scans</div>
          <div className="text-xs text-[var(--muted)] mt-1">{completedScans.length} completed</div>
        </div>
      </div>

      {/* Average Score */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
        <div className="relative z-10">
          <div className={`text-3xl font-bold ${averageScore >= 80 ? 'text-green-600 dark:text-green-400' : averageScore >= 60 ? 'text-yellow-600 dark:text-yellow-400' : 'text-red-600 dark:text-red-400'}`}>
            {averageScore}
          </div>
          <div className="text-sm text-[var(--muted)] font-medium">Average Score</div>
          <div className="text-xs text-[var(--muted)] mt-1">Security rating</div>
        </div>
      </div>

      {/* Total Vulnerabilities */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-3xl font-bold text-orange-600 dark:text-orange-400 mb-2">{totalVulnerabilities}</div>
          <div className="text-sm text-[var(--muted)] font-medium">Vulnerabilities</div>
          <div className="text-xs text-[var(--muted)] mt-1">Found across all scans</div>
        </div>
      </div>

      {/* Severity Breakdown */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-sm text-[var(--muted)] font-medium mb-3">Severity Breakdown</div>
          <div className="space-y-2">
            {Object.entries(severityCounts).map(([severity, count]) => (
              <div key={severity} className="flex items-center justify-between">
                <span className={`text-xs px-2 py-1 rounded-full font-semibold ${getSeverityBgColor(severity)} ${getSeverityColor(severity)}`}>
                  {severity.toUpperCase()}
                </span>
                <span className="text-sm font-medium text-[var(--fg)]">{count}</span>
              </div>
            ))}
            {Object.keys(severityCounts).length === 0 && (
              <div className="text-sm text-[var(--muted)]">No vulnerabilities found</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
