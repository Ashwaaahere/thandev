'use client';

import { ReactNode } from 'react';

export function TabList({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`border-b px-4 pt-3 ${className}`}
      style={{ borderColor: 'var(--border)' }}
    >
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

export function Tab({
  active,
  onClick,
  children,
  className = '',
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-2 text-xs font-medium rounded-t-lg transition-colors ${className}`}
      style={{
        background: active ? 'var(--card-2)' : 'transparent',
        color: active ? 'var(--text)' : 'var(--muted)',
        borderLeft: active ? '1px solid var(--border)' : '1px solid transparent',
        borderRight: active ? '1px solid var(--border)' : '1px solid transparent',
        borderTop: active ? '1px solid var(--border)' : '1px solid transparent',
      }}
    >
      {children}
    </button>
  );
}

export function TabPanel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`p-4 ${className}`}>{children}</div>;
}
