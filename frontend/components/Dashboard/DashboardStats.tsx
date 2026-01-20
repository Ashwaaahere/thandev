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

interface DashboardStatsProps {
  session: Session | null;
}

export default function DashboardStats({ session }: DashboardStatsProps) {
  const [stats, setStats] = useState({
    totalProjects: 0,
    totalScans: 0,
    scansLast7Days: 0,
    openFindings: 0,
    threatScore: 0,
    projectIncrease: 0,
    scanPercentage: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadMetrics() {
      if (!session) {
        setIsLoading(false);
        setError('Session not available. Please refresh the page.');
        return;
      }
      
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
          
          // Calculate threat score from avg_security_score (round to nearest integer)
          const threatScore = Math.round(data.avg_security_score || 0);
          
          // Calculate project increase (mock for now, could be from historical data)
          const projectIncrease = 2; // This would ideally come from comparing with previous period
          
          // Calculate scan percentage (scans in last 7 days / total scans * 100)
          const totalScans = data.totals?.scans || 0;
          const scansLast7Days = data.recent_activity?.scans_last_7_days || 0;
          const scanPercentage = totalScans > 0 ? Math.round((scansLast7Days / totalScans) * 100) : 0;
          
          setStats({
            totalProjects: data.totals?.projects || 0,
            totalScans: totalScans,
            scansLast7Days: scansLast7Days,
            openFindings: openFindings,
            threatScore: threatScore,
            projectIncrease: projectIncrease,
            scanPercentage: scanPercentage,
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
          <div key={i} className="rounded-xl border p-5 shadow-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="animate-pulse">
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-1.5"></div>
              <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-1.5"></div>
              <div className="h-2.5 bg-gray-200 dark:bg-gray-700 rounded w-2/3"></div>
            </div>
          </div>
        ))}
      </>
    );
  }

  if (error) {
    return (
      <div className="col-span-full rounded-xl border p-5" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Could not load data: {error}. Please try again.
        </p>
      </div>
    );
  }

  // Generate bar chart data for Total Scans (5 bars with varying heights)
  const barHeights = [60, 75, 85, 90, 95]; // Heights as percentages

  return (
    <>
      {/* TOTAL PROJECTS Card */}
      <div className="rounded-xl border p-5 shadow-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-xs font-medium mb-1.5 text-gray-400">
          TOTAL PROJECTS
        </p>
        <div className="flex items-center gap-1.5 mb-2.5">
          <p className="text-2xl font-bold text-white">
            {stats.totalProjects.toString().padStart(2, '0')}
          </p>
          <div className="flex items-center gap-1 text-blue-500">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
            <span className="text-xs font-medium">+{stats.projectIncrease}</span>
          </div>
        </div>
        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full overflow-hidden bg-gray-700">
          <div 
            className="h-full rounded-full transition-all duration-300"
            style={{ 
              width: `${Math.min((stats.totalProjects / 20) * 100, 100)}%`,
              background: '#3b82f6' // blue-500
            }}
          />
        </div>
      </div>

      {/* TOTAL SCANS Card */}
      <div className="rounded-xl border p-5 shadow-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-xs font-medium mb-1.5 text-gray-400">
          TOTAL SCANS
        </p>
        <div className="flex items-center gap-1.5 mb-2.5">
          <p className="text-2xl font-bold text-white">
            {stats.totalScans}
          </p>
          <div className="flex items-center gap-1 text-green-500">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-xs font-medium">{stats.scanPercentage}%</span>
          </div>
        </div>
        {/* Bar chart */}
        <div className="flex items-end gap-1 h-10">
          {barHeights.map((height, index) => (
            <div
              key={index}
              className="flex-1 rounded-t"
              style={{
                height: `${height}%`,
                background: index < 3 ? '#16a34a' : '#22c55e', // darker green for first 3, brighter for last 2
              }}
            />
          ))}
        </div>
      </div>

      {/* OPEN FINDINGS Card */}
      <div className="rounded-xl border p-5 shadow-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-xs font-medium mb-1.5 text-gray-400">
          OPEN FINDINGS
        </p>
        <p className="text-2xl font-bold mb-1.5 text-red-500">
          {stats.openFindings.toString().padStart(2, '0')}
        </p>
        {stats.openFindings > 0 && (
          <div className="mb-2.5">
            <span 
              className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-medium text-red-500"
              style={{ background: 'rgba(239, 68, 68, 0.2)' }}
            >
              REQUIRES ATTENTION
            </span>
          </div>
        )}
        {/* Progress bar */}
        <div className="w-full h-1.5 rounded-full overflow-hidden bg-gray-700">
          <div 
            className="h-full rounded-full transition-all duration-300"
            style={{ 
              width: `${Math.min((stats.openFindings / 20) * 100, 100)}%`,
              background: '#ef4444' // red-500
            }}
          />
        </div>
      </div>

      {/* THREAT SCORE Card */}
      <div className="rounded-xl border p-5 shadow-sm" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <p className="text-xs font-medium mb-1.5 text-gray-400">
          THREAT SCORE
        </p>
        <div className="flex items-center gap-1.5 mb-2.5">
          <p className="text-2xl font-bold text-white">
            {stats.threatScore}
          </p>
          <span className="text-xs font-medium text-green-500">SECURE</span>
        </div>
        {/* Indicator segments */}
        <div className="flex gap-1">
          {[1, 2, 3, 4].map((segment) => (
            <div
              key={segment}
              className="h-1 flex-1 rounded"
              style={{
                background: segment <= 2 ? '#22c55e' : '#16a34a', // bright green for first 2, darker for last 2
              }}
            />
          ))}
        </div>
      </div>
    </>
  );
}
