'use client';

import { useState, useMemo } from 'react';
import { docsNav, type NavItem } from '@/lib/docs/nav';

interface DocsSearchProps {
  onSelect?: (item: NavItem) => void;
  className?: string;
}

export default function DocsSearch({ onSelect, className = '' }: DocsSearchProps) {
  const [query, setQuery] = useState('');

  const filteredItems = useMemo(() => {
    if (!query.trim()) {
      return [];
    }

    const lowerQuery = query.toLowerCase();
    return docsNav.filter(item => {
      const searchableText = `${item.title} ${item.shortDescription} ${item.keywords.join(' ')}`.toLowerCase();
      return searchableText.includes(lowerQuery);
    });
  }, [query]);

  const handleSelect = (item: NavItem) => {
    setQuery('');
    if (onSelect) {
      onSelect(item);
    }
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        <svg
          className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4"
          style={{ color: 'var(--muted)' }}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Q Search documentation..."
          className="w-full pl-10 pr-4 py-2 rounded-lg text-sm"
          style={{
            background: 'var(--surface)',
            color: 'var(--fg)',
            border: '1px solid var(--border)',
          }}
        />
      </div>

      {query && filteredItems.length > 0 && (
        <div
          className="absolute z-50 mt-2 w-full rounded-lg border shadow-lg max-h-64 overflow-y-auto"
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
          }}
        >
          {filteredItems.map((item) => (
            <button
              key={item.href}
              onClick={() => handleSelect(item)}
              className="w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors border-b last:border-b-0"
              style={{ borderColor: 'var(--border)' }}
            >
              <div className="font-medium text-sm" style={{ color: 'var(--fg)' }}>
                {item.title}
              </div>
              <div className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
                {item.shortDescription}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


