'use client';

import { useState, useEffect } from 'react';

interface CopyLinkButtonProps {
  href: string;
  className?: string;
}

export default function CopyLinkButton({ href, className = '' }: CopyLinkButtonProps) {
  const [copied, setCopied] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleCopy = async () => {
    if (typeof window === 'undefined') return;
    const fullUrl = `${window.location.origin}${href}`;
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy link:', err);
    }
  };

  // Render placeholder during SSR/SSG
  if (!mounted) {
    return (
      <button
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${className}`}
        style={{
          background: 'transparent',
          color: 'var(--fg)',
          border: '1px solid var(--border)',
        }}
        disabled
      >
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
          />
        </svg>
        Copy link
      </button>
    );
  }

  return (
    <button
      onClick={handleCopy}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${className}`}
      style={{
        background: copied ? 'var(--brand)' : 'transparent',
        color: copied ? 'white' : 'var(--fg)',
        border: `1px solid ${copied ? 'var(--brand)' : 'var(--border)'}`,
      }}
      title="Copy link to this page"
    >
      <svg
        className="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        {copied ? (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        ) : (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
          />
        )}
      </svg>
      {copied ? 'Copied!' : 'Copy link'}
    </button>
  );
}


