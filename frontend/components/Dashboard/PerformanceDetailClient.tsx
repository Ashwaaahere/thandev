'use client';

import { useState, useEffect } from 'react';
import { Session } from 'next-auth';
import Link from 'next/link';
import { thandevFetchJSON } from '@/lib/thandevApi';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

// Types
type PerformanceScanDetail = {
  id: string;
  project_id: string | null;
  target_url: string;
  scan_level: string;
  status: string;
  metrics: {
    overall_score?: number;
    first_contentful_paint_ms?: number;
    largest_contentful_paint_ms?: number;
    time_to_interactive_ms?: number;
    total_requests?: number;
    total_kb?: number;
    cumulative_layout_shift?: number;
    first_input_delay_ms?: number;
    speed_index?: number;
  } | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

// Status badge component
function ScanStatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const base = 'px-2 py-0.5 rounded-full text-xs font-medium';
  
  switch (normalized) {
    case 'completed':
      return (
        <span className={`${base} bg-green-500/10 text-green-400 border border-green-500/20`}>
          Completed
        </span>
      );
    case 'running':
    case 'queued':
      return (
        <span className={`${base} bg-blue-500/10 text-blue-400 border border-blue-500/20`}>
          {normalized === 'running' ? 'Running' : 'Queued'}
        </span>
      );
    case 'failed':
      return (
        <span className={`${base} bg-red-500/10 text-red-400 border border-red-500/20`}>
          Failed
        </span>
      );
    default:
      return (
        <span className={`${base} bg-gray-500/10 text-gray-400 border border-gray-500/20`}>
          {status}
        </span>
      );
  }
}

interface PerformanceDetailClientProps {
  scanId: string;
  session: Session | null;
}

