'use client';

export type BadgeVariant =
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'info'
  | 'success'
  | 'good'
  | 'completed'
  | 'neutral';

const variantStyles: Record<BadgeVariant, string> = {
  critical: 'bg-red-900/40 text-red-200 border-red-500/50',
  high: 'bg-amber-900/40 text-amber-200 border-amber-500/50',
  medium: 'bg-yellow-900/40 text-yellow-200 border-yellow-500/50',
  low: 'bg-blue-900/40 text-blue-200 border-blue-500/50',
  info: 'bg-slate-800/60 text-slate-200 border-slate-500/50',
  success: 'bg-emerald-900/40 text-emerald-200 border-emerald-500/50',
  good: 'bg-emerald-900/40 text-emerald-200 border-emerald-500/50',
  completed: 'bg-emerald-900/40 text-emerald-200 border-emerald-500/50',
  neutral: 'bg-slate-800/60 text-slate-300 border-slate-600',
};

export interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  className?: string;
}

export default function Badge({ children, variant = 'neutral', size = 'md', className = '' }: BadgeProps) {
  const sizeClass = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs';
  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border ${variantStyles[variant]} ${sizeClass} ${className}`}
    >
      {children}
    </span>
  );
}
