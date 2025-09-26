'use client';

import { useState, useEffect } from 'react';
import NewsList from '../../app/news/NewsList';
import LoadMoreButton from './LoadMoreButton';

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
  initialNews: NewsItem[];
  totalCount: number;
};

export default function NewsClientWrapper({ initialNews, totalCount }: Props) {
  const [news, setNews] = useState(initialNews);
  const [totalNewsCount, setTotalNewsCount] = useState(totalCount);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(initialNews.length === 0);

  // Fetch initial data if not provided
  useEffect(() => {
    if (initialNews.length === 0) {
      const fetchInitialData = async () => {
        setInitialLoading(true);
        try {
          const res = await fetch('/api/news?category=cyber&limit=100');
          if (!res.ok) {
            throw new Error(`Failed to fetch news: ${res.status}`);
          }
          
          const data = await res.json();
          const items = data.items || [];
          setNews(items.slice(0, 31)); // Show first 31 articles
          setTotalNewsCount(data.total || items.length);
        } catch (error) {
          console.error('Initial data fetch error:', error);
        } finally {
          setInitialLoading(false);
        }
      };
      
      fetchInitialData();
    }
  }, [initialNews.length]);

  const handleLoadMore = async () => {
    setLoading(true);
    try {
      // Fetch more news from the API
      const res = await fetch('/api/news?category=cyber&limit=100');
      if (!res.ok) {
        throw new Error(`Failed to fetch more news: ${res.status}`);
      }
      
      const data = await res.json();
      const allItems = data.items || [];
      const currentCount = news.length;
      const nextBatch = allItems.slice(currentCount, currentCount + 20);
      
      setNews(prev => [...prev, ...nextBatch]);
    } catch (error) {
      console.error('Load more error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Show loading state while fetching initial data
  if (initialLoading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-[var(--muted)]">Loading news...</p>
      </div>
    );
  }

  return (
    <>
      <NewsList items={news} />
      <LoadMoreButton
        currentCount={news.length}
        totalCount={totalNewsCount}
        onLoadMore={handleLoadMore}
      />
    </>
  );
}
