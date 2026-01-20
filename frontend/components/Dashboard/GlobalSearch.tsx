'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';

export default function GlobalSearch() {
  const router = useRouter();
  const [query, setQuery] = useState('');

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;
    
    const params = new URLSearchParams({ search: trimmed });
    router.push(`/dashboard/vulnerabilities?${params.toString()}`);
  };

  return (
    <form onSubmit={handleSubmit} className="relative w-full" style={{ height: '32px' }}>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search scans, reports, or vulnerabilities..."
        className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border transition-all duration-200 focus:outline-none focus:ring-2 focus:border-transparent placeholder:text-[var(--muted)]"
        style={{
          height: '32px',
          borderColor: 'var(--border)',
          background: 'var(--surface-2)',
          color: 'var(--fg)'
        }}
      />
      <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none">
        <svg className="h-4 w-4" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>
    </form>
  );
}

