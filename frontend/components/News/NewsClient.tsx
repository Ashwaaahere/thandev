'use client';

import { useEffect, useState } from 'react';
import NewsList from '../../app/news/NewsList';
import RightSidebar from './RightSidebar';
import NewsLoading from './NewsLoading';

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

export default function NewsClient() {
  const [latest, setLatest] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        setLoading(true);
        const res = await fetch('/api/news?category=cyber&limit=20');
        if (!res.ok) {
          throw new Error(`Failed to fetch news: ${res.status}`);
        }
        const data = await res.json();
        console.log('News data received:', data.items?.length || 0, 'items');
        setLatest(data.items || []);
        setError(null);
      } catch (err: any) {
        console.error('News fetch error:', err);
        setError(err.message);
        setLatest([]);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
  }, []);

  const pinned = latest.slice(0, 5);

  if (loading) {
    return <NewsLoading />;
  }

  if (error) {
    return (
      <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-8 text-red-600 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
        Error loading news: {error}
      </div>
    );
  }

  return (
    <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_380px]">
      {/* left: futuristic content grid */}
      <div className="space-y-8">
        {/* Breaking news banner */}
        <div className="relative overflow-hidden rounded-2xl border border-[var(--brand)]/20 bg-gradient-to-r from-[var(--brand)]/5 to-transparent p-6 backdrop-blur-sm">
          <div className="absolute inset-0 bg-gradient-to-r from-[var(--brand)]/10 to-transparent" />
          <div className="relative z-10 flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-sm font-semibold text-[var(--brand)]">BREAKING</span>
            <span className="text-sm text-[var(--muted)]">Real-time security updates</span>
          </div>
        </div>

        {/* Main news grid */}
        <NewsList items={latest} />
      </div>

      {/* right: futuristic sidebar */}
      <div className="space-y-6">
        <RightSidebar pinned={pinned} latest={latest} />
      </div>
    </div>
  );
}
