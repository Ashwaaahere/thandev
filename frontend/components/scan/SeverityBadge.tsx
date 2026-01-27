/**
 * Standardized Severity Badge Component
 * Displays vulnerability severity with consistent styling
 */
import React from 'react';

export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info' | 'unknown';

interface SeverityBadgeProps {
  severity: string | null | undefined;
  size?: 'sm' | 'md' | 'lg';
  showIcon?: boolean;
}

const SEVERITY_CONFIG: Record<SeverityLevel, {
  label: string;
  icon: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}> = {
  critical: {
    label: 'Critical',
    icon: '🔴',
    bgColor: 'bg-red-500/10',
    textColor: 'text-red-400',
    borderColor: 'border-red-500/30',
  },
  high: {
    label: 'High',
    icon: '🟠',
    bgColor: 'bg-orange-500/10',
    textColor: 'text-orange-400',
    borderColor: 'border-orange-500/30',
  },
  medium: {
    label: 'Medium',
    icon: '🟡',
    bgColor: 'bg-yellow-500/10',
    textColor: 'text-yellow-400',
    borderColor: 'border-yellow-500/30',
  },
  low: {
    label: 'Low',
    icon: '🟢',
    bgColor: 'bg-blue-500/10',
    textColor: 'text-blue-400',
    borderColor: 'border-blue-500/30',
  },
  info: {
    label: 'Info',
    icon: 'ℹ️',
    bgColor: 'bg-slate-500/10',
    textColor: 'text-slate-400',
    borderColor: 'border-slate-500/30',
  },
  unknown: {
    label: 'Unknown',
    icon: '❓',
    bgColor: 'bg-slate-600/10',
    textColor: 'text-slate-500',
    borderColor: 'border-slate-600/30',
  },
};

const SIZE_CLASSES = {
  sm: {
    container: 'px-2 py-0.5 text-xs gap-1',
    icon: 'text-xs',
  },
  md: {
    container: 'px-2.5 py-1 text-sm gap-1.5',
    icon: 'text-sm',
  },
  lg: {
    container: 'px-3 py-1.5 text-base gap-2',
    icon: 'text-base',
  },
};

/**
 * Normalize severity string to standard severity level
 */
function normalizeSeverity(severity: string | null | undefined): SeverityLevel {
  if (!severity) return 'unknown';
  
  const normalized = severity.toLowerCase().trim();
  
  // Handle various severity formats
  if (normalized === 'critical' || normalized === 'crit') return 'critical';
  if (normalized === 'high' || normalized === 'h') return 'high';
  if (normalized === 'medium' || normalized === 'med' || normalized === 'moderate' || normalized === 'm') return 'medium';
  if (normalized === 'low' || normalized === 'l') return 'low';
  if (normalized === 'info' || normalized === 'informational' || normalized === 'i') return 'info';
  
  return 'unknown';
}

export function SeverityBadge({
  severity,
  size = 'md',
  showIcon = true,
}: SeverityBadgeProps) {
  const severityLevel = normalizeSeverity(severity);
  const config = SEVERITY_CONFIG[severityLevel];
  const sizeClasses = SIZE_CLASSES[size];

  return (
    <span
      className={`inline-flex items-center rounded-md border font-medium ${
        config.bgColor
      } ${config.textColor} ${config.borderColor} ${sizeClasses.container}`}
    >
      {showIcon && (
        <span className={sizeClasses.icon}>{config.icon}</span>
      )}
      <span>{config.label}</span>
    </span>
  );
}

/**
 * Severity counts component for displaying vulnerability distribution
 */
interface SeverityCountsProps {
  counts: {
    critical?: number;
    high?: number;
    medium?: number;
    low?: number;
    info?: number;
  };
  size?: 'sm' | 'md' | 'lg';
}

export function SeverityCounts({ counts, size = 'md' }: SeverityCountsProps) {
  const severityLevels: SeverityLevel[] = ['critical', 'high', 'medium', 'low', 'info'];
  
  return (
    <div className="flex flex-wrap items-center gap-2">
      {severityLevels.map((level) => {
        const count = counts[level] || 0;
        if (count === 0) return null;
        
        const config = SEVERITY_CONFIG[level];
        const sizeClasses = SIZE_CLASSES[size];
        
        return (
          <div
            key={level}
            className={`inline-flex items-center rounded-md border ${
              config.bgColor
            } ${config.textColor} ${config.borderColor} ${sizeClasses.container}`}
          >
            <span className={sizeClasses.icon}>{config.icon}</span>
            <span className="font-semibold">{count}</span>
            <span className="capitalize">{config.label}</span>
          </div>
        );
      })}
    </div>
  );
}

