'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';

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

type NewsResponse = {
  items: NewsItem[];
  total: number;
  sources_checked: number;
};

export default function QuickActions() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchNews() {
      try {
        const response = await fetch('/api/news?limit=4&category=cyber');
        if (!response.ok) {
          throw new Error('Failed to fetch news');
        }
        const data: NewsResponse = await response.json();
        setNews(data.items || []);
      } catch (error) {
        console.error('Error fetching news:', error);
        setNews([]);
      } finally {
        setLoading(false);
      }
    }

    fetchNews();
  }, []);

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 60) {
        return `${diffMins}m ago`;
      } else if (diffHours < 24) {
        return `${diffHours}h ago`;
      } else if (diffDays < 7) {
        return `${diffDays}d ago`;
      } else {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      }
    } catch {
      return '';
    }
  };

  const RocketIcon = () => (
    <svg className="w-6 h-6 text-blue-400" fill="currentColor" viewBox="0 0 24 24">
      {/* Rocket pointing up and right */}
      <path d="M13 3v7h7l-7-7zm-2 8H4l7 7v-7z" />
      <circle cx="12" cy="12" r="1.5" />
    </svg>
  );

  const EyeIcon = () => (
    <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
    </svg>
  );

  const CoinsIcon = () => (
    <svg className="w-6 h-6 text-yellow-400" fill="currentColor" viewBox="0 0 24 24">
      <circle cx="10" cy="8" r="3.5" />
      <circle cx="14" cy="10" r="3.5" />
      <circle cx="12" cy="13" r="3.5" />
    </svg>
  );

  const actions = [
    {
      title: 'New Surface Scan',
      description: 'Fast attack vector assessment',
      href: '/dashboard/scan',
      iconComponent: <RocketIcon />,
      iconColor: 'text-blue-400'
    },
    {
      title: 'Review Reports',
      description: 'View detailed summaries',
      href: '/dashboard/reports',
      iconComponent: <EyeIcon />,
      iconColor: 'text-green-400'
    },
    {
      title: 'Vulnerability DB',
      description: 'Search 40k+ known exploits',
      href: '/exploits',
      iconComponent: <CoinsIcon />,
      iconColor: 'text-yellow-400'
    }
  ];

  return (
    <div className="rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      {/* Quick Actions Header */}
      <div className="px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <h2 className="text-base font-bold text-white">
            Quick Actions
          </h2>
        </div>
      </div>

      {/* Quick Actions Content */}
      <div className="p-5">
        <div className="space-y-2.5">
          {actions.map((action, index) => (
            <Link
              key={index}
              href={action.href}
              className="block p-3 rounded-lg border hover:shadow-md transition-all duration-200 group"
              style={{ 
                borderColor: 'var(--border)', 
                background: 'var(--surface-2)'
              }}
            >
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0">
                  {action.iconComponent}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold mb-0.5 text-sm text-white">
                    {action.title}
                  </h3>
                  <p className="text-xs text-gray-400">
                    {action.description}
                  </p>
                </div>
                <div className="flex-shrink-0">
                  <svg className="w-4 h-4 text-gray-400 group-hover:translate-x-1 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* LIVE NEWS FEED Section */}
      <div className="px-5 py-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-1.5 mb-3">
          <div className="w-1.5 h-1.5 rounded-full bg-blue-400"></div>
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wide">
            LIVE NEWS FEED
          </h3>
        </div>
        <div className="space-y-2.5">
          {loading ? (
            <div className="text-[10px] text-gray-400">Loading news...</div>
          ) : news.length === 0 ? (
            <div className="text-[10px] text-gray-400">No news available</div>
          ) : (
            news.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block group"
              >
                <div className="text-[10px]">
                  <div className="flex items-start justify-between gap-1.5 mb-0.5">
                    <p className="text-white group-hover:text-blue-400 transition-colors line-clamp-2 flex-1">
                      {item.title}
                    </p>
                    <span className="text-gray-400 flex-shrink-0">
                      {formatDate(item.publishedAt)}
                    </span>
                  </div>
                  <p className="text-gray-500 text-[9px]">
                    {item.source}
                  </p>
                </div>
              </a>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
