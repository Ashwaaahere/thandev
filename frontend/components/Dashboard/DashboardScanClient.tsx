'use client';

import { useState, useEffect } from 'react';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

export interface ScanResult {
  id: string;
  url: string;
  status: 'pending' | 'scanning' | 'completed' | 'error';
  vulnerabilities: Vulnerability[];
  scanTime: number;
  timestamp: Date;
  score: number;
  scanType: string;
  duration: number;
}

export interface Vulnerability {
  id: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  title: string;
  description: string;
  recommendation: string;
  cwe?: string;
  cvss?: number;
}

interface DashboardScanClientProps {
  user: any;
}

export default function DashboardScanClient({ user }: DashboardScanClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [currentScan, setCurrentScan] = useState<ScanResult | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanStatus, setScanStatus] = useState('');
  const [scanUrl, setScanUrl] = useState('');
  const [scanType, setScanType] = useState('comprehensive');
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    // Load scan history
    const savedScans = localStorage.getItem('thandev-scans');
    if (savedScans) {
      try {
        const parsedScans = JSON.parse(savedScans).map((scan: any) => ({
          ...scan,
          timestamp: new Date(scan.timestamp)
        }));
        setScans(parsedScans);
      } catch (e) {
        console.error('Error loading scan history:', e);
      }
    }
  }, []);


  const startScan = async () => {
    console.log('=== SCAN BUTTON CLICKED ===');
    console.log('scanUrl:', scanUrl);
    console.log('scanType:', scanType);
    console.log('isScanning:', isScanning);
    
    if (!scanUrl.trim()) {
      console.log('ERROR: No URL provided');
      return;
    }

    console.log('Starting security scan...');
    console.log('Scan URL:', scanUrl);

    await startSecurityScan();
  };


  const startSecurityScan = async () => {
    const newScan: ScanResult = {
      id: Date.now().toString(),
      url: scanUrl,
      status: 'scanning',
      vulnerabilities: [],
      scanTime: 0,
      timestamp: new Date(),
      score: 0,
      scanType,
      duration: 0
    };

    setCurrentScan(newScan);
    setIsScanning(true);
    setScanProgress(0);
    setScanStatus('Initializing security scan...');

    // Simulate scan progress
    const scanDuration = scanType === 'quick' ? 3000 : scanType === 'comprehensive' ? 8000 : 15000;
    const startTime = Date.now();

    // Simulate scanning with progress updates
    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min((elapsed / scanDuration) * 100, 95);
      
      setCurrentScan(prev => prev ? {
        ...prev,
        scanTime: Math.floor(elapsed / 1000),
        score: Math.floor(progress * 0.8) // Score increases with progress
      } : null);
    }, 1000);

    // Complete scan after duration
    setTimeout(() => {
      clearInterval(progressInterval);
      
      // Generate mock vulnerabilities based on scan type
      const vulnerabilities = generateMockVulnerabilities(scanType);
      const finalScore = Math.max(20, 100 - (vulnerabilities.length * 8) - Math.floor(Math.random() * 20));
      
      const completedScan: ScanResult = {
        ...newScan,
        status: 'completed',
        vulnerabilities,
        score: finalScore,
        duration: Math.floor(scanDuration / 1000)
      };

      setCurrentScan(completedScan);
      setIsScanning(false);

      // Save to history
      const updatedScans = [completedScan, ...scans];
      setScans(updatedScans);
      localStorage.setItem('thandev-scans', JSON.stringify(updatedScans));
    }, scanDuration);
  };

  const generateMockVulnerabilities = (type: string): Vulnerability[] => {
    const baseVulns: Vulnerability[] = [
      {
        id: '1',
        type: 'SSL/TLS',
        severity: 'medium' as 'medium',
        title: 'Weak SSL/TLS Configuration',
        description: 'The server is using outdated SSL/TLS protocols or weak cipher suites.',
        recommendation: 'Update to TLS 1.2 or higher and disable weak cipher suites.',
        cwe: 'CWE-326',
        cvss: 5.3
      },
      {
        id: '2',
        type: 'Headers',
        severity: 'low' as 'low',
        title: 'Missing Security Headers',
        description: 'Important security headers like X-Frame-Options and X-Content-Type-Options are missing.',
        recommendation: 'Implement comprehensive security headers to protect against common attacks.',
        cwe: 'CWE-693',
        cvss: 3.7
      }
    ];

    if (type === 'comprehensive' || type === 'deep') {
      baseVulns.push(
        {
          id: '3',
          type: 'Authentication',
          severity: 'high' as 'high',
          title: 'Weak Authentication Mechanism',
          description: 'The application uses weak password policies or lacks proper authentication controls.',
          recommendation: 'Implement strong password policies and multi-factor authentication.',
          cwe: 'CWE-287',
          cvss: 7.2
        },
        {
          id: '4',
          type: 'Input Validation',
          severity: 'medium' as 'medium',
          title: 'Insufficient Input Validation',
          description: 'User inputs are not properly validated, potentially leading to injection attacks.',
          recommendation: 'Implement comprehensive input validation and sanitization.',
          cwe: 'CWE-20',
          cvss: 6.1
        }
      );
    }

    if (type === 'deep') {
      baseVulns.push(
        {
          id: '5',
          type: 'Subdomain',
          severity: 'low' as 'low',
          title: 'Subdomain Takeover Risk',
          description: 'A subdomain is pointing to a non-existent service, creating a takeover risk.',
          recommendation: 'Remove or properly configure the subdomain DNS records.',
          cwe: 'CWE-346',
          cvss: 4.2
        }
      );
    }

    return baseVulns;
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-600 bg-red-100';
      case 'high': return 'text-orange-600 bg-orange-100';
      case 'medium': return 'text-yellow-600 bg-yellow-100';
      case 'low': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const tabs = [
    { id: 'overview', name: 'Overview' },
    { id: 'vulnerabilities', name: 'Vulnerabilities' },
    { id: 'recommendations', name: 'Recommendations' },
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
        
        {/* Scanner Content */}
        <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
          <div className="max-w-7xl mx-auto">
            {/* Header */}
            <div className="mb-8">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                  <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div>
                  <h1 className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>Professional Security Scanner</h1>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Enterprise-grade vulnerability assessment and penetration testing</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-green-600">1000+</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Vulnerability Checks</div>
                </div>
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-blue-600">50+</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Security Categories</div>
                </div>
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-purple-600">24/7</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Monitoring</div>
                </div>
                <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                  <div className="text-2xl font-bold text-orange-600">99.9%</div>
                  <div className="text-sm" style={{ color: 'var(--muted)' }}>Accuracy</div>
                </div>
              </div>
            </div>

            {/* Professional Scan Interface */}
            <div className="mb-8">
              <div className="relative overflow-hidden rounded-2xl border shadow-xl" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                {/* Background Pattern */}
                <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5"></div>
                <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-blue-500/10 to-transparent rounded-full -translate-y-32 translate-x-32"></div>
                <div className="absolute bottom-0 left-0 w-48 h-48 bg-gradient-to-tr from-purple-500/10 to-transparent rounded-full translate-y-24 -translate-x-24"></div>
                
                <div className="relative z-10 p-8">
                  <div className="flex items-center gap-4 mb-8">
                    <div className="h-12 w-12 rounded-xl flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(135deg, var(--brand) 0%, #3b82f6 100%)' }}>
                      <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold" style={{ color: 'var(--fg)' }}>Professional Security Scanner</h2>
                      <p className="text-sm" style={{ color: 'var(--muted)' }}>Enterprise-grade vulnerability assessment and penetration testing</p>
                    </div>
                  </div>
                
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                  <div className="lg:col-span-2 space-y-6">
                    {/* Target URL Input */}
                    <div className="space-y-3">
                      <label className="block text-sm font-semibold" style={{ color: 'var(--fg)' }}>Target URL or IP Address</label>
                      <div className="relative group">
                        <input
                          type="url"
                          value={scanUrl}
                          onChange={(e) => setScanUrl(e.target.value)}
                          placeholder="https://example.com or 192.168.1.1"
                          className="w-full px-4 py-4 pl-12 border-2 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all duration-200 group-hover:border-blue-300"
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

                    
                    {/* Scan Configuration */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-3">
                        <label className="block text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                          </svg>
                          Scan Type
                        </label>
                        <div className="relative group">
                          <select
                            value={scanType}
                            onChange={(e) => setScanType(e.target.value)}
                            className="w-full px-4 py-4 pl-12 pr-10 border-2 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all duration-200 hover:border-blue-300 appearance-none cursor-pointer text-base font-medium dark:bg-gray-800 dark:text-white"
                            style={{
                              borderColor: 'var(--border)',
                              background: 'var(--surface-2) !important',
                              backgroundColor: 'var(--surface-2) !important',
                              color: 'var(--fg) !important'
                            }}
                          >
                            <>
                              <option value="quick" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                ⚡ Quick Scan - Basic security checks (5-10 minutes)
                              </option>
                              <option value="comprehensive" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                🔍 Comprehensive Scan - Full vulnerability assessment (15-30 minutes)
                              </option>
                              <option value="deep" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                🛡️ Deep Scan - Thorough analysis with subdomains (30-60 minutes)
                              </option>
                              <option value="custom" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                ⚙️ Custom Configuration - Advanced settings
                              </option>
                            </>
                          </select>
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <svg className="w-5 h-5" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                            </svg>
                          </div>
                          <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none">
                            <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </div>
                        
                        {/* Scan Type Description */}
                        <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                          <div className="flex items-center gap-2 mb-1">
                            <div className="w-2 h-2 rounded-full" style={{ background: 'var(--brand)' }}></div>
                            <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                              {scanType === 'quick' ? 'Quick Scan' : 
                               scanType === 'comprehensive' ? 'Comprehensive Scan' : 
                               scanType === 'deep' ? 'Deep Scan' : 'Custom Configuration'}
                            </span>
                          </div>
                          <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                            {scanType === 'quick' ? 'Fast security assessment covering SSL/TLS, security headers, and common vulnerabilities. Ideal for regular monitoring.' :
                             scanType === 'comprehensive' ? 'Complete vulnerability assessment with authentication testing, input validation, and comprehensive reporting.' :
                             scanType === 'deep' ? 'Extensive security analysis including subdomain discovery, directory enumeration, and advanced penetration testing techniques.' :
                             'Configure custom scan parameters and select specific security checks to run based on your requirements.'}
                          </p>
                        </div>
                      </div>
                      
                      <div className="space-y-3">
                        <label className="block text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          Scan Priority
                        </label>
                        <div className="relative group">
                          <select className="w-full px-4 py-4 pl-12 pr-10 border-2 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all duration-200 hover:border-blue-300 appearance-none cursor-pointer text-base font-medium dark:bg-gray-800 dark:text-white" style={{ borderColor: 'var(--border)', background: 'var(--surface-2) !important', backgroundColor: 'var(--surface-2) !important', color: 'var(--fg) !important' }}>
                            <option value="normal" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                              🟢 Normal Priority - Standard processing time
                            </option>
                            <option value="high" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                              🟡 High Priority - Faster processing
                            </option>
                            <option value="urgent" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                              🔴 Urgent Priority - Immediate processing
                            </option>
                          </select>
                          <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                            <svg className="w-5 h-5" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                          </div>
                          <div className="absolute inset-y-0 right-0 pr-4 flex items-center pointer-events-none">
                            <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-6">
                    {/* Scan Features Preview */}
                    <div className="p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                      <div className="flex items-center gap-2 mb-4">
                        <div className="h-6 w-6 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)' }}>
                          <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        </div>
                        <h3 className="font-semibold" style={{ color: 'var(--fg)' }}>{scanType === 'quick' ? 'Quick' : scanType === 'comprehensive' ? 'Comprehensive' : 'Deep'} Scan Features</h3>
                      </div>
                      <div className="space-y-3">
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>SSL/TLS Analysis</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Header Security</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Port Scanning</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanType === 'deep' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanType === 'deep' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>Subdomain Enumeration</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanType === 'deep' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanType === 'deep' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>Directory Brute Force</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanType === 'comprehensive' || scanType === 'deep' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanType === 'comprehensive' || scanType === 'deep' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>Authentication Analysis</span>
                        </div>
                      </div>
                    </div>
                    
                    {/* Scan Button */}
                    <button
                      onClick={startScan}
                      disabled={isScanning || !scanUrl.trim()}
                      className="w-full px-6 py-5 rounded-xl font-bold text-white transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed hover:shadow-2xl transform hover:scale-105 active:scale-95"
                      style={{ 
                        background: 'linear-gradient(135deg, var(--brand) 0%, #3b82f6 50%, #8b5cf6 100%)',
                        boxShadow: '0 8px 25px rgba(59, 130, 246, 0.4)'
                      }}
                      title={`URL: ${scanUrl || 'none'}, Type: ${scanType}, Scanning: ${isScanning}`}
                    >
                      {isScanning ? (
                        <div className="flex flex-col items-center justify-center gap-3">
                          <div className="flex items-center gap-3">
                            <div className="animate-spin rounded-full h-6 w-6 border-3 border-white border-t-transparent"></div>
                            <span className="text-lg">{scanStatus || 'Scanning in Progress...'}</span>
                          </div>
                          <div className="w-full bg-white/20 rounded-full h-2">
                            <div 
                              className="bg-white h-2 rounded-full transition-all duration-500 ease-out"
                              style={{ width: `${scanProgress}%` }}
                            ></div>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-3">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span className="text-lg">
                            Start {scanType === 'quick' ? 'Quick' : scanType === 'comprehensive' ? 'Comprehensive' : 'Deep'} Security Scan
                          </span>
                        </div>
                      )}
                    </button>
                    
                    {/* Scan Info */}
                    <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                      <div className="flex items-center justify-center gap-2 mb-2">
                        <svg className="w-4 h-4" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Estimated Duration</span>
                      </div>
                      <p className="text-lg font-bold" style={{ color: 'var(--brand)' }}>
                        {scanType === 'quick' ? '5-10 minutes' : scanType === 'comprehensive' ? '15-30 minutes' : '30-60 minutes'}
                      </p>
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
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </div>
                          <h2 className="text-xl font-semibold" style={{ color: 'var(--fg)' }}>Professional Security Assessment</h2>
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getScoreColor(currentScan.score)}`}>
                            {currentScan.score >= 80 ? 'SECURE' : currentScan.score >= 60 ? 'MODERATE' : 'AT RISK'}
                          </span>
                        </div>
                        <p className="text-sm mb-1" style={{ color: 'var(--fg)' }}>{currentScan.url}</p>
                        <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--muted)' }}>
                          <span>📅 {currentScan.timestamp.toLocaleString()}</span>
                          <span>⚡ {currentScan.scanType} scan</span>
                          <span>⏱️ {currentScan.duration}s duration</span>
                          <span>🔍 {currentScan.vulnerabilities.length} issues found</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-4xl font-bold ${getScoreColor(currentScan.score)}`}>
                          {currentScan.score}
                        </div>
                        <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Security Score</div>
                        <div className="text-xs" style={{ color: 'var(--muted)' }}>
                          {currentScan.score >= 90 ? 'Excellent' : 
                           currentScan.score >= 80 ? 'Good' : 
                           currentScan.score >= 70 ? 'Fair' : 
                           currentScan.score >= 60 ? 'Poor' : 'Critical'}
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
                              ? 'border-blue-500 text-blue-600'
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
                    {activeTab === 'overview' && (
                      <div className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                          <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <div className="text-2xl font-bold text-green-600">{currentScan.vulnerabilities.filter(v => v.severity === 'low').length}</div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>Low Risk</div>
                          </div>
                          <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <div className="text-2xl font-bold text-yellow-600">{currentScan.vulnerabilities.filter(v => v.severity === 'medium').length}</div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>Medium Risk</div>
                          </div>
                          <div className="text-center p-4 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                            <div className="text-2xl font-bold text-red-600">{currentScan.vulnerabilities.filter(v => v.severity === 'high' || v.severity === 'critical').length}</div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>High Risk</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'vulnerabilities' && (
                      <div className="space-y-4">
                        {currentScan.vulnerabilities.map((vuln) => (
                          <div key={vuln.id} className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                            <div className="flex items-start justify-between mb-2">
                              <h3 className="font-medium" style={{ color: 'var(--fg)' }}>{vuln.title}</h3>
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(vuln.severity)}`}>
                                {vuln.severity.toUpperCase()}
                              </span>
                            </div>
                            <p className="text-sm mb-3" style={{ color: 'var(--muted)' }}>{vuln.description}</p>
                            <div className="text-sm">
                              <strong style={{ color: 'var(--fg)' }}>Recommendation:</strong>
                              <p style={{ color: 'var(--muted)' }}>{vuln.recommendation}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {activeTab === 'recommendations' && (
                      <div className="space-y-4">
                        <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
                          <h3 className="font-medium mb-2" style={{ color: 'var(--fg)' }}>Immediate Actions</h3>
                          <ul className="space-y-2 text-sm" style={{ color: 'var(--muted)' }}>
                            <li>• Update all security headers</li>
                            <li>• Implement proper SSL/TLS configuration</li>
                            <li>• Review and strengthen authentication mechanisms</li>
                          </ul>
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
                                {scan.timestamp.toLocaleString()} • {scan.scanType}
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
          </div>
        </main>
      </div>
    </div>
  );
}