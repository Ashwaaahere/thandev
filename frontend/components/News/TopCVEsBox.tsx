'use client';

import Link from 'next/link';

type Props = {
  cveCounts: Map<string, number>;
  loading?: boolean;
};

export default function TopCVEsBox({ cveCounts, loading = false }: Props) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-5 shadow-lg">
        <h3 className="text-lg font-bold text-[var(--fg)] mb-4">Top CVEs in your environment</h3>
        <div className="space-y-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-8 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (cveCounts.size === 0) {
    return null; // Don't show if no CVEs
  }

  // Sort CVEs by count (descending) and take top 10
  const sortedCVEs = Array.from(cveCounts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10);

  return (
    <div className="rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-5 shadow-lg">
      <h3 className="text-lg font-bold text-[var(--fg)] mb-4">Top CVEs in your environment</h3>
      <div className="space-y-2">
        {sortedCVEs.map(([cve, count]) => (
          <Link
            key={cve}
            href={`/dashboard/vulnerabilities?search=${encodeURIComponent(cve)}`}
            className="flex items-center justify-between p-2 rounded-lg hover:bg-[var(--brand)]/10 transition-colors group"
          >
            <span className="text-sm font-mono font-semibold text-[var(--fg)] group-hover:text-[var(--brand)] transition-colors">
              {cve}
            </span>
            <span className="text-xs text-[var(--muted)] bg-[var(--brand)]/10 px-2 py-0.5 rounded-full">
              {count} {count === 1 ? 'finding' : 'findings'}
            </span>
          </Link>
        ))}
      </div>
      {sortedCVEs.length > 0 && (
        <Link
          href="/dashboard/vulnerabilities"
          className="mt-4 block text-center text-sm text-[var(--brand)] hover:text-[var(--brand)]/80 font-semibold transition-colors"
        >
          View all vulnerabilities →
        </Link>
      )}
    </div>
  );
}
