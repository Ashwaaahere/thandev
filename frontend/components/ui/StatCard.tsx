'use client';

import { ReactNode } from 'react';

export interface StatCardProps {
  label: string;
  value: ReactNode;
  className?: string;
  accent?: 'default' | 'critical' | 'high' | 'success' | 'muted';
}

const accentStyles: Record<string, { label: string; value: string }> = {
  default: { label: 'var(--muted)', value: 'var(--text)' },
  critical: { label: 'rgba(248, 113, 113, 0.9)', value: 'rgb(254, 202, 202)' },
  high: { label: 'rgba(251, 191, 36, 0.9)', value: 'rgb(253, 224, 71)' },
  success: { label: 'rgba(34, 197, 94, 0.9)', value: 'rgb(134, 239, 172)' },
  muted: { label: 'var(--muted)', value: 'var(--muted)' },
};

export default function StatCard({ label, value, className = '', accent = 'default' }: StatCardProps) {
  const style = accentStyles[accent] ?? accentStyles.default;
  return (
    <div
      className={`rounded-xl border p-5 shadow-sm ${className}`}
      style={{ background: 'var(--card)', borderColor: 'var(--border)' }}
    >
      <p className="text-xs font-medium uppercase tracking-wide mb-1.5" style={{ color: style.label }}>
        {label}
      </p>
      <div className="text-2xl font-bold" style={{ color: style.value }}>
        {value}
      </div>
    </div>
  );
}
