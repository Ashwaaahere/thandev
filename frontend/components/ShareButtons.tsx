'use client';

import { useState } from 'react';

interface ShareButtonsProps {
  title: string;
  url: string;
}

export default function ShareButtons({ title, url }: ShareButtonsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy link:', err);
    }
  };

  const tweetUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`;

  return (
    <div className="space-y-2">
      <button
        onClick={handleCopyLink}
        className="w-full rounded-lg bg-[var(--muted)]/10 px-4 py-2 text-sm font-semibold text-[var(--muted)] hover:bg-[var(--muted)]/20 transition-all duration-300 border border-[var(--muted)]/30"
      >
        {copied ? 'Copied!' : 'Copy Link'}
      </button>
      <a
        href={tweetUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="block w-full rounded-lg bg-blue-500/10 px-4 py-2 text-center text-sm font-semibold text-blue-500 hover:bg-blue-500/20 transition-all duration-300 border border-blue-500/30"
      >
        Tweet
      </a>
    </div>
  );
}
