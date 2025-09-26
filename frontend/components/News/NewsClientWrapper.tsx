'use client';

import { useState } from 'react';
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
  const [loading, setLoading] = useState(false);

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

  return (
    <>
      <NewsList items={news} />
      <LoadMoreButton
        currentCount={news.length}
        totalCount={totalCount}
        onLoadMore={handleLoadMore}
      />
    </>
  );
}
