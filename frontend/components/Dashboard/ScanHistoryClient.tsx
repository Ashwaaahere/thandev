'use client';

import { useState, useEffect } from 'react';
import { User, Session } from 'next-auth';
import Link from 'next/link';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';

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

// Backend scan types
type ScanJobListItem = {
  id: string;
  project_id: string;
  project_name?: string | null;
  target_url?: string | null;
  scan_level: string;
  status: string;
  created_at: string;
  completed_at?: string | null;
  risk_score?: number | null;
  findings_count?: number | null;
};

type ScanJobListResponse = {
  items: ScanJobListItem[];
  total: number;
};

// Legacy SecurityScan interface (for static/mock data compatibility)
interface SecurityScan {
  id: string;
  url: string;
  status: 'completed' | 'scanning' | 'error';
  timestamp: Date;
  score: number;
  scanType: 'quick' | 'comprehensive' | 'deep';
  vulnerabilities: Array<{
    id: string;
    type: string;
    severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
    title: string;
    description: string;
    recommendation: string;
    cwe?: string;
    cvss?: number;
    port?: number;
    service?: string;
  }>;
  severityBreakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  duration: number;
}

interface ScanHistoryClientProps {
  user: any;
  session: Session | null;
}

export default function ScanHistoryClient({ user, session }: ScanHistoryClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'performance' | 'security'>('performance');
  const [performanceScans, setPerformanceScans] = useState<PerformanceScan[]>([]);
  const [securityScans, setSecurityScans] = useState<SecurityScan[]>([]);
  const [selectedScan, setSelectedScan] = useState<PerformanceScan | SecurityScan | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Real security scan data from backend
  const [realSecurityScans, setRealSecurityScans] = useState<ScanJobListItem[]>([]);
  const [securityTotal, setSecurityTotal] = useState(0);
  const [isLoadingSecurity, setIsLoadingSecurity] = useState(false);
  const [errorSecurity, setErrorSecurity] = useState<string | null>(null);

  useEffect(() => {
    // Load performance scan history from localStorage (keep static for now)
    const loadScanHistory = () => {
      try {
        const perfScans = localStorage.getItem('thandev-performance-scans');
        
        if (perfScans) {
          const parsed = JSON.parse(perfScans).map((scan: any) => ({
            ...scan,
            timestamp: new Date(scan.timestamp)
          }));
          setPerformanceScans(parsed);
        }
      } catch (error) {
        console.error('Error loading scan history:', error);
      }
    };

    loadScanHistory();
  }, []);

  // Fetch real security scans from backend
  useEffect(() => {
    async function fetchSecurityScans() {
      if (!session) return;
      
      setIsLoadingSecurity(true);
      setErrorSecurity(null);
      
      try {
        const data = await thandevFetchJSON<ScanJobListResponse>(
          '/api/scans?limit=20&offset=0',
          session
        );
        
        setRealSecurityScans(data.items);
        setSecurityTotal(data.total);
      } catch (err) {
        console.error('Error fetching security scans:', err);
        setErrorSecurity(err instanceof Error ? err.message : 'Failed to load security scans');
      } finally {
        setIsLoadingSecurity(false);
      }
    }

    // Fetch when security tab is active or on mount
    if (activeTab === 'security') {
      fetchSecurityScans();
    }
  }, [activeTab, session]);

  const handleViewDetails = (scan: PerformanceScan | SecurityScan) => {
    setSelectedScan(scan);
    setShowDetails(true);
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    if (score >= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-500 bg-red-500/10';
      case 'high': return 'text-orange-500 bg-orange-500/10';
      case 'medium': return 'text-yellow-500 bg-yellow-500/10';
      case 'low': return 'text-blue-500 bg-blue-500/10';
      case 'info': return 'text-gray-500 bg-gray-500/10';
      default: return 'text-gray-500 bg-gray-500/10';
    }
  };

  // Use formatDateTime from lib/formatDate.ts for consistent timezone handling

  const totalPerformanceScans = performanceScans.length;
  const totalSecurityScans = securityTotal; // Use real total from backend
  const avgPerformance = performanceScans.length > 0 
    ? Math.round(performanceScans.reduce((sum, scan) => sum + scan.score, 0) / performanceScans.length)
    : 0;
  
  // Calculate avg security from real scans (100 - risk_score, or 0 if no risk_score)
  const completedScans = realSecurityScans.filter(s => s.status === 'completed' && s.risk_score !== null);
  const avgSecurity = completedScans.length > 0
    ? Math.round(completedScans.reduce((sum, scan) => sum + (100 - (scan.risk_score || 0)), 0) / completedScans.length)
    : 0;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      
      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <DashboardHeader 
          user={user} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        
        {/* Scan History Content */}
        <main className="flex-1 overflow-y-auto" style={{ background: 'var(--bg)' }}>
          <div className="container mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
            Scan History
          </h1>
          <p className="text-lg" style={{ color: 'var(--muted)' }}>
            View your performance and security scan results
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="p-6 rounded-2xl border shadow-lg" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Performance Scans</p>
                <p className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>{totalPerformanceScans}</p>
              </div>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-2xl border shadow-lg" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Security Scans</p>
                <p className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>{totalSecurityScans}</p>
              </div>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-2xl border shadow-lg" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Avg Performance</p>
                <p className={`text-3xl font-bold ${getScoreColor(avgPerformance)}`}>{avgPerformance}</p>
              </div>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-2xl border shadow-lg" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Avg Security</p>
                <p className={`text-3xl font-bold ${getScoreColor(avgSecurity)}`}>{avgSecurity}</p>
              </div>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex space-x-1 mb-8" style={{ background: 'var(--surface-2)', padding: '4px', borderRadius: '12px' }}>
          <button
            onClick={() => setActiveTab('performance')}
            className={`flex-1 py-3 px-6 rounded-lg font-medium transition-all ${
              activeTab === 'performance'
                ? 'text-white shadow-lg'
                : 'text-gray-500 hover:text-gray-300'
            }`}
            style={{
              background: activeTab === 'performance' ? 'var(--brand)' : 'transparent'
            }}
          >
            Performance Scans ({totalPerformanceScans})
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`flex-1 py-3 px-6 rounded-lg font-medium transition-all ${
              activeTab === 'security'
                ? 'text-white shadow-lg'
                : 'text-gray-500 hover:text-gray-300'
            }`}
            style={{
              background: activeTab === 'security' ? 'var(--brand)' : 'transparent'
            }}
          >
            Security Scans ({totalSecurityScans})
          </button>
        </div>

        {/* Scan List */}
        <div className="space-y-4">
          {activeTab === 'performance' ? (
            performanceScans.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                  <svg className="w-12 h-12" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>No Performance Scans</h3>
                <p style={{ color: 'var(--muted)' }}>Start scanning websites to see your performance history here.</p>
              </div>
            ) : (
              performanceScans.map((scan) => (
                <div key={scan.id} className="p-6 rounded-2xl border shadow-lg" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-4 mb-4">
                        <div className="flex-1">
                          <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--fg)' }}>{scan.url}</h3>
                          <div className="flex items-center gap-4 text-sm" style={{ color: 'var(--muted)' }}>
                            <span>{formatDateTime(scan.timestamp)}</span>
                            <div className="flex items-center gap-1">
                              {scan.device === 'mobile' ? (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                                </svg>
                              ) : (
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                </svg>
                              )}
                              <span className="capitalize">{scan.device}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <div className="w-2 h-2 rounded-full bg-green-500"></div>
                              <span className="capitalize">{scan.status}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="text-center">
                          <div className={`text-2xl font-bold ${getScoreColor(scan.categories.performance)}`}>
                            {scan.categories.performance}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Performance</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-2xl font-bold ${getScoreColor(scan.categories.accessibility)}`}>
                            {scan.categories.accessibility}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Accessibility</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-2xl font-bold ${getScoreColor(scan.categories.bestPractices)}`}>
                            {scan.categories.bestPractices}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>Best Practices</div>
                        </div>
                        <div className="text-center">
                          <div className={`text-2xl font-bold ${getScoreColor(scan.categories.seo)}`}>
                            {scan.categories.seo}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>SEO</div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="ml-6">
                      <button
                        onClick={() => handleViewDetails(scan)}
                        className="px-6 py-2 rounded-lg font-medium transition-all hover:opacity-90"
                        style={{ background: 'var(--brand)', color: 'white' }}
                      >
                        View Details
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )
          ) : (
            isLoadingSecurity ? (
              <div className="text-center py-12">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-4" style={{ color: 'var(--muted)' }}>Loading security scans...</p>
              </div>
            ) : errorSecurity ? (
              <div className="text-center py-12">
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
                  <p className="text-red-800 dark:text-red-200">{errorSecurity}</p>
                </div>
              </div>
            ) : isLoadingSecurity ? (
              <div className="space-y-4">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="p-6 rounded-2xl border animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                  </div>
                ))}
              </div>
            ) : errorSecurity ? (
              <div className="text-center py-12">
                <div className="p-3 rounded-lg border border-red-500/50 bg-red-500/10 mb-4">
                  <p className="text-sm text-red-400">{errorSecurity}</p>
                </div>
                <p className="text-sm" style={{ color: 'var(--muted)' }}>
                  Could not load data. Please try again.
                </p>
              </div>
            ) : realSecurityScans.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                  <svg className="w-12 h-12" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>No Security Scans</h3>
                <p style={{ color: 'var(--muted)' }}>Start scanning websites to see your security history here.</p>
              </div>
            ) : (
              realSecurityScans.map((scan) => {
                const displayUrl = scan.target_url || scan.project_name || 'Unknown target';
                const securityScore = scan.risk_score !== null && scan.risk_score !== undefined 
                  ? Math.round(100 - scan.risk_score) 
                  : null;
                const findingsCount = scan.findings_count ?? 0;
                const statusColor = scan.status === 'completed' 
                  ? 'bg-green-500' 
                  : scan.status === 'running' || scan.status === 'queued'
                  ? 'bg-yellow-500'
                  : 'bg-red-500';
                
                return (
                  <div key={scan.id} className="p-6 rounded-2xl border shadow-lg" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-4 mb-4">
                          <div className="flex-1">
                            <h3 className="text-lg font-semibold mb-1" style={{ color: 'var(--fg)' }}>{displayUrl}</h3>
                            <div className="flex items-center gap-4 text-sm" style={{ color: 'var(--muted)' }}>
                              <span>{formatDateTime(scan.created_at)}</span>
                              <span className="px-2 py-1 rounded-full text-xs font-medium" style={{ background: 'var(--surface-2)' }}>
                                {scan.scan_level.toUpperCase()}
                              </span>
                              <div className="flex items-center gap-1">
                                <div className={`w-2 h-2 rounded-full ${statusColor}`}></div>
                                <span className="capitalize">{scan.status}</span>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-6">
                          {securityScore !== null && (
                            <div className="text-center">
                              <div className={`text-3xl font-bold ${getScoreColor(securityScore)}`}>
                                {securityScore}
                              </div>
                              <div className="text-sm" style={{ color: 'var(--muted)' }}>Security Score</div>
                            </div>
                          )}
                          
                          <div className="text-center">
                            <div className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>
                              {findingsCount}
                            </div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>Findings</div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="ml-6">
                        <Link
                          href={`/projects/${scan.project_id}/scans/${scan.id}`}
                          className="px-6 py-2 rounded-lg font-medium transition-all hover:opacity-90 inline-block"
                          style={{ background: 'var(--brand)', color: 'white' }}
                        >
                          View Details
                        </Link>
                      </div>
                    </div>
                  </div>
                );
              })
            )
          )}
        </div>
      </div>

      {/* Details Modal */}
      {showDetails && selectedScan && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white dark:bg-gray-900 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                  Scan Details
                </h2>
                <button
                  onClick={() => setShowDetails(false)}
                  className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            
            <div className="p-6">
              {selectedScan ? (
                <>
                  <div className="mb-6">
                    <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>URL</h3>
                    <p className="text-sm" style={{ color: 'var(--muted)' }}>{selectedScan.url}</p>
                  </div>
              
              {activeTab === 'performance' && 'categories' in selectedScan ? (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Performance Scores</h3>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {Object.entries(selectedScan.categories).map(([category, score]) => (
                        <div key={category} className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                          <div className={`text-3xl font-bold ${getScoreColor(score)}`}>
                            {score}
                          </div>
                          <div className="text-sm capitalize" style={{ color: 'var(--muted)' }}>
                            {category.replace(/([A-Z])/g, ' $1').trim()}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Core Web Vitals</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Largest Contentful Paint</div>
                        <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                          {selectedScan.metrics.largestContentfulPaint.toFixed(0)}ms
                        </div>
                      </div>
                      <div className="p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>First Input Delay</div>
                        <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                          {selectedScan.metrics.firstInputDelay.toFixed(0)}ms
                        </div>
                      </div>
                      <div className="p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Cumulative Layout Shift</div>
                        <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                          {selectedScan.metrics.cumulativeLayoutShift.toFixed(3)}
                        </div>
                      </div>
                      <div className="p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                        <div className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>Speed Index</div>
                        <div className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>
                          {selectedScan.metrics.speedIndex.toFixed(0)}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : activeTab === 'security' && 'vulnerabilities' in selectedScan ? (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Security Overview</h3>
                    <div className="flex items-center gap-6">
                      <div className="text-center">
                        <div className={`text-4xl font-bold ${getScoreColor(selectedScan.score)}`}>
                          {selectedScan.score}
                        </div>
                        <div className="text-sm" style={{ color: 'var(--muted)' }}>Security Score</div>
                      </div>
                      <div className="flex-1">
                        <div className="grid grid-cols-5 gap-2">
                          {selectedScan.severityBreakdown && Object.entries(selectedScan.severityBreakdown).map(([severity, count]) => (
                            <div key={severity} className="text-center p-2 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                              <div className={`text-lg font-bold ${getSeverityColor(severity).split(' ')[0]}`}>
                                {count}
                              </div>
                              <div className="text-xs capitalize" style={{ color: 'var(--muted)' }}>
                                {severity}
                              </div>
                            </div>
                          ))}
                          {!selectedScan.severityBreakdown && (
                            <div className="col-span-5 text-center text-sm p-4" style={{ color: 'var(--muted)', background: 'var(--surface-2)' }}>
                              No severity data available
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div>
                    <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>Vulnerabilities</h3>
                    <div className="space-y-3">
                      {selectedScan.vulnerabilities.map((vuln) => (
                        <div key={vuln.id} className="p-4 rounded-lg border" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
                          <div className="flex items-start justify-between mb-2">
                            <h4 className="font-semibold" style={{ color: 'var(--fg)' }}>{vuln.title}</h4>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(vuln.severity)}`}>
                              {vuln.severity.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-sm mb-2" style={{ color: 'var(--muted)' }}>{vuln.description}</p>
                          <p className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                            Recommendation: {vuln.recommendation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : null}
                </>
              ) : (
                <div className="text-center py-8">
                  <p className="text-muted-foreground">No scan selected</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
        </main>
      </div>
    </div>
  );
}
