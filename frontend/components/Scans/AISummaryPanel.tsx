'use client';

import React from 'react';

interface AISummaryPanelProps {
  scanId: string;
}

export default function AISummaryPanel({ scanId }: AISummaryPanelProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] p-12">
      <div className="text-center space-y-4 max-w-md">
        {/* Icon */}
        <div className="mx-auto w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
          <svg
            className="w-8 h-8"
            style={{ color: 'var(--brand)' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
        </div>

        {/* Heading */}
        <h2 className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
          Coming Soon
        </h2>

        {/* Description */}
        <p className="text-base" style={{ color: 'var(--muted)' }}>
          AI-powered summary and insights for your security scans are currently under development.
        </p>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          This feature will provide intelligent analysis of your scan results, prioritized recommendations, and actionable insights.
        </p>
      </div>
    </div>
  );
}
