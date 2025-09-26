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
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  useEffect(() => {
    const fetchNews = async () => {
      try {
        setLoading(true);
        const res = await fetch('/api/news?category=cyber&limit=100');
        if (!res.ok) {
          throw new Error(`Failed to fetch news: ${res.status}`);
        }
        const data = await res.json();
        console.log('News data received:', data.items?.length || 0, 'items');
        const allItems = data.items || [];
        setTotalCount(allItems.length);
        setLatest(allItems.slice(0, 31)); // Show first 31 articles
        setHasMore(allItems.length > 31);
        setError(null);
      } catch (err: any) {
        console.error('News fetch error:', err);
        setError(err.message);
        setLatest([]);
        setTotalCount(0);
      } finally {
        setLoading(false);
      }
    };

    fetchNews();
  }, []);

  const pinned = latest.slice(0, 5);

  const loadMore = async () => {
    if (loadingMore || !hasMore) return;
    
    setLoadingMore(true);
    try {
      const res = await fetch('/api/news?category=cyber&limit=100');
      if (!res.ok) {
        throw new Error(`Failed to fetch more news: ${res.status}`);
      }
      const data = await res.json();
      const allItems = data.items || [];
      const currentCount = latest.length;
      const nextBatch = allItems.slice(currentCount, currentCount + 20); // Load 20 more
      
      setLatest(prev => [...prev, ...nextBatch]);
      setHasMore(currentCount + nextBatch.length < allItems.length);
    } catch (err: any) {
      console.error('Load more error:', err);
    } finally {
      setLoadingMore(false);
    }
  };

  if (loading) {
    return <NewsLoading />;
  }

  if (error) {
    return (
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="relative overflow-hidden rounded-2xl border border-red-200/50 bg-gradient-to-br from-red-50/50 to-red-100/30 p-8 backdrop-blur-sm dark:border-red-800/50 dark:from-red-950/40 dark:to-red-900/20">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent" />
          <div className="relative z-10 text-center">
            <div className="mb-4 flex items-center justify-center gap-3">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm font-semibold text-red-600 dark:text-red-400">ERROR</span>
            </div>
            <h2 className="text-2xl font-bold text-red-800 dark:text-red-200 mb-2">Failed to Load News</h2>
            <p className="text-red-600 dark:text-red-300 mb-6">{error}</p>
            <button 
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-2 rounded-lg bg-red-100 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-200 transition-all duration-300 border border-red-200 dark:bg-red-900/50 dark:text-red-200 dark:hover:bg-red-800/50 dark:border-red-700"
            >
              Try Again
            </button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 space-y-8">
      {/* HERO */}
      <section className="relative">
        <div className="text-center mb-12">
          <div className="relative inline-block">
            <h1 className="text-5xl md:text-7xl font-bold title-future mb-6 relative z-10">
              Latest News
            </h1>
            <div className="absolute -inset-4 bg-gradient-to-r from-[var(--brand)]/20 via-[var(--brand)]/10 to-[var(--brand)]/20 rounded-2xl blur-xl opacity-60" />
          </div>
          <div className="w-32 h-1 mx-auto bg-gradient-to-r from-transparent via-[var(--brand)] to-transparent rounded-full mb-8" />
          <p className="text-xl text-[var(--muted)] max-w-3xl mx-auto leading-relaxed">
            Stay ahead with real-time security intelligence and breaking news from the cybersecurity world
          </p>
        </div>
      </section>

      {/* Breaking news banner */}
      <section>
        <div className="relative overflow-hidden rounded-3xl border border-[var(--brand)]/30 bg-gradient-to-r from-[var(--brand)]/10 via-[var(--brand)]/5 to-transparent p-8 backdrop-blur-sm shadow-lg shadow-[var(--brand)]/10">
          <div className="absolute inset-0 bg-gradient-to-r from-[var(--brand)]/15 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent dark:from-white/10" />
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3">
                <div className="h-3 w-3 rounded-full bg-red-500 animate-pulse shadow-lg shadow-red-500/50" />
                <span className="text-sm font-bold text-[var(--brand)] tracking-wider">BREAKING</span>
              </div>
              <span className="text-sm text-[var(--muted)] font-medium">Real-time security updates</span>
            </div>
            <div className="text-xs text-[var(--muted)] font-mono">
              {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">{latest.length}</div>
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
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">24/7</div>
            <div className="text-sm text-[var(--muted)] font-medium">Monitoring</div>
          </div>
        </div>
      </section>

      {/* FEED + RIGHT SIDEBAR */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--fg)]">Security News Feed</h2>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>Live updates</span>
            </div>
          </div>
          <NewsList items={latest} />
          
          {/* Load More Button */}
          {hasMore && (
            <div className="flex justify-center pt-6">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="
                  relative overflow-hidden rounded-2xl border border-[var(--brand)]/30 
                  bg-gradient-to-r from-[var(--brand)]/10 to-[var(--brand)]/5 
                  px-8 py-4 text-[var(--brand)] font-semibold
                  hover:from-[var(--brand)]/20 hover:to-[var(--brand)]/10
                  hover:border-[var(--brand)]/50
                  transition-all duration-300
                  disabled:opacity-50 disabled:cursor-not-allowed
                  focus:outline-none focus:ring-2 focus:ring-[var(--brand)]/30
                "
              >
                {loadingMore ? (
                  <div className="flex items-center gap-3">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--brand)]"></div>
                    <span>Loading More...</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-3">
                    <span>Load More Articles</span>
                    <div className="text-lg">↓</div>
                  </div>
                )}
              </button>
            </div>
          )}
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar pinned={pinned} latest={latest} />
        </aside>
      </section>
    </main>
  );
}
