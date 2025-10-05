'use client';

import { useState, useEffect } from 'react';
import { User } from 'next-auth';

interface PerformanceScan {
  id: string;
  url: string;
  status: 'completed' | 'scanning' | 'error';
  timestamp: Date;
  score: number;
  device: 'desktop' | 'mobile';
  metrics: {
    firstContentfulPaint: number;
    largestContentfulPaint: number;
    firstMeaningfulPaint: number;
    speedIndex: number;
    cumulativeLayoutShift: number;
    totalBlockingTime: number;
    interactive: number;
    firstInputDelay: number;
  };
  opportunities: Array<{
    id: string;
    title: string;
    description: string;
    score: number;
    savings: number;
  }>;
  diagnostics: Array<{
    id: string;
    title: string;
    description: string;
    score: number;
  }>;
  categories: {
    performance: number;
    accessibility: number;
    bestPractices: number;
    seo: number;
  };
  screenshot?: string;
}

interface SecurityScan {
  id: string;
  url: string;
  status: 'completed' | 'scanning' | 'error';
  timestamp: Date;
  score: number;
  vulnerabilities: Array<{
    id: string;
    title: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    description: string;
    solution: string;
    cve?: string;
  }>;
  recommendations: Array<{
    id: string;
    title: string;
    description: string;
    priority: 'low' | 'medium' | 'high';
  }>;
  scanType: 'full' | 'quick' | 'custom';
}

interface ScanHistoryClientProps {
  user: User;
}

