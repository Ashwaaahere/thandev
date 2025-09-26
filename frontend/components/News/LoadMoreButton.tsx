'use client';

import { useState } from 'react';

type LoadMoreButtonProps = {
  currentCount: number;
  totalCount: number;
  onLoadMore: () => void;
};

export default function LoadMoreButton({ 
  currentCount, 
  totalCount, 
  onLoadMore 
}: LoadMoreButtonProps) {
  const [loading, setLoading] = useState(false);
  const hasMore = currentCount < totalCount;

  const handleLoadMore = async () => {
    if (loading || !hasMore) return;
    
    setLoading(true);
    try {
      await onLoadMore();
    } finally {
      setLoading(false);
    }
  };

  if (!hasMore) {
    return (
      <div className="flex justify-center pt-6">
        <div className="text-sm text-[var(--muted)]">
          All {totalCount} articles loaded
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-center pt-6">
      <button
        onClick={handleLoadMore}
        disabled={loading}
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
        {loading ? (
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--brand)]"></div>
            <span>Loading More...</span>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <span>Load More Articles ({totalCount - currentCount} remaining)</span>
            <div className="text-lg">↓</div>
          </div>
        )}
      </button>
    </div>
  );
}
