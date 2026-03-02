'use client';

import { useState, ReactNode } from 'react';

export interface JsonViewerPanelProps {
  data: unknown;
  title?: string;
  defaultOpen?: boolean;
  maxHeight?: string;
}

export default function JsonViewerPanel({
  data,
  title = 'View Raw JSON',
  defaultOpen = false,
  maxHeight = '400px',
}: JsonViewerPanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className="rounded-xl border overflow-hidden"
      style={{ background: 'var(--card-2)', borderColor: 'var(--border)' }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left text-sm font-medium transition-colors hover:opacity-90"
        style={{ color: 'var(--text)' }}
      >
        <span>{title}</span>
        <span style={{ color: 'var(--muted)' }}>{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div
          className="overflow-auto scrollbar-thin border-t"
          style={{
            maxHeight,
            borderColor: 'var(--border)',
            lineHeight: 1.5,
          }}
        >
          <pre
            className="p-4 text-xs font-mono whitespace-pre-wrap break-all"
            style={{ color: 'var(--text)' }}
          >
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
