'use client';

import { useEffect, useState } from 'react';

type NewsItem = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string;
  summary: string;
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;
  certified: boolean;
};

type Props = {
  news: NewsItem[];
  totalCount: number;
  loading?: boolean;
};

export default function NewsStats({ news, totalCount, loading = false }: Props) {
  const [sourceCounts, setSourceCounts] = useState<Array<{ source: string; count: number }>>([]);

  // Calculate source counts when news data changes
  useEffect(() => {
    if (news.length > 0) {
      const counts = news.reduce((acc, item) => {
        const existing = acc.find(s => s.source === item.source);
        if (existing) {
          existing.count++;
        } else {
          acc.push({ source: item.source, count: 1 });
        }
        return acc;
      }, [] as Array<{ source: string; count: number }>);
      
      setSourceCounts(counts.sort((a, b) => b.count - a.count));
    }
  }, [news]);

  if (loading) {
    return (
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">-</div>
            <div className="text-sm text-[var(--muted)] font-medium">Articles Shown</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">-</div>
            <div className="text-sm text-[var(--muted)] font-medium">Total Available</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">Live</div>
            <div className="text-sm text-[var(--muted)] font-medium">Real-time Updates</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">-</div>
            <div className="text-sm text-[var(--muted)] font-medium">Sources</div>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
        <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{news.length}</div>
          <div className="text-sm text-[var(--muted)] font-medium">Articles Shown</div>
        </div>
      </div>
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{totalCount}</div>
          <div className="text-sm text-[var(--muted)] font-medium">Total Available</div>
        </div>
      </div>
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">Live</div>
          <div className="text-sm text-[var(--muted)] font-medium">Real-time Updates</div>
        </div>
      </div>
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent" />
        <div className="relative z-10">
          <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">{sourceCounts.length}</div>
          <div className="text-sm text-[var(--muted)] font-medium">Sources</div>
        </div>
      </div>
    </section>
  );
}