export default function PerformanceDetailClient({ scanId, session }: PerformanceDetailClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scan, setScan] = useState<PerformanceScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    
    let cancelled = false;

    async function loadScan() {
      setLoading(true);
      setError(null);
      
      try {
        const data = await thandevFetchJSON<PerformanceScanDetail>(
          `/api/performance/${scanId}`,
          session
        );
        
        if (!cancelled) {
          setScan(data);
        }
      } catch (e) {
        console.error('Error loading performance scan:', e);
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load performance scan');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadScan();

    return () => {
      cancelled = true;
    };
  }, [scanId, session]);

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return '–';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  const getScoreColor = (score: number | null | undefined) => {
    if (score === null || score === undefined) return 'text-gray-400';
    if (score >= 90) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    if (score >= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  const getMetricStatus = (value: number | null | undefined, thresholds: { good: number; needsImprovement: number }) => {
    if (value === null || value === undefined) return { label: 'N/A', color: 'text-gray-400' };
    if (value <= thresholds.good) return { label: 'Good', color: 'text-green-400' };
    if (value <= thresholds.needsImprovement) return { label: 'Needs Improvement', color: 'text-yellow-400' };
    return { label: 'Poor', color: 'text-red-400' };
  };

  if (loading) {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader 
            user={session?.user} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-6xl mx-auto">
              <div className="rounded-xl border p-8 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-8"></div>
                <div className="space-y-4">
                  <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                  <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded"></div>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (error || !scan) {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader 
            user={session?.user} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-6xl mx-auto">
              <div className="rounded-xl border p-6 mb-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <p className="text-sm text-red-400 mb-4">{error || 'Performance scan not found'}</p>
                <Link
                  href="/dashboard/performance/history"
                  className="text-sm font-medium hover:opacity-80 transition-opacity"
                  style={{ color: 'var(--brand)' }}
                >
                  ← Back to Performance History
                </Link>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const metrics = scan.metrics || {};
  const overallScore = metrics.overall_score;

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader 
          user={session?.user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-6xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <Link
                  href="/dashboard/performance/history"
                  className="text-sm font-medium hover:opacity-80 transition-opacity mb-2 inline-block"
                  style={{ color: 'var(--brand)' }}
                >
                  ← Back to Performance History
                </Link>
                <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                  Performance Scan Results
                </h1>
                <p className="text-sm font-mono" style={{ color: 'var(--muted)' }}>
                  {scan.target_url}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <ScanStatusBadge status={scan.status} />
                {overallScore !== null && overallScore !== undefined && (
                  <div className="text-right">
                    <div className={`text-3xl font-bold ${getScoreColor(overallScore)}`}>
                      {overallScore.toFixed(0)}
                    </div>
                    <div className="text-xs" style={{ color: 'var(--muted)' }}>Performance Score</div>
                  </div>
                )}
              </div>
            </div>

            {/* Metrics Grid */}
            {metrics && Object.keys(metrics).length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* First Contentful Paint */}
                {metrics.first_contentful_paint_ms !== undefined && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>First Contentful Paint</div>
                    <div className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                      {(metrics.first_contentful_paint_ms / 1000).toFixed(2)}s
                    </div>
                    <div className={`text-xs ${getMetricStatus(metrics.first_contentful_paint_ms, { good: 1800, needsImprovement: 3000 }).color}`}>
                      {getMetricStatus(metrics.first_contentful_paint_ms, { good: 1800, needsImprovement: 3000 }).label}
                    </div>
                  </div>
                )}

                {/* Largest Contentful Paint */}
                {metrics.largest_contentful_paint_ms !== undefined && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Largest Contentful Paint</div>
                    <div className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                      {(metrics.largest_contentful_paint_ms / 1000).toFixed(2)}s
                    </div>
                    <div className={`text-xs ${getMetricStatus(metrics.largest_contentful_paint_ms, { good: 2500, needsImprovement: 4000 }).color}`}>
                      {getMetricStatus(metrics.largest_contentful_paint_ms, { good: 2500, needsImprovement: 4000 }).label}
                    </div>
                  </div>
                )}

                {/* Time to Interactive */}
                {metrics.time_to_interactive_ms !== undefined && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Time to Interactive</div>
                    <div className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                      {(metrics.time_to_interactive_ms / 1000).toFixed(2)}s
                    </div>
                    <div className={`text-xs ${getMetricStatus(metrics.time_to_interactive_ms, { good: 3800, needsImprovement: 7300 }).color}`}>
                      {getMetricStatus(metrics.time_to_interactive_ms, { good: 3800, needsImprovement: 7300 }).label}
                    </div>
                  </div>
                )}

                {/* Total Requests */}
                {metrics.total_requests !== undefined && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Total Requests</div>
                    <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                      {metrics.total_requests}
                    </div>
                  </div>
                )}

                {/* Total KB */}
                {metrics.total_kb !== undefined && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Total Size</div>
                    <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                      {metrics.total_kb > 1024 
                        ? `${(metrics.total_kb / 1024).toFixed(2)} MB`
                        : `${metrics.total_kb.toFixed(0)} KB`}
                    </div>
                  </div>
                )}

                {/* Cumulative Layout Shift */}
                {metrics.cumulative_layout_shift !== undefined && (
                  <div className="rounded-xl border p-4" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Cumulative Layout Shift</div>
                    <div className="text-2xl font-bold mb-1" style={{ color: 'var(--fg)' }}>
                      {metrics.cumulative_layout_shift.toFixed(3)}
                    </div>
                    <div className={`text-xs ${getMetricStatus(metrics.cumulative_layout_shift, { good: 0.1, needsImprovement: 0.25 }).color}`}>
                      {getMetricStatus(metrics.cumulative_layout_shift, { good: 0.1, needsImprovement: 0.25 }).label}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Suggested Improvements */}
            {metrics && (
              <div className="rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                <h2 className="text-xl font-semibold mb-4" style={{ color: 'var(--fg)' }}>
                  Suggested Improvements
                </h2>
                <ul className="space-y-2">
                  {metrics.largest_contentful_paint_ms && metrics.largest_contentful_paint_ms > 2500 && (
                    <li className="text-sm flex items-start gap-2" style={{ color: 'var(--fg)' }}>
                      <span className="text-yellow-400 mt-0.5">•</span>
                      <span>Largest Contentful Paint is {((metrics.largest_contentful_paint_ms / 1000).toFixed(1))}s. Consider optimizing images and reducing render-blocking resources.</span>
                    </li>
                  )}
                  {metrics.time_to_interactive_ms && metrics.time_to_interactive_ms > 3800 && (
                    <li className="text-sm flex items-start gap-2" style={{ color: 'var(--fg)' }}>
                      <span className="text-yellow-400 mt-0.5">•</span>
                      <span>Time to Interactive is {((metrics.time_to_interactive_ms / 1000).toFixed(1))}s. Reduce JavaScript execution time and minimize main-thread work.</span>
                    </li>
                  )}
                  {metrics.total_kb && metrics.total_kb > 1000 && (
                    <li className="text-sm flex items-start gap-2" style={{ color: 'var(--fg)' }}>
                      <span className="text-yellow-400 mt-0.5">•</span>
                      <span>Page size is {metrics.total_kb > 1024 ? `${(metrics.total_kb / 1024).toFixed(1)} MB` : `${metrics.total_kb.toFixed(0)} KB`}. Consider code splitting and lazy loading.</span>
                    </li>
                  )}
                  {metrics.cumulative_layout_shift && metrics.cumulative_layout_shift > 0.1 && (
                    <li className="text-sm flex items-start gap-2" style={{ color: 'var(--fg)' }}>
                      <span className="text-yellow-400 mt-0.5">•</span>
                      <span>Cumulative Layout Shift is {metrics.cumulative_layout_shift.toFixed(3)}. Ensure images and ads have size attributes.</span>
                    </li>
                  )}
                  {(!metrics.largest_contentful_paint_ms || metrics.largest_contentful_paint_ms <= 2500) &&
                   (!metrics.time_to_interactive_ms || metrics.time_to_interactive_ms <= 3800) &&
                   (!metrics.total_kb || metrics.total_kb <= 1000) &&
                   (!metrics.cumulative_layout_shift || metrics.cumulative_layout_shift <= 0.1) && (
                    <li className="text-sm" style={{ color: 'var(--muted)' }}>
                      No immediate performance improvements required. Your page meets Core Web Vitals thresholds.
                    </li>
                  )}
                </ul>
              </div>
            )}

            {/* Metadata */}
            <div className="rounded-xl border p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
              <h2 className="text-xl font-semibold mb-4" style={{ color: 'var(--fg)' }}>
                Scan Information
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Scan Level</div>
                  <div className="font-medium" style={{ color: 'var(--fg)' }}>
                    {scan.scan_level.charAt(0).toUpperCase() + scan.scan_level.slice(1)}
                  </div>
                </div>
                <div>
                  <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Status</div>
                  <div>
                    <ScanStatusBadge status={scan.status} />
                  </div>
                </div>
                <div>
                  <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Created</div>
                  <div className="font-medium" style={{ color: 'var(--fg)' }}>
                    {formatDate(scan.created_at)}
                  </div>
                </div>
                <div>
                  <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Completed</div>
                  <div className="font-medium" style={{ color: 'var(--fg)' }}>
                    {formatDate(scan.completed_at)}
                  </div>
                </div>
              </div>
              {scan.project_id && (
                <div className="mt-4">
                  <Link
                    href={`/projects/${scan.project_id}`}
                    className="text-sm font-medium hover:opacity-80 transition-opacity"
                    style={{ color: 'var(--brand)' }}
                  >
                    View Project →
                  </Link>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
