'use client';

import { useState, useEffect } from 'react';
import { Session } from 'next-auth';
import { thandevFetchJSON } from '@/lib/thandevApi';

// Types matching backend response
type DashboardMetrics = {
  // Legacy fields
  total_scans: number;
  security_scans: number;
  performance_scans: number;
  vulnerabilities_found: number;
  avg_security_score: number;
  scans_this_month: number;
  recent_scans: Array<{
    id: string;
    project_id: string;
    project_name: string;
    target_url: string;
    level: string;
    status: string;
    created_at: string;
    risk_score?: number | null;
    findings_count?: number | null;
  }>;
  // Phase 2 fields
  totals: {
    projects: number;
    scans: number;
    findings: number;
  };
  recent_activity: {
    last_scan_at: string | null;
    scans_last_7_days: number;
  };
  findings_by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  latest_scans: Array<{
    id: string;
    project_id: string;
    project_name: string;
    target_url: string;
    scan_level: string;
    status: string;
    risk_score?: number | null;
    findings_count?: number | null;
    completed_at?: string | null;
  }>;
};

interface StatCardProps {
  title: string;
  value: string | number;
  change: string;
  changeType: 'positive' | 'negative' | 'neutral';
  icon: string;
  description: string;
}

function StatCard({ title, value, change, changeType, icon, description }: StatCardProps) {
  const getChangeColor = () => {
    switch (changeType) {
      case 'positive':
        return 'text-green-600 dark:text-green-400';
      case 'negative':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getChangeIcon = () => {
    switch (changeType) {
      case 'positive':
        return 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6';
      case 'negative':
        return 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6';
      default:
        return 'M20 12H4';
    }
  };

  return (
    <div className="rounded-xl border p-6 shadow-sm hover:shadow-md transition-shadow" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>
            {title}
          </p>
          <p className="text-2xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
            {value}
          </p>
          <div className="flex items-center gap-1">
            <svg className={`w-4 h-4 ${getChangeColor()}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getChangeIcon()} />
            </svg>
            <span className={`text-sm font-medium ${getChangeColor()}`}>
              {change}
            </span>
          </div>
        </div>
        <div className="flex-shrink-0">
          <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)', opacity: 0.1 }}>
            <svg className="w-6 h-6" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
            </svg>
          </div>
        </div>
      </div>
      <p className="text-xs mt-2" style={{ color: 'var(--muted)' }}>
        {description}
      </p>
    </div>
  );
}

interface DashboardStatsProps {
  session: Session | null;
}

export default function DashboardStats({ session }: DashboardStatsProps) {
  const [stats, setStats] = useState({
    totalProjects: 0,
    totalScans: 0,
    scansLast7Days: 0,
    openFindings: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadMetrics() {
      if (!session) return;
      
      setIsLoading(true);
      setError(null);
      try {
        const data = await thandevFetchJSON<DashboardMetrics>(
          '/api/metrics/overview',
          session
        );
        
        if (!cancelled) {
          // Calculate open findings (exclude info)
          const openFindings = 
            (data.findings_by_severity?.critical || 0) +
            (data.findings_by_severity?.high || 0) +
            (data.findings_by_severity?.medium || 0) +
            (data.findings_by_severity?.low || 0);
          
          setStats({
            totalProjects: data.totals?.projects || 0,
            totalScans: data.totals?.scans || 0,
            scansLast7Days: data.recent_activity?.scans_last_7_days || 0,
            openFindings: openFindings,
          });
        }
      } catch (e) {
        console.error('Error loading dashboard metrics:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load metrics');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [session]);

  if (isLoading) {
    return (
      <>
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl border p-6 shadow-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2"></div>
              <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-2"></div>
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-2/3"></div>
            </div>
          </div>
        ))}
      </>
    );
  }

  if (error) {
    return (
      <div className="col-span-full rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-sm" style={{ color: 'var(--muted)' }}>
          Could not load data. Please try again.
        </p>
      </div>
    );
  }

  return (
    <>
      <StatCard
        title="Total Projects"
        value={stats.totalProjects}
        change={`${stats.totalProjects === 1 ? 'project' : 'projects'}`}
        changeType="neutral"
        icon="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
        description="Active security projects"
      />
      
      <StatCard
        title="Total Scans"
        value={stats.totalScans}
        change={`${stats.scansLast7Days} in last 7 days`}
        changeType="positive"
        icon="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        description="Security assessments completed"
      />
      
      <StatCard
        title="Open Findings"
        value={stats.openFindings}
        change={stats.openFindings > 0 ? "Requires attention" : "All clear"}
        changeType={stats.openFindings > 0 ? "negative" : "positive"}
        icon="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
        description="Security issues to address"
      />
      
      <StatCard
        title="This Week"
        value={stats.scansLast7Days}
        change="Recent activity"
        changeType="positive"
        icon="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
        description="Scans in last 7 days"
      />
    </>
  );
}
