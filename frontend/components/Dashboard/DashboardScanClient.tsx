'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Session } from 'next-auth';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';
import { toast } from '../Toast';
import { thandevFetchJSON } from '@/lib/thandevApi';
import { formatDateTime } from '@/lib/formatDate';

// API base URL
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

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
  session: Session | null;
}

export default function DashboardScanClient({ user, session }: DashboardScanClientProps) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [currentScan, setCurrentScan] = useState<ScanResult | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  const [scanStatus, setScanStatus] = useState('');
  const [scanUrl, setScanUrl] = useState('');
  const [scanLevel, setScanLevel] = useState('level1');
  const [activeTab, setActiveTab] = useState('overview');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Load scan history
    const savedScans = localStorage.getItem('thandev-security-scans');
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


  // Map frontend level0/level1/level2 to backend basic/pro/advanced
  const mapScanLevel = (level: string): 'basic' | 'pro' | 'advanced' => {
    switch (level) {
      case 'level0':
        return 'basic';
      case 'level1':
        return 'pro';
      case 'level2':
        return 'advanced';
      default:
        return 'basic';
    }
  };

  const startScan = async () => {
    if (!scanUrl.trim()) {
      setError('Please enter a target URL');
      return;
    }

    setIsScanning(true);
    setError(null);
    setScanStatus('Starting scan...');

    try {
      if (!session) {
        throw new Error('Session required. Please log in again.');
      }

      const mappedLevel = mapScanLevel(scanLevel);
      
      let data: { project_id: string; scan_id: string };
      try {
        data = await thandevFetchJSON<{ project_id: string; scan_id: string }>(
          '/api/scans/quick',
          session,
          {
            method: 'POST',
            body: JSON.stringify({
              target_url: scanUrl.trim(),
              scan_level: mappedLevel,
            }),
          }
        );
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Failed to start scan';
        console.error('Scan creation error:', error);
        
        // Check if it's a structured error from backend
        let displayMessage = errorMessage;
        if (errorMessage.includes('DB_COMMIT_FAILED') || errorMessage.includes('database')) {
          displayMessage = 'Database error: Failed to create scan. Please try again or contact support if the issue persists.';
        } else if (errorMessage.includes('LIMIT_EXCEEDED') || errorMessage.includes('limit')) {
          displayMessage = errorMessage; // Show the limit error as-is
        } else if (errorMessage.includes('403') || errorMessage.includes('Forbidden')) {
          displayMessage = errorMessage; // Show permission errors as-is
        }
        
        alert(displayMessage);
        return;
      }
      
      // Redirect to scan report page
      router.push(`/projects/${data.project_id}/scans/${data.scan_id}`);
    } catch (e) {
      console.error('Error starting scan:', e);
      // Safely extract error message - never show [object Object]
      let errorMessage = 'Failed to start scan';
      if (e instanceof Error) {
        errorMessage = e.message;
      } else if (typeof e === 'string') {
        errorMessage = e;
      } else if (e && typeof e === 'object') {
        // Handle structured error response
        if (e.message && typeof e.message === 'string') {
          errorMessage = e.message;
        } else if (e.detail) {
          if (typeof e.detail === 'string') {
            errorMessage = e.detail;
          } else if (typeof e.detail === 'object' && e.detail.message) {
            errorMessage = e.detail.message;
          } else {
            errorMessage = JSON.stringify(e.detail);
          }
        } else {
          errorMessage = JSON.stringify(e);
        }
      }
      setError(errorMessage);
      setScanStatus('');
      toast.error(errorMessage);
    } finally {
      setIsScanning(false);
    }
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
      scanType: scanLevel,
      duration: 0
    };

    setCurrentScan(newScan);
    setIsScanning(true);
    setScanProgress(0);
    setScanStatus('Initializing security scan...');

    try {
      // Call the security scan API
      const response = await fetch('/api/security-scan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: scanUrl,
          tier: scanLevel,
          user_id: 'anonymous'
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || errorData.details || 'Failed to start scan');
      }

      const data = await response.json();
      console.log('Scan start response:', data);
      
      // Backend returns jobId directly, not wrapped in success field
      if (!data.jobId) {
        throw new Error(data.error || data.message || 'Failed to start scan - no jobId returned');
      }
      
      const jobId = data.jobId;
      
      setScanStatus('Scan started, monitoring progress...');
      setScanProgress(10);

      // Poll for scan completion
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await fetch(`/api/security-scan?jobId=${jobId}`);
          
          if (!statusResponse.ok) {
            throw new Error('Failed to get scan status');
          }

          const statusData = await statusResponse.json();
          console.log('Scan status response:', statusData);
          
          if (statusData.success && statusData.status === 'completed') {
            clearInterval(pollInterval);
            
            // Process the scan results
            const result = statusData.result;
            const vulnerabilities = result?.vulnerabilities || [];
            
            // Calculate security score based on vulnerabilities
            let securityScore = 100; // Start with perfect score
            if (vulnerabilities.length > 0) {
              const severityWeights = { critical: 25, high: 15, medium: 10, low: 5, info: 2 };
              vulnerabilities.forEach((vuln: any) => {
                securityScore -= severityWeights[vuln.severity] || 0;
              });
              securityScore = Math.max(0, securityScore); // Don't go below 0
            }
            
            const completedScan: ScanResult = {
              ...newScan,
              id: jobId,
              status: 'completed',
              vulnerabilities: vulnerabilities.map((vuln: any, index: number) => ({
                id: vuln.id || `vuln-${index}`,
                type: vuln.type || 'Unknown',
                severity: vuln.severity || 'info',
                title: vuln.title || vuln.name || 'Security Issue',
                description: vuln.description || 'No description available',
                recommendation: vuln.recommendation || vuln.remediation || 'No recommendation available',
                cwe: vuln.cwe,
                cvss: vuln.cvss,
                port: vuln.port,
                service: vuln.service
              })),
              score: securityScore,
              duration: Math.floor((Date.now() - newScan.timestamp.getTime()) / 1000)
            };

            setCurrentScan(completedScan);
            setIsScanning(false);
            setScanProgress(100);
            setScanStatus('Scan completed successfully');
            toast.success('Security scan completed successfully!');

            // Save to history
            const updatedScans = [completedScan, ...scans];
            setScans(updatedScans);
            localStorage.setItem('thandev-security-scans', JSON.stringify(updatedScans));
            
          } else if (statusData.status === 'error') {
            clearInterval(pollInterval);
            setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
            setIsScanning(false);
            setScanStatus('Scan failed');
            toast.error('Scan failed. Please try again.');
          } else if (statusData.status === 'running' || statusData.status === 'queued') {
            // Update progress for running/queued scans
            const progress = statusData.status === 'running' ? 50 : 25;
            setScanProgress(progress);
            setScanStatus(`Scan ${statusData.status}...`);
            // Continue polling - don't clear interval
          } else {
            // Unknown status - log and continue
            console.log('Unknown scan status:', statusData.status);
            setScanStatus(`Scan ${statusData.status || 'processing'}...`);
          }
          
        } catch (error) {
          console.error('Error polling scan status:', error);
          clearInterval(pollInterval);
          setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
          setIsScanning(false);
          setScanStatus('Scan failed');
        }
      }, 5000); // Poll every 5 seconds

      // Set a timeout to prevent infinite polling
      setTimeout(() => {
        clearInterval(pollInterval);
        if (isScanning) {
          setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
          setIsScanning(false);
          setScanStatus('Scan timed out');
        }
      }, 10 * 60 * 1000); // 10 minute timeout

    } catch (error) {
      console.error('Scan error:', error);
      setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
      setIsScanning(false);
      setScanStatus('Failed to start scan');
      toast.error(`Failed to start scan: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
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
                          onChange={(e) => {
                            setScanUrl(e.target.value);
                            setError(null); // Clear error when user types
                          }}
                          placeholder="https://example.com or 192.168.1.1"
                          className="w-full px-4 py-4 pl-12 border-2 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all duration-200 group-hover:border-blue-300"
                          style={{
                            borderColor: error ? '#ef4444' : 'var(--border)',
                            background: 'var(--surface-2)',
                            color: 'var(--fg)'
                          }}
                          disabled={isScanning}
                        />
                        <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                          <svg className="h-5 w-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                          </svg>
                        </div>
                      </div>
                      {error && (
                        <div className="p-3 rounded-lg border border-red-500/50 bg-red-500/10">
                          <p className="text-sm text-red-400">{error}</p>
                        </div>
                      )}
                    </div>

                    
                    {/* Scan Configuration */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-3">
                        <label className="block text-sm font-semibold flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                          </svg>
                          Scan Level
                          <div className="group relative">
                            <svg className="w-4 h-4 text-gray-400 cursor-help" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 whitespace-nowrap z-10">
                              Choose the appropriate scan level based on your needs
                            </div>
                          </div>
                        </label>
                        <div className="relative group">
                          <select
                            value={scanLevel}
                            onChange={(e) => setScanLevel(e.target.value)}
                            className="w-full px-4 py-4 pl-12 pr-10 border-2 rounded-xl focus:outline-none focus:ring-4 focus:ring-blue-500/20 transition-all duration-200 hover:border-blue-300 appearance-none cursor-pointer text-base font-medium dark:bg-gray-800 dark:text-white"
                            style={{
                              borderColor: 'var(--border)',
                              background: 'var(--surface-2) !important',
                              backgroundColor: 'var(--surface-2) !important',
                              color: 'var(--fg) !important'
                            }}
                          >
                            <>
                              <option value="level0" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                Level 0 — Surface (Quick) - 3-8 minutes
                              </option>
                              <option value="level1" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                Level 1 — Discovery (Buzz) - 10-25 minutes
                              </option>
                              <option value="level2" className="py-3 text-base font-medium" style={{ background: 'var(--surface-2)', color: 'var(--fg)' }}>
                                Level 2 — Active (Non-destructive) - 20-45 minutes
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
                        
                        {/* Scan Level Description */}
                        <div className="p-3 rounded-lg" style={{ background: 'var(--surface-2)' }}>
                          <div className="flex items-center gap-2 mb-1">
                            <div className="w-2 h-2 rounded-full" style={{ background: 'var(--brand)' }}></div>
                            <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>
                              {scanLevel === 'level0' ? 'Level 0 — Surface (Quick)' : 
                               scanLevel === 'level1' ? 'Level 1 — Discovery (Buzz)' : 
                               'Level 2 — Active (Non-destructive)'}
                            </span>
                          </div>
                          <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                            {scanLevel === 'level0' ? 'Very fast, low-noise footprinting and tech checks. Tools: nuclei (info, technologies), sslscan/sslyze, nmap (--top-ports 100 -sV -Pn).' :
                             scanLevel === 'level1' ? 'Broaden surface, find hidden endpoints and subdomains. Everything in Level 0 plus: subfinder/amass, crt.sh lookups, ffuf/gobuster, nuclei medium templates.' :
                             'More aggressive detection (non-exploitative) and CVE checks. Everything in Level 1 plus: nuclei CVE templates, nikto, nmap with NSE scripts.'}
                          </p>
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
                        <h3 className="font-semibold" style={{ color: 'var(--fg)' }}>{scanLevel === 'level0' ? 'Level 0' : scanLevel === 'level1' ? 'Level 1' : 'Level 2'} Scan Features</h3>
                      </div>
                      <div className="space-y-3">
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>SSL/TLS Analysis</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Technology Detection</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className="w-3 h-3 rounded-full bg-green-500 shadow-sm"></div>
                          <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Port Scanning</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanLevel === 'level1' || scanLevel === 'level2' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanLevel === 'level1' || scanLevel === 'level2' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>Subdomain Enumeration</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanLevel === 'level1' || scanLevel === 'level2' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanLevel === 'level1' || scanLevel === 'level2' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>Directory Discovery</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanLevel === 'level2' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanLevel === 'level2' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>CVE Scanning</span>
                        </div>
                        <div className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--surface)' }}>
                          <div className={`w-3 h-3 rounded-full shadow-sm ${scanLevel === 'level2' ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                          <span className={`text-sm font-medium ${scanLevel === 'level2' ? '' : 'opacity-60'}`} style={{ color: 'var(--fg)' }}>HTTP Server Analysis</span>
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
                      title={`URL: ${scanUrl || 'none'}, Level: ${scanLevel}, Scanning: ${isScanning}`}
                    >
                      {isScanning ? (
                        <div className="flex items-center justify-center gap-3">
                            <div className="animate-spin rounded-full h-6 w-6 border-3 border-white border-t-transparent"></div>
                          <span className="text-lg">{scanStatus || 'Starting scan...'}</span>
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-3">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span className="text-lg">
                            Start {scanLevel === 'level0' ? 'Level 0' : scanLevel === 'level1' ? 'Level 1' : 'Level 2'} Security Scan
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
                        {scanLevel === 'level0' ? '3-8 minutes' : scanLevel === 'level1' ? '10-25 minutes' : '20-45 minutes'}
                      </p>
                    </div>
                  </div>
                </div>
                </div>
              </div>
            </div>

            {/* Current Scan Results - Futuristic Dashboard */}
            {currentScan && (
              <div className="mb-8">
                <div className="relative overflow-hidden rounded-2xl border shadow-2xl" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
                  {/* Animated Background */}
                  <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5"></div>
                  <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-blue-500/10 to-transparent rounded-full -translate-y-48 translate-x-48 animate-pulse"></div>
                  <div className="absolute bottom-0 left-0 w-80 h-80 bg-gradient-to-tr from-purple-500/10 to-transparent rounded-full translate-y-40 -translate-x-40 animate-pulse"></div>
                  
                  {/* Scan Header */}
                  <div className="relative z-10 p-8 border-b" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex items-center justify-between mb-6">
                      <div className="flex-1">
                        <div className="flex items-center gap-4 mb-4">
                          <div className="h-12 w-12 rounded-xl flex items-center justify-center shadow-lg" style={{ background: 'linear-gradient(135deg, var(--brand) 0%, #3b82f6 100%)' }}>
                            <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                          </div>
                          <div>
                            <h2 className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>Security Assessment Report</h2>
                            <div className="flex items-center gap-3 mt-2">
                              <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(currentScan.score)}`} style={{ background: 'var(--surface-2)' }}>
                                {currentScan.score >= 80 ? '🛡️ SECURE' : currentScan.score >= 60 ? '⚠️ MODERATE' : '🚨 AT RISK'}
                              </span>
                              <span className="px-3 py-1 rounded-full text-sm font-medium" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                                {currentScan.scanType.toUpperCase()} SCAN
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-6 text-sm" style={{ color: 'var(--muted)' }}>
                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                            </svg>
                            <span>{currentScan.url}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{formatDateTime(currentScan.timestamp)}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                            </svg>
                            <span>{currentScan.duration}s duration</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{currentScan.vulnerabilities.length} issues found</span>
                          </div>
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="relative">
                          <div className="w-32 h-32 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                            <div className="w-24 h-24 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--brand) 0%, #3b82f6 100%)' }}>
                              <div className={`text-4xl font-bold text-white`}>
                                {currentScan.score}
                              </div>
                            </div>
                          </div>
                          <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2">
                            <div className="text-sm font-bold" style={{ color: 'var(--fg)' }}>Security Score</div>
                            <div className="text-xs" style={{ color: 'var(--muted)' }}>
                              {currentScan.score >= 90 ? 'Excellent' : 
                               currentScan.score >= 80 ? 'Good' : 
                               currentScan.score >= 70 ? 'Fair' : 
                               currentScan.score >= 60 ? 'Poor' : 'Critical'}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Tabs */}
                  <div className="relative z-10 border-b" style={{ borderColor: 'var(--border)' }}>
                    <nav className="flex space-x-8 px-8">
                      {tabs.map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab(tab.id)}
                          className={`py-4 px-1 border-b-2 font-medium text-sm transition-all duration-200 ${
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
                  <div className="relative z-10 p-8">
                    {activeTab === 'overview' && (
                      <div className="space-y-8">
                        {/* Security Metrics Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                          <div className="relative p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                            <div className="flex items-center justify-between mb-4">
                              <div className="p-3 rounded-lg bg-green-100">
                                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                              </div>
                              <div className="text-right">
                                <div className="text-3xl font-bold text-green-600">{currentScan.vulnerabilities.filter(v => v.severity === 'low').length}</div>
                                <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Low Risk</div>
                              </div>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div className="bg-green-500 h-2 rounded-full" style={{ width: `${(currentScan.vulnerabilities.filter(v => v.severity === 'low').length / Math.max(currentScan.vulnerabilities.length, 1)) * 100}%` }}></div>
                            </div>
                          </div>

                          <div className="relative p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                            <div className="flex items-center justify-between mb-4">
                              <div className="p-3 rounded-lg bg-yellow-100">
                                <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                                </svg>
                              </div>
                              <div className="text-right">
                                <div className="text-3xl font-bold text-yellow-600">{currentScan.vulnerabilities.filter(v => v.severity === 'medium').length}</div>
                                <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Medium Risk</div>
                              </div>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div className="bg-yellow-500 h-2 rounded-full" style={{ width: `${(currentScan.vulnerabilities.filter(v => v.severity === 'medium').length / Math.max(currentScan.vulnerabilities.length, 1)) * 100}%` }}></div>
                            </div>
                          </div>

                          <div className="relative p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                            <div className="flex items-center justify-between mb-4">
                              <div className="p-3 rounded-lg bg-red-100">
                                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                              </div>
                              <div className="text-right">
                                <div className="text-3xl font-bold text-red-600">{currentScan.vulnerabilities.filter(v => v.severity === 'high').length}</div>
                                <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>High Risk</div>
                              </div>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div className="bg-red-500 h-2 rounded-full" style={{ width: `${(currentScan.vulnerabilities.filter(v => v.severity === 'high').length / Math.max(currentScan.vulnerabilities.length, 1)) * 100}%` }}></div>
                            </div>
                          </div>

                          <div className="relative p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                            <div className="flex items-center justify-between mb-4">
                              <div className="p-3 rounded-lg bg-purple-100">
                                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                              </div>
                              <div className="text-right">
                                <div className="text-3xl font-bold text-purple-600">{currentScan.vulnerabilities.filter(v => v.severity === 'critical').length}</div>
                                <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Critical</div>
                              </div>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div className="bg-purple-500 h-2 rounded-full" style={{ width: `${(currentScan.vulnerabilities.filter(v => v.severity === 'critical').length / Math.max(currentScan.vulnerabilities.length, 1)) * 100}%` }}></div>
                            </div>
                          </div>
                        </div>

                        {/* Security Score Visualization */}
                        <div className="p-8 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                          <h3 className="text-xl font-bold mb-6" style={{ color: 'var(--fg)' }}>Security Score Breakdown</h3>
                          <div className="flex items-center justify-between">
                            <div className="flex-1">
                              <div className="flex items-center justify-between mb-2">
                                <span className="text-sm font-medium" style={{ color: 'var(--fg)' }}>Overall Security</span>
                                <span className="text-sm font-bold" style={{ color: 'var(--brand)' }}>{currentScan.score}/100</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-4">
                                <div 
                                  className="h-4 rounded-full transition-all duration-1000 ease-out"
                                  style={{ 
                                    width: `${currentScan.score}%`,
                                    background: currentScan.score >= 80 ? 'linear-gradient(90deg, #10b981, #34d399)' : 
                                               currentScan.score >= 60 ? 'linear-gradient(90deg, #f59e0b, #fbbf24)' : 
                                               'linear-gradient(90deg, #ef4444, #f87171)'
                                  }}
                                ></div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'vulnerabilities' && (
                      <div className="space-y-6">
                        {currentScan.vulnerabilities.length === 0 ? (
                          <div className="text-center py-12">
                            <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                              <svg className="w-12 h-12 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            </div>
                            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--fg)' }}>No Vulnerabilities Found</h3>
                            <p className="text-sm" style={{ color: 'var(--muted)' }}>Great! No security issues were detected in this scan.</p>
                          </div>
                        ) : (
                          currentScan.vulnerabilities.map((vuln, index) => (
                            <div key={vuln.id} className="relative p-6 rounded-xl border shadow-lg hover:shadow-xl transition-all duration-200" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                              <div className="flex items-start justify-between mb-4">
                                <div className="flex items-start gap-4">
                                  <div className={`p-3 rounded-lg ${getSeverityColor(vuln.severity)}`}>
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      {vuln.severity === 'critical' ? (
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                      ) : vuln.severity === 'high' ? (
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                                      ) : (
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                      )}
                                    </svg>
                                  </div>
                                  <div className="flex-1">
                                    <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--fg)' }}>{vuln.title}</h3>
                                    <div className="flex items-center gap-3 mb-3">
                                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${getSeverityColor(vuln.severity)}`}>
                                        {vuln.severity.toUpperCase()}
                                      </span>
                                      {vuln.cwe && (
                                        <span className="px-2 py-1 rounded text-xs font-mono" style={{ background: 'var(--surface)', color: 'var(--muted)' }}>
                                          CWE-{vuln.cwe}
                                        </span>
                                      )}
                                      {vuln.cvss && (
                                        <span className="px-2 py-1 rounded text-xs font-mono" style={{ background: 'var(--surface)', color: 'var(--muted)' }}>
                                          CVSS: {vuln.cvss}
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                              <div className="mb-4">
                                <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>{vuln.description}</p>
                              </div>
                              <div className="p-4 rounded-lg" style={{ background: 'var(--surface)' }}>
                                <h4 className="font-semibold mb-2 flex items-center gap-2" style={{ color: 'var(--fg)' }}>
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                  </svg>
                                  Recommendation
                                </h4>
                                <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>{vuln.recommendation}</p>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    )}

                    {activeTab === 'recommendations' && (
                      <div className="space-y-6">
                        <div className="p-8 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                          <h3 className="text-xl font-bold mb-6 flex items-center gap-3" style={{ color: 'var(--fg)' }}>
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                            </svg>
                            Immediate Actions Required
                          </h3>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-4">
                              <div className="flex items-start gap-3 p-4 rounded-lg" style={{ background: 'var(--surface)' }}>
                                <div className="w-2 h-2 rounded-full bg-red-500 mt-2"></div>
                                <div>
                                  <h4 className="font-semibold mb-1" style={{ color: 'var(--fg)' }}>Update Security Headers</h4>
                                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Implement comprehensive security headers to protect against common attacks</p>
                                </div>
                              </div>
                              <div className="flex items-start gap-3 p-4 rounded-lg" style={{ background: 'var(--surface)' }}>
                                <div className="w-2 h-2 rounded-full bg-orange-500 mt-2"></div>
                                <div>
                                  <h4 className="font-semibold mb-1" style={{ color: 'var(--fg)' }}>SSL/TLS Configuration</h4>
                                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Update to TLS 1.2 or higher and disable weak cipher suites</p>
                                </div>
                              </div>
                            </div>
                            <div className="space-y-4">
                              <div className="flex items-start gap-3 p-4 rounded-lg" style={{ background: 'var(--surface)' }}>
                                <div className="w-2 h-2 rounded-full bg-yellow-500 mt-2"></div>
                                <div>
                                  <h4 className="font-semibold mb-1" style={{ color: 'var(--fg)' }}>Authentication Review</h4>
                                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Review and strengthen authentication mechanisms</p>
                                </div>
                              </div>
                              <div className="flex items-start gap-3 p-4 rounded-lg" style={{ background: 'var(--surface)' }}>
                                <div className="w-2 h-2 rounded-full bg-blue-500 mt-2"></div>
                                <div>
                                  <h4 className="font-semibold mb-1" style={{ color: 'var(--fg)' }}>Regular Monitoring</h4>
                                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Set up continuous security monitoring and scanning</p>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {activeTab === 'history' && (
                      <div className="space-y-4">
                        {scans.length === 0 ? (
                          <div className="text-center py-12">
                            <div className="w-24 h-24 mx-auto mb-4 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)' }}>
                              <svg className="w-12 h-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            </div>
                            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--fg)' }}>No Scan History</h3>
                            <p className="text-sm" style={{ color: 'var(--muted)' }}>Start your first security scan to see results here.</p>
                          </div>
                        ) : (
                          scans.map((scan) => (
                            <div key={scan.id} className="flex items-center justify-between p-6 rounded-xl border shadow-lg hover:shadow-xl transition-all duration-200" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                              <div className="flex items-center gap-4">
                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${getScoreColor(scan.score)}`} style={{ background: 'var(--surface)' }}>
                                  <span className="text-lg font-bold">{scan.score}</span>
                                </div>
                                <div>
                                  <div className="font-bold" style={{ color: 'var(--fg)' }}>{scan.url}</div>
                                  <div className="text-sm" style={{ color: 'var(--muted)' }}>
                                    {formatDateTime(scan.timestamp)} • {scan.scanType} • {scan.duration}s
                                  </div>
                                </div>
                              </div>
                              <div className="text-right">
                                <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>{scan.vulnerabilities.length} issues</div>
                                <div className="text-xs" style={{ color: 'var(--muted)' }}>Security Score</div>
                              </div>
                            </div>
                          ))
                        )}
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
