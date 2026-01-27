/**
 * SeverityBadge Component
 * 
 * Standardized severity badge for displaying vulnerability severity levels.
 * Uses backend-normalized severity values (INFO, LOW, MEDIUM, HIGH, CRITICAL).
 */

import React from 'react';

interface SeverityBadgeProps {
  severity: string | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const severityConfig = {
  critical: {
    label: 'CRITICAL',
    bgClass: 'bg-red-900/40',
    textClass: 'text-red-200',
    borderClass: 'border-red-500/50',
  },
  high: {
    label: 'HIGH',
    bgClass: 'bg-orange-900/40',
    textClass: 'text-orange-200',
    borderClass: 'border-orange-500/50',
  },
  medium: {
    label: 'MEDIUM',
    bgClass: 'bg-yellow-900/40',
    textClass: 'text-yellow-200',
    borderClass: 'border-yellow-500/50',
  },
  low: {
    label: 'LOW',
    bgClass: 'bg-blue-900/40',
    textClass: 'text-blue-200',
    borderClass: 'border-blue-500/50',
  },
  info: {
    label: 'INFO',
    bgClass: 'bg-slate-900/40',
    textClass: 'text-slate-200',
    borderClass: 'border-slate-500/50',
  },
};

const sizeClasses = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export default function SeverityBadge({ severity, size = 'md', className = '' }: SeverityBadgeProps) {
  const normalizedSeverity = (severity || 'info').toLowerCase();
  const config = severityConfig[normalizedSeverity as keyof typeof severityConfig] || severityConfig.info;
  const sizeClass = sizeClasses[size];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border ${config.bgClass} ${config.textClass} ${config.borderClass} ${sizeClass} ${className}`}
    >
      {config.label}
    </span>
  );
}

