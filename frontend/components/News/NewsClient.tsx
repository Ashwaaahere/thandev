'use client';

import { useEffect, useState } from 'react';
import NewsList from '../../app/news/NewsList';
import RightSidebar from './RightSidebar';

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
    return (
      <div className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 text-[var(--muted)]">
        Loading news...
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-8 text-red-600 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200">
        Error loading news: {error}
      </div>
    );
  }

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      {/* left: content */}
      <div>
        <NewsList items={latest} />
      </div>

      {/* right: sidebar */}
      <RightSidebar pinned={pinned} latest={latest} />
    </div>
  );
}
