'use client';

import { useState } from 'react';
import NewsClientWrapper from './NewsClientWrapper';
import RightSidebar from './RightSidebar';
import NewsStats from './NewsStats';

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

export default function NewsPageClient() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const handleStatsUpdate = (newsItems: NewsItem[], total: number) => {
    setNews(newsItems);
    setTotalCount(total);
    setLoading(false);
  };

  return (
    <>
      {/* Stats bar */}
      <NewsStats news={news} totalCount={totalCount} loading={loading} />

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
          <NewsClientWrapper 
            initialNews={[]} 
            totalCount={0} 
            onStatsUpdate={handleStatsUpdate}
          />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar pinned={news.slice(0, 5)} latest={news} />
        </aside>
      </section>
    </>
  );
}
