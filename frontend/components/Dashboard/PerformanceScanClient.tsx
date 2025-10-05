'use client';

import { useState, useEffect, useRef } from 'react';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

export interface PerformanceScanResult {
  id: string;
  url: string;
  status: 'pending' | 'scanning' | 'completed' | 'error';
  timestamp: Date;
  score: number;
  device: 'mobile' | 'desktop';
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
    displayValue: string;
    details: {
      items: Array<{
        node: {
          type: string;
          snippet: string;
          boundingRect: {
            top: number;
            bottom: number;
            left: number;
            right: number;
            width: number;
            height: number;
          };
        };
        url: string;
        wastedBytes?: number;
        wastedMs?: number;
      }>;
    };
  }>;
  diagnostics: Array<{
    id: string;
    title: string;
    description: string;
    score: number;
    displayValue: string;
    details: {
      items: Array<{
        node: {
          type: string;
          snippet: string;
          boundingRect: {
            top: number;
            bottom: number;
            left: number;
            right: number;
            width: number;
            height: number;
          };
        };
        url: string;
        wastedBytes?: number;
        wastedMs?: number;
      }>;
    };
  }>;
  categories: {
    performance: number;
    accessibility: number;
    bestPractices: number;
    seo: number;
  };
  screenshot?: string;
}

interface PerformanceScanClientProps {
  user: any;
}