export default function ScanHistoryClient({ user }: ScanHistoryClientProps) {
  const [activeTab, setActiveTab] = useState<'performance' | 'security'>('performance');
  const [performanceScans, setPerformanceScans] = useState<PerformanceScan[]>([]);
  const [securityScans, setSecurityScans] = useState<SecurityScan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Load scan history from localStorage
    const loadScanHistory = () => {
      try {
        const perfScans = localStorage.getItem('thandev-performance-scans');
        const secScans = localStorage.getItem('thandev-scans');
        
        if (perfScans) {
          const parsed = JSON.parse(perfScans);
          setPerformanceScans(parsed.map((scan: any) => ({
            ...scan,
            timestamp: new Date(scan.timestamp)
          })));
        }
        
        if (secScans) {
          const parsed = JSON.parse(secScans);
          setSecurityScans(parsed.map((scan: any) => ({
            ...scan,
            timestamp: new Date(scan.timestamp),
            vulnerabilities: scan.vulnerabilities || [],
            recommendations: scan.recommendations || []
          })));
        }
      } catch (error) {
        console.error('Error loading scan history:', error);
      } finally {
        setLoading(false);
      }
    };

    loadScanHistory();
  }, []);

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-500';
    if (score >= 70) return 'text-yellow-500';
    if (score >= 50) return 'text-orange-500';
    return 'text-red-500';
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 90) return 'bg-green-500/10 border-green-500/20';
    if (score >= 70) return 'bg-yellow-500/10 border-yellow-500/20';
    if (score >= 50) return 'bg-orange-500/10 border-orange-500/20';
    return 'bg-red-500/10 border-red-500/20';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-500 bg-red-500/10';
      case 'high': return 'text-orange-500 bg-orange-500/10';
      case 'medium': return 'text-yellow-500 bg-yellow-500/10';
      case 'low': return 'text-green-500 bg-green-500/10';
      default: return 'text-gray-500 bg-gray-500/10';
    }
  };

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  };

  const PerformanceScanCard = ({ scan }: { scan: PerformanceScan }) => (
    <div className="p-6 rounded-xl border shadow-lg hover:shadow-xl transition-all duration-300" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>
            {scan.url}
          </h3>
          <div className="flex items-center gap-4 text-sm" style={{ color: 'var(--muted)' }}>
            <span>{formatDate(scan.timestamp)}</span>
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
              {scan.device}
            </span>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreBgColor(scan.score)}`}>
          <span className={getScoreColor(scan.score)}>{scan.score}</span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-blue-500">{scan.categories.performance}</div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Performance</div>
        </div>
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-green-500">{scan.categories.accessibility}</div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Accessibility</div>
        </div>
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-purple-500">{scan.categories.bestPractices}</div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Best Practices</div>
        </div>
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-orange-500">{scan.categories.seo}</div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>SEO</div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            scan.status === 'completed' ? 'bg-green-500' : 
            scan.status === 'scanning' ? 'bg-yellow-500' : 'bg-red-500'
          }`}></div>
          <span className="text-sm capitalize" style={{ color: 'var(--muted)' }}>
            {scan.status}
          </span>
        </div>
        <button className="px-4 py-2 rounded-lg text-sm font-medium transition-colors" style={{ background: 'var(--brand)', color: 'white' }}>
          View Details
        </button>
      </div>
    </div>
  );

  const SecurityScanCard = ({ scan }: { scan: SecurityScan }) => (
    <div className="p-6 rounded-xl border shadow-lg hover:shadow-xl transition-all duration-300" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>
            {scan.url}
          </h3>
          <div className="flex items-center gap-4 text-sm" style={{ color: 'var(--muted)' }}>
            <span>{formatDate(scan.timestamp)}</span>
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {scan.scanType}
            </span>
          </div>
        </div>
        <div className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreBgColor(scan.score)}`}>
          <span className={getScoreColor(scan.score)}>{scan.score}</span>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-red-500">
            {scan.vulnerabilities.filter(v => v.severity === 'critical').length}
          </div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Critical</div>
        </div>
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-orange-500">
            {scan.vulnerabilities.filter(v => v.severity === 'high').length}
          </div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>High</div>
        </div>
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-yellow-500">
            {scan.vulnerabilities.filter(v => v.severity === 'medium').length}
          </div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Medium</div>
        </div>
        <div className="text-center p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
          <div className="text-2xl font-bold text-green-500">
            {scan.vulnerabilities.filter(v => v.severity === 'low').length}
          </div>
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Low</div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            scan.status === 'completed' ? 'bg-green-500' : 
            scan.status === 'scanning' ? 'bg-yellow-500' : 'bg-red-500'
          }`}></div>
          <span className="text-sm capitalize" style={{ color: 'var(--muted)' }}>
            {scan.status}
          </span>
        </div>
        <button className="px-4 py-2 rounded-lg text-sm font-medium transition-colors" style={{ background: 'var(--brand)', color: 'white' }}>
          View Details
        </button>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-12 w-12 border-2 border-blue-500 border-t-transparent"></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <div className="h-10 w-10 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)' }}>
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h1 className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>Scan History</h1>
              <p className="text-sm" style={{ color: 'var(--muted)' }}>View your performance and security scan results</p>
            </div>
          </div>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
              <div className="text-2xl font-bold text-blue-600">{performanceScans.length}</div>
              <div className="text-sm" style={{ color: 'var(--muted)' }}>Performance Scans</div>
            </div>
            <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
              <div className="text-2xl font-bold text-red-600">{securityScans.length}</div>
              <div className="text-sm" style={{ color: 'var(--muted)' }}>Security Scans</div>
            </div>
            <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
              <div className="text-2xl font-bold text-green-600">
                {performanceScans.length > 0 ? Math.round(performanceScans.reduce((sum, scan) => sum + scan.score, 0) / performanceScans.length) : 0}
              </div>
              <div className="text-sm" style={{ color: 'var(--muted)' }}>Avg Performance</div>
            </div>
            <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
              <div className="text-2xl font-bold text-purple-600">
                {securityScans.length > 0 ? Math.round(securityScans.reduce((sum, scan) => sum + scan.score, 0) / securityScans.length) : 0}
              </div>
              <div className="text-sm" style={{ color: 'var(--muted)' }}>Avg Security</div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="flex space-x-1 p-1 rounded-lg" style={{ background: 'var(--surface-2)' }}>
            <button
              onClick={() => setActiveTab('performance')}
              className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                activeTab === 'performance'
                  ? 'text-white shadow-lg'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              style={{
                background: activeTab === 'performance' ? 'var(--brand)' : 'transparent',
                color: activeTab === 'performance' ? 'white' : 'var(--muted)'
              }}
            >
              Performance Scans ({performanceScans.length})
            </button>
            <button
              onClick={() => setActiveTab('security')}
              className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                activeTab === 'security'
                  ? 'text-white shadow-lg'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              style={{
                background: activeTab === 'security' ? 'var(--brand)' : 'transparent',
                color: activeTab === 'security' ? 'white' : 'var(--muted)'
              }}
            >
              Security Scans ({securityScans.length})
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-6">
          {activeTab === 'performance' ? (
            performanceScans.length > 0 ? (
              performanceScans.map((scan) => (
                <PerformanceScanCard key={scan.id} scan={scan} />
              ))
            ) : (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                  <svg className="w-8 h-8" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>No Performance Scans Yet</h3>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>Start scanning websites to see your performance history here.</p>
              </div>
            )
          ) : (
            securityScans.length > 0 ? (
              securityScans.map((scan) => (
                <SecurityScanCard key={scan.id} scan={scan} />
              ))
            ) : (
              <div className="text-center py-12">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                  <svg className="w-8 h-8" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>No Security Scans Yet</h3>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>Start scanning websites to see your security history here.</p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