export default function PerformanceScanClient({ user }: PerformanceScanClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scans, setScans] = useState<PerformanceScanResult[]>([]);
  const [currentScan, setCurrentScan] = useState<PerformanceScanResult | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanStatus, setScanStatus] = useState('');
  const [scanUrl, setScanUrl] = useState('');
  const [device, setDevice] = useState<'mobile' | 'desktop'>('desktop');
  const [showScrollNotification, setShowScrollNotification] = useState(false);
  
  // Ref for auto-scrolling to results
  const resultsRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    // Load scan history
    const savedScans = localStorage.getItem('thandev-performance-scans');
    if (savedScans) {
      try {
        const parsedScans = JSON.parse(savedScans).map((scan: any) => ({
          ...scan,
          timestamp: new Date(scan.timestamp)
        }));
        setScans(parsedScans);
      } catch (e) {
        console.error('Error loading performance scan history:', e);
      }
    }
  }, []);

  // Auto-scroll to results when scan completes
  useEffect(() => {
    if (currentScan && currentScan.status === 'completed' && resultsRef.current) {
      // Show notification
      setShowScrollNotification(true);
      
      // Small delay to ensure the results section is rendered
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
          inline: 'nearest'
        });
        
        // Add a subtle highlight effect
        const element = resultsRef.current;
        if (element) {
          element.style.boxShadow = '0 0 20px rgba(59, 130, 246, 0.3)';
          element.style.transition = 'box-shadow 0.5s ease-in-out';
          
          // Remove the highlight after 3 seconds
          setTimeout(() => {
            element.style.boxShadow = '';
          }, 3000);
        }
        
        // Hide notification after scroll
        setTimeout(() => {
          setShowScrollNotification(false);
        }, 2000);
      }, 500);
    }
  }, [currentScan]);

  const startPerformanceScan = async () => {
    if (!scanUrl.trim()) {
      alert('Please enter a URL to scan');
      return;
    }

    const newScan: PerformanceScanResult = {
      id: Date.now().toString(),
      url: scanUrl,
      status: 'scanning',
      timestamp: new Date(),
      score: 0,
      device,
      metrics: {
        firstContentfulPaint: 0,
        largestContentfulPaint: 0,
        firstMeaningfulPaint: 0,
        speedIndex: 0,
        cumulativeLayoutShift: 0,
        totalBlockingTime: 0,
        interactive: 0,
        firstInputDelay: 0,
      },
      opportunities: [],
      diagnostics: [],
      categories: {
        performance: 0,
        accessibility: 0,
        bestPractices: 0,
        seo: 0,
      }
    };

    setCurrentScan(newScan);
    setIsScanning(true);
    setScanProgress(0);
    setScanStatus('Initializing performance scan...');

    try {
      // Send request to FastAPI backend
      const response = await fetch('/api/performance-scan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: scanUrl,
          device: device,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to start performance scan');
      }

      const { jobId } = await response.json();
      console.log('Performance scan started with jobId:', jobId);

      // Poll for results
      const pollInterval = setInterval(async () => {
        try {
          setScanStatus('Analyzing website performance...');
          setScanProgress(20);
          
          const statusResponse = await fetch(`/api/performance-scan?jobId=${jobId}`);
          const statusData = await statusResponse.json();
          
          if (statusData.status === 'running') {
            setScanProgress(40);
            setScanStatus('Measuring Core Web Vitals...');
          } else if (statusData.status === 'completed') {
            clearInterval(pollInterval);
            
            setScanProgress(100);
            setScanStatus('Performance scan completed!');
            
            const completedScan: PerformanceScanResult = {
              ...newScan,
              status: 'completed',
              score: Math.round(statusData.result.categories.performance),
              metrics: statusData.result.metrics,
              opportunities: statusData.result.opportunities,
              diagnostics: statusData.result.diagnostics,
              categories: statusData.result.categories,
              screenshot: statusData.result.screenshot,
            };

            setCurrentScan(completedScan);
            setIsScanning(false);

            // Save to history
            const updatedScans = [completedScan, ...scans];
            setScans(updatedScans);
            localStorage.setItem('thandev-performance-scans', JSON.stringify(updatedScans));
            
            // Show detailed report in the same page
            // No redirect needed - report will be displayed below
          } else if (statusData.status === 'failed') {
            clearInterval(pollInterval);
            setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
            setIsScanning(false);
            setScanStatus('Scan failed. Please try again.');
          }
        } catch (error) {
          console.error('Error polling scan status:', error);
        }
      }, 2000);

      // Timeout after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (isScanning) {
          setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
          setIsScanning(false);
          setScanStatus('Scan timed out. Please try again.');
        }
      }, 300000);

    } catch (error) {
      console.error('Performance scan error:', error);
      setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
      setIsScanning(false);
      setScanStatus('Scan failed. Please try again.');
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 90) return 'bg-green-500';
    if (score >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const formatTime = (ms: number) => {
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const getMetricStatus = (value: number, thresholds: { good: number; poor: number }) => {
    if (value <= thresholds.good) return { status: 'good', color: 'text-green-500' };
    if (value <= thresholds.poor) return { status: 'needs-improvement', color: 'text-yellow-500' };
    return { status: 'poor', color: 'text-red-500' };
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const tabs = [
    { id: 'overview', name: 'Overview' },
    { id: 'metrics', name: 'Core Web Vitals' },
    { id: 'opportunities', name: 'Opportunities' },
    { id: 'diagnostics', name: 'Diagnostics' },
    { id: 'history', name: 'History' }
  ];

  if (!user) {
    return null; // Will redirect to auth
  }

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
        
        {/* Performance Scanner Content */}
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-7xl mx-auto">
            
            {/* Scroll Notification */}
            {showScrollNotification && (
              <div className="fixed top-20 right-6 z-50 animate-in slide-in-from-right-4 duration-300">
                <div className="bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                  </svg>
                  <span className="text-sm font-medium">Scrolling to results...</span>
                </div>
              </div>
            )}
            {/* Header */}
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>Performance Scanner</h1>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Website performance analysis using Google Lighthouse technology</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-green-600">100+</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Performance Checks</div>
                </div>
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-blue-600">Core Web Vitals</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>LCP, FID, CLS</div>
                </div>
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-purple-600">Real-time</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Live Analysis</div>
                </div>
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-orange-600">Detailed</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Optimization Tips</div>
                </div>
              </div>
            </div>

            {/* Performance Scan Interface */}
            <div className="mb-8">
              <div className="relative overflow-hidden rounded-2xl border shadow-xl" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                {/* Background Pattern */}
                <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 via-transparent to-blue-500/5"></div>
                <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-green-500/10 to-transparent rounded-full -translate-y-32 translate-x-32"></div>
                <div className="absolute bottom-0 left-0 w-48 h-48 bg-gradient-to-tr from-blue-500/10 to-transparent rounded-full translate-y-24 -translate-x-24"></div>
                
                <div className="relative z-10 p-8">
                  <div className="flex items-center gap-4 mb-8">
                    <div className="h-12 w-12 rounded-xl flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 100%)' }}>
                      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>Performance Analysis</h2>
                      <p className="text-sm" style={{ color: 'var(--muted)' }}>Comprehensive website performance testing with Core Web Vitals</p>
                    </div>
                  </div>
                
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    <div className="space-y-6">
                      {/* Target URL Input */}
                      <div className="space-y-3">
                        <label className="block text-sm font-semibold" style={{ color: 'var(--fg)' }}>Website URL</label>
                        <div className="relative group">
                          <input
                            type="url"
                            value={scanUrl}
                            onChange={(e) => setScanUrl(e.target.value)}
                            placeholder="https://example.com"
                            className="w-full px-4 py-4 pl-12 border-2 rounded-xl focus:outline-none focus:ring-4 focus:ring-green-500/20 transition-all duration-200 group-hover:border-green-300"
                            style={{
                              borderColor: 'var(--border)',
                              background: 'var(--surface-2)',
                              color: 'var(--fg)'
                            }}
                          />
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <svg className="h-5 w-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                            </svg>
                          </div>
                        </div>
                      </div>

                      {/* Device Selection */}
                      <div className="space-y-3">
                        <label className="block text-sm font-semibold" style={{ color: 'var(--fg)' }}>Device Type</label>
                        <div className="grid grid-cols-2 gap-4">
                          <label className={`relative flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                            device === 'desktop' 
                              ? 'border-green-500 bg-green-500/10' 
                              : 'border-[var(--border)] hover:border-green-300 hover:bg-green-500/5'
                          }`}>
                            <input
                              type="radio"
                              name="device"
                              value="desktop"
                              checked={device === 'desktop'}
                              onChange={(e) => setDevice(e.target.value as 'desktop')}
                              className="sr-only"
                            />
                            <div className={`h-5 w-5 rounded-full border-2 ${
                              device === 'desktop' 
                                ? 'border-green-500 bg-green-500' 
                                : 'border-[var(--muted)]'
                            }`}>
                              {device === 'desktop' && (
                                <div className="h-2 w-2 bg-white rounded-full m-0.5"></div>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 4a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1V8zm8 0a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1h-4a1 1 0 01-1-1V8zm0 4a1 1 0 011-1h4a1 1 0 011 1v2a1 1 0 01-1 1h-4a1 1 0 01-1-1v-2z" clipRule="evenodd" />
                              </svg>
                              <span className="font-medium" style={{ color: 'var(--fg)' }}>Desktop</span>
                            </div>
                          </label>
                          
                          <label className={`relative flex items-center gap-3 p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                            device === 'mobile' 
                              ? 'border-green-500 bg-green-500/10' 
                              : 'border-[var(--border)] hover:border-green-300 hover:bg-green-500/5'
                          }`}>
                            <input
                              type="radio"
                              name="device"
                              value="mobile"
                              checked={device === 'mobile'}
                              onChange={(e) => setDevice(e.target.value as 'mobile')}
                              className="sr-only"
                            />
                            <div className={`h-5 w-5 rounded-full border-2 ${
                              device === 'mobile' 
                                ? 'border-green-500 bg-green-500' 
                                : 'border-[var(--muted)]'
                            }`}>
                              {device === 'mobile' && (
                                <div className="h-2 w-2 bg-white rounded-full m-0.5"></div>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M7 2a2 2 0 00-2 2v12a2 2 0 002 2h6a2 2 0 002-2V4a2 2 0 00-2-2H7zm3 14a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                              </svg>
                              <span className="font-medium" style={{ color: 'var(--fg)' }}>Mobile</span>
                            </div>
                          </label>
                        </div>
                      </div>
                    </div>

                    {/* Scan Button and Estimated Duration */}
                    <div className="mt-4">
                      <button
                        onClick={startPerformanceScan}
                        disabled={isScanning || !scanUrl.trim()}
                        className="w-full px-4 py-6 rounded-xl font-bold text-white transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-2xl transform hover:scale-105 active:scale-95"
                        style={{ 
                          background: 'linear-gradient(135deg, #10b981 0%, #3b82f6 50%, #8b5cf6 100%)',
                          boxShadow: '0 8px 25px rgba(16, 185, 129, 0.4)'
                        }}
                      >
                        {isScanning ? (
                          <div className="flex flex-col items-center justify-center gap-2">
                            <div className="flex items-center gap-2">
                              <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                              <span className="text-base">{scanStatus || 'Analyzing...'}</span>
                            </div>
                            <div className="w-full bg-white/20 rounded-full h-1.5">
                              <div 
                                className="bg-white h-1.5 rounded-full transition-all duration-500 ease-out"
                                style={{ width: `${scanProgress}%` }}
                              ></div>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center justify-center gap-2">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                            <span className="text-base">Start Scan</span>
                          </div>
                        )}
                      </button>
                      
                      {/* Estimated Duration - directly below scan button */}
                      <div className="mt-2 p-4 text-center rounded-lg border-2 border-green-500" style={{ background: 'var(--surface-2)' }}>
                        <div className="flex items-center justify-center gap-2 mb-2">
                          <svg className="w-4 h-4" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Estimated Duration</span>
                        </div>
                        <p className="text-lg font-bold text-green-500">
                          30-60 seconds
                        </p>
                      </div>
                    </div>

                    {/* Analysis Features */}
                    <div className="mt-4 p-4 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                      <div className="flex items-center gap-2 mb-3">
                        <div className="h-5 w-5 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <h3 className="text-base font-semibold" style={{ color: 'var(--fg)' }}>Analysis Features</h3>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Core Web Vitals</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Performance Metrics</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Optimization Opportunities</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-2 h-2 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Accessibility & SEO</span>
                        </div>
                      </div>
                    </div>

                    {/* Scan Statistics */}
                    <div className="mt-6 p-4 rounded-xl border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                      <h4 className="text-base font-semibold mb-3 text-center" style={{ color: 'var(--fg)' }}>Scan Statistics</h4>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="text-center p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="text-xl font-bold text-blue-500">{scans.length}</div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Total Scans</div>
                        </div>
                        <div className="text-center p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="text-xl font-bold text-green-500">
                            {scans.length > 0 ? Math.round(scans.reduce((sum, scan) => sum + scan.score, 0) / scans.length) : 0}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Avg Score</div>
                        </div>
                        <div className="text-center p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="text-xl font-bold text-purple-500">
                            {scans.filter(scan => scan.device === 'mobile').length}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Mobile Scans</div>
                        </div>
                        <div className="text-center p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="text-xl font-bold text-orange-500">
                            {scans.filter(scan => scan.device === 'desktop').length}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Desktop Scans</div>
                        </div>
                      </div>
                    </div>

                    {/* Quick Tips */}
                    <div className="mt-4 p-4 rounded-xl border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                      <h4 className="text-base font-semibold mb-3 text-center" style={{ color: 'var(--fg)' }}>Quick Tips</h4>
                      <div className="space-y-2 text-sm">
                        <div className="p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="font-medium text-green-500 mb-1">💡 Optimize Images</div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Use WebP format and proper sizing</div>
                        </div>
                        <div className="p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="font-medium text-blue-500 mb-1">⚡ Minimize CSS/JS</div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Remove unused code and compress files</div>
                        </div>
                        <div className="p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="font-medium text-purple-500 mb-1">🚀 Enable Caching</div>
                          <div className="text-xs" style={{ color: 'var(--muted)' }}>Set proper cache headers for static assets</div>
                        </div>
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      {/* Performance Scale Indicator */}
                      <div className="p-4 rounded-xl border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                        <h4 className="text-base font-semibold mb-3 text-center" style={{ color: 'var(--fg)' }}>Performance Scale</h4>
                        <div className="relative">
                          <div className="flex justify-between items-center mb-2">
                            <span className="text-xs font-medium text-red-500">Poor (0-49)</span>
                            <span className="text-xs font-medium text-yellow-500">Needs Improvement (50-89)</span>
                            <span className="text-xs font-medium text-green-500">Good (90-100)</span>
                          </div>
                          <div className="relative h-2.5 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
                            <div className="absolute inset-0 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 opacity-80"></div>
                            <div className="absolute inset-0 flex">
                              <div className="w-1/2 h-full border-r border-white/30"></div>
                              <div className="w-1/2 h-full"></div>
                            </div>
                          </div>
                          <div className="flex justify-between mt-1.5 text-xs" style={{ color: 'var(--muted)' }}>
                            <span>0</span>
                            <span>25</span>
                            <span>50</span>
                            <span>75</span>
                            <span>100</span>
                          </div>
                        </div>
                      </div>


                      {/* What We Analyze */}
                      <div className="p-4 rounded-xl border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                        <h4 className="text-base font-semibold mb-3 text-center" style={{ color: 'var(--fg)' }}>What We Analyze</h4>
                        <div className="space-y-2">
                          <div className="flex items-start gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-cyan-500 mt-1.5"></div>
                            <div>
                              <div className="font-medium text-sm" style={{ color: 'var(--fg)' }}>Loading Performance</div>
                              <div className="text-xs" style={{ color: 'var(--muted)' }}>First Contentful Paint, Speed Index</div>
                            </div>
                          </div>
                          <div className="flex items-start gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5"></div>
                            <div>
                              <div className="font-medium text-sm" style={{ color: 'var(--fg)' }}>User Experience</div>
                              <div className="text-xs" style={{ color: 'var(--muted)' }}>Largest Contentful Paint, Layout Shift</div>
                            </div>
                          </div>
                          <div className="flex items-start gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-purple-500 mt-1.5"></div>
                            <div>
                              <div className="font-medium text-sm" style={{ color: 'var(--fg)' }}>Interactivity</div>
                              <div className="text-xs" style={{ color: 'var(--muted)' }}>Time to Interactive, Total Blocking Time</div>
                            </div>
                          </div>
                          <div className="flex items-start gap-2">
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5"></div>
                            <div>
                              <div className="font-medium text-sm" style={{ color: 'var(--fg)' }}>Resource Optimization</div>
                              <div className="text-xs" style={{ color: 'var(--muted)' }}>Image optimization, Code splitting</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Current Scan Results */}
            {currentScan && (
              <div className="mb-8">
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                  {/* Scan Header */}
                  <div className="p-6 border-b" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="h-8 w-8 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                          </div>
                          <h2 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>Performance Analysis</h2>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getScoreColor(currentScan.score)}`}>
                            {currentScan.score >= 90 ? 'EXCELLENT' : currentScan.score >= 50 ? 'NEEDS IMPROVEMENT' : 'POOR'}
                          </span>
                        </div>
                        <p className="text-sm mb-1" style={{ color: 'var(--fg)' }}>{currentScan.url}</p>
                        <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                          <span>📅 {currentScan.timestamp.toLocaleString()}</span>
                          <span>📱 {currentScan.device} scan</span>
                          <span>⚡ Performance Score: {currentScan.score}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-4xl font-bold ${getScoreColor(currentScan.score)}`}>
                          {currentScan.score}
                        </div>
                        <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Performance Score</div>
                        <div className="text-xs" style={{ color: 'var(--muted)' }}>
                          {currentScan.score >= 90 ? 'Excellent' : 
                           currentScan.score >= 50 ? 'Needs Improvement' : 'Poor'}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Tabs */}
                  <div className="border-b" style={{ borderColor: 'var(--border)' }}>
                    <nav className="flex space-x-8 px-6">
                      {tabs.map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`py-4 px-1 border-b-2 font-medium text-sm ${
                            activeTab === tab.id
                              ? 'border-green-500 text-green-600'
                              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                          }`}
                        >
                          {tab.name}
                        </button>
                      ))}
                    </nav>
                  </div>

                  {/* Tab Content */}
                  <div className="p-6">
                    {activeTab === 'overview' && currentScan.status === 'completed' && (
                      <div className="space-y-6">
                        {/* Performance Score Circle */}
                        <div className="flex justify-center">
                          <div className="relative w-32 h-32">
                            <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 100 100">
                              <circle
                                cx="50"
                                cy="50"
                                r="40"
                                stroke="currentColor"
                                strokeWidth="8"
                                fill="none"
                                className="text-gray-200 dark:text-gray-700"
                              />
                              <circle
                                cx="50"
                                cy="50"
                                r="40"
                                stroke="currentColor"
                                strokeWidth="8"
                                fill="none"
                                strokeDasharray={`${2 * Math.PI * 40}`}
                                strokeDashoffset={`${2 * Math.PI * 40 * (1 - currentScan.score / 100)}`}
                                className={getScoreColor(currentScan.score)}
                                strokeLinecap="round"
                              />
                            </svg>
                            <div className="absolute inset-0 flex items-center justify-center">
                              <span className={`text-2xl font-bold ${getScoreColor(currentScan.score)}`}>
                                {currentScan.score}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Core Web Vitals */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                          <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <div className="text-2xl font-bold text-green-600">
                              {formatTime(currentScan.metrics.firstContentfulPaint)}
                            </div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>First Contentful Paint</div>
                          </div>
                          <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <div className="text-2xl font-bold text-blue-600">
                              {formatTime(currentScan.metrics.largestContentfulPaint)}
                            </div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>Largest Contentful Paint</div>
                          </div>
                          <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <div className="text-2xl font-bold text-purple-600">
                              {currentScan.metrics.cumulativeLayoutShift.toFixed(3)}
                            </div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>Cumulative Layout Shift</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'history' && (
                      <div className="space-y-4">
                        {scans.map((scan) => (
                          <div key={scan.id} className="flex items-center justify-between p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                            <div>
                              <div className="font-medium" style={{ color: 'var(--fg)' }}>{scan.url}</div>
                              <div className="text-sm" style={{ color: 'var(--muted)' }}>
                                {scan.timestamp.toLocaleString()} • {scan.device}
                              </div>
                            </div>
                            <div className="text-right">
                              <div className={`text-lg font-bold ${getScoreColor(scan.score)}`}>{scan.score}</div>
                              <div className="text-xs" style={{ color: 'var(--muted)' }}>Score</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Detailed Performance Report */}
            {currentScan && currentScan.status === 'completed' && (
              <div ref={resultsRef} className="mt-12 animate-in slide-in-from-bottom-4 duration-700">
                <div className="text-center mb-8">
                  <h2 className="text-3xl font-bold mb-2 bg-gradient-to-r from-cyan-400 via-blue-500 to-purple-600 bg-clip-text text-transparent">
                    Performance Analysis Report
                  </h2>
                  <p className="text-lg" style={{ color: 'var(--muted)' }}>
                    Comprehensive insights powered by Google Lighthouse
                  </p>
                </div>

                {/* Main Performance Score */}
                <div className="relative mb-12">
                  <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-purple-500/20 rounded-3xl blur-xl"></div>
                  <div className="relative p-8 rounded-3xl border-2 border-cyan-500/30" style={{ background: 'linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%)' }}>
                    <div className="text-center">
                      <div className="relative inline-block">
                        <div className="w-48 h-48 mx-auto relative">
                          <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                            <circle
                              cx="50"
                              cy="50"
                              r="40"
                              fill="none"
                              stroke="var(--border)"
                              strokeWidth="8"
                            />
                            <circle
                              cx="50"
                              cy="50"
                              r="40"
                              fill="none"
                              stroke="url(#gradient)"
                              strokeWidth="8"
                              strokeLinecap="round"
                              strokeDasharray={`${2 * Math.PI * 40}`}
                              strokeDashoffset={`${2 * Math.PI * 40 * (1 - currentScan.score / 100)}`}
                              className="transition-all duration-2000 ease-out"
                            />
                            <defs>
                              <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" stopColor="#06b6d4" />
                                <stop offset="50%" stopColor="#3b82f6" />
                                <stop offset="100%" stopColor="#8b5cf6" />
                              </linearGradient>
                            </defs>
                          </svg>
                          <div className="absolute inset-0 flex items-center justify-center">
                            <div className="text-center">
                              <div className={`text-4xl font-bold ${getScoreColor(currentScan.score)}`}>
                                {currentScan.score}
                              </div>
                              <div className="text-sm" style={{ color: 'var(--muted)' }}>Performance</div>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className="mt-6">
                        <h3 className="text-xl font-semibold mb-2" style={{ color: 'var(--fg)' }}>{currentScan.url}</h3>
                        <p className="text-sm" style={{ color: 'var(--muted)' }}>
                          {currentScan.timestamp.toLocaleString()} • {currentScan.device} • Job ID: {currentScan.id}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Category Scores Grid */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
                  {[
                    { key: 'performance', label: 'Performance', icon: '⚡' },
                    { key: 'accessibility', label: 'Accessibility', icon: '♿' },
                    { key: 'bestPractices', label: 'Best Practices', icon: '✅' },
                    { key: 'seo', label: 'SEO', icon: '🔍' }
                  ].map((category) => (
                    <div key={category.key} className="group relative">
                      <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-2xl blur-lg group-hover:blur-xl transition-all duration-300"></div>
                      <div className="relative p-6 rounded-2xl border border-cyan-500/20 hover:border-cyan-500/40 transition-all duration-300" style={{ background: 'var(--surface-2)' }}>
                        <div className="text-center">
                          <div className="text-3xl mb-2">{category.icon}</div>
                          <div className={`text-2xl font-bold mb-1 ${getScoreColor(currentScan.categories?.[category.key] || 0)}`}>
                            {currentScan.categories?.[category.key] || 0}
                          </div>
                          <div className="text-sm" style={{ color: 'var(--muted)' }}>{category.label}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>


                {/* Opportunities */}
                {currentScan.opportunities && currentScan.opportunities.length > 0 && (
                  <div className="mb-12">
                    <h3 className="text-2xl font-bold mb-6 text-center bg-gradient-to-r from-orange-400 to-red-500 bg-clip-text text-transparent">
                      Optimization Opportunities
                    </h3>
                    <div className="space-y-4">
                      {currentScan.opportunities.slice(0, 5).map((opportunity, index) => (
                        <div key={index} className="group relative">
                          <div className="absolute inset-0 bg-gradient-to-r from-orange-500/10 to-red-500/10 rounded-xl blur-lg group-hover:blur-xl transition-all duration-300"></div>
                          <div className="relative p-6 rounded-xl border border-orange-500/20 hover:border-orange-500/40 transition-all duration-300" style={{ background: 'var(--surface-2)' }}>
                            <div className="flex items-start justify-between mb-4">
                              <div className="flex-1">
                                <h4 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>{opportunity.title}</h4>
                                <p className="text-sm mb-3" style={{ color: 'var(--muted)' }}>{opportunity.description}</p>
                                {opportunity.displayValue && (
                                  <div className="text-sm font-medium text-orange-400">{opportunity.displayValue}</div>
                                )}
                              </div>
                              <div className={`text-2xl font-bold ${getScoreColor(Math.round(opportunity.score * 100))}`}>
                                {Math.round(opportunity.score * 100)}
                              </div>
                            </div>
                            {opportunity.details?.items && opportunity.details.items.length > 0 && (
                              <div className="mt-4">
                                <h5 className="font-medium mb-2 text-sm" style={{ color: 'var(--fg)' }}>Affected Resources:</h5>
                                <div className="space-y-2">
                                  {opportunity.details.items.slice(0, 3).map((item, itemIndex) => (
                                    <div key={itemIndex} className="p-3 rounded border text-sm" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                                      {item.node?.snippet && (
                                        <div className="font-mono text-xs mb-1" style={{ color: 'var(--muted)' }}>
                                          {item.node.snippet}
                                        </div>
                                      )}
                                      {item.url && (
                                        <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>
                                          URL: {item.url}
                                        </div>
                                      )}
                                      {item.wastedBytes && (
                                        <div className="text-xs" style={{ color: 'var(--muted)' }}>
                                          Wasted: {formatBytes(item.wastedBytes)}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Diagnostics */}
                {currentScan.diagnostics && currentScan.diagnostics.length > 0 && (
                  <div className="mb-12">
                    <h3 className="text-2xl font-bold mb-6 text-center bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
                      Diagnostic Information
                    </h3>
                    <div className="space-y-4">
                      {currentScan.diagnostics.slice(0, 5).map((diagnostic, index) => (
                        <div key={index} className="group relative">
                          <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-xl blur-lg group-hover:blur-xl transition-all duration-300"></div>
                          <div className="relative p-6 rounded-xl border border-purple-500/20 hover:border-purple-500/40 transition-all duration-300" style={{ background: 'var(--surface-2)' }}>
                            <div className="flex items-start justify-between mb-4">
                              <div className="flex-1">
                                <h4 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>{diagnostic.title}</h4>
                                <p className="text-sm mb-3" style={{ color: 'var(--muted)' }}>{diagnostic.description}</p>
                                {diagnostic.displayValue && (
                                  <div className="text-sm font-medium text-purple-400">{diagnostic.displayValue}</div>
                                )}
                              </div>
                              <div className={`text-2xl font-bold ${getScoreColor(Math.round(diagnostic.score * 100))}`}>
                                {Math.round(diagnostic.score * 100)}
                              </div>
                            </div>
                            {diagnostic.details?.items && diagnostic.details.items.length > 0 && (
                              <div className="mt-4">
                                <h5 className="font-medium mb-2 text-sm" style={{ color: 'var(--fg)' }}>Details:</h5>
                                <div className="space-y-2">
                                  {diagnostic.details.items.slice(0, 3).map((item, itemIndex) => (
                                    <div key={itemIndex} className="p-3 rounded border text-sm" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                                      {item.node?.snippet && (
                                        <div className="font-mono text-xs mb-1" style={{ color: 'var(--muted)' }}>
                                          {item.node.snippet}
                                        </div>
                                      )}
                                      {item.url && (
                                        <div className="text-xs mb-1" style={{ color: 'var(--muted)' }}>
                                          URL: {item.url}
                                        </div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
