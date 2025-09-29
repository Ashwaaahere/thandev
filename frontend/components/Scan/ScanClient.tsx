'use client';

import { useState, useEffect } from 'react';
import ScanForm from './ScanForm';
import ScanResults from './ScanResults';
import ScanHistory from './ScanHistory';
import ScanStats from './ScanStats';

export interface ScanResult {
  id: string;
  url: string;
  status: 'pending' | 'scanning' | 'completed' | 'error';
  vulnerabilities: Vulnerability[];
  scanTime: number;
  timestamp: Date;
  score: number;
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

export default function ScanClient() {
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [currentScan, setCurrentScan] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load scan history from localStorage on mount
  useEffect(() => {
    const savedScans = localStorage.getItem('thandev-scans');
    if (savedScans) {
      try {
        const parsedScans = JSON.parse(savedScans).map((scan: any) => ({
          ...scan,
          timestamp: new Date(scan.timestamp)
        }));
        setScans(parsedScans);
      } catch (e) {
        console.error('Failed to parse saved scans:', e);
      }
    }
  }, []);

  // Save scans to localStorage whenever scans change
  useEffect(() => {
    if (scans.length > 0) {
      localStorage.setItem('thandev-scans', JSON.stringify(scans));
    }
  }, [scans]);

  const handleScan = async (url: string, scanType: string) => {
    setLoading(true);
    setError(null);
    
    const newScan: ScanResult = {
      id: Date.now().toString(),
      url,
      status: 'pending',
      vulnerabilities: [],
      scanTime: 0,
      timestamp: new Date(),
      score: 0
    };

    setCurrentScan(newScan);
    setScans(prev => [newScan, ...prev]);

    try {
      // Simulate scanning process
      await simulateScan(newScan);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan failed');
      setCurrentScan(prev => prev ? { ...prev, status: 'error' } : null);
    } finally {
      setLoading(false);
    }
  };

  const simulateScan = async (scan: ScanResult) => {
    // Update status to scanning
    setCurrentScan(prev => prev ? { ...prev, status: 'scanning' } : null);
    setScans(prev => prev.map(s => s.id === scan.id ? { ...s, status: 'scanning' } : s));

    // Simulate scan time
    const startTime = Date.now();
    
    // Simulate different scan phases
    await new Promise(resolve => setTimeout(resolve, 1000)); // Initial check
    await new Promise(resolve => setTimeout(resolve, 2000)); // Port scanning
    await new Promise(resolve => setTimeout(resolve, 1500)); // Vulnerability detection
    await new Promise(resolve => setTimeout(resolve, 1000)); // Report generation

    const scanTime = Date.now() - startTime;

    // Generate mock vulnerabilities based on URL
    const vulnerabilities = generateMockVulnerabilities(scan.url);
    const score = calculateSecurityScore(vulnerabilities);

    const completedScan: ScanResult = {
      ...scan,
      status: 'completed',
      vulnerabilities,
      scanTime,
      score
    };

    setCurrentScan(completedScan);
    setScans(prev => prev.map(s => s.id === scan.id ? completedScan : s));
  };

  const generateMockVulnerabilities = (url: string): Vulnerability[] => {
    const vulnerabilities: Vulnerability[] = [];
    
    // Generate random vulnerabilities based on URL characteristics
    const urlLower = url.toLowerCase();
    
    if (urlLower.includes('http://')) {
      vulnerabilities.push({
        id: '1',
        type: 'Insecure Protocol',
        severity: 'medium',
        title: 'HTTP Protocol Used',
        description: 'The website is using HTTP instead of HTTPS, which means data is transmitted in plain text.',
        recommendation: 'Implement HTTPS with SSL/TLS certificates to encrypt data transmission.',
        cwe: 'CWE-319',
        cvss: 5.3
      });
    }

    if (urlLower.includes('www.')) {
      vulnerabilities.push({
        id: '2',
        type: 'Subdomain Configuration',
        severity: 'low',
        title: 'WWW Subdomain Present',
        description: 'The website uses www subdomain which may cause confusion in security policies.',
        recommendation: 'Consider redirecting www to the main domain or vice versa for consistency.',
        cwe: 'CWE-16',
        cvss: 2.1
      });
    }

    // Add some random vulnerabilities
    const randomVulns = [
      {
        id: '3',
        type: 'Security Headers',
        severity: 'medium' as const,
        title: 'Missing Security Headers',
        description: 'The website is missing important security headers like X-Frame-Options, X-Content-Type-Options.',
        recommendation: 'Implement security headers to prevent clickjacking and MIME type sniffing attacks.',
        cwe: 'CWE-693',
        cvss: 4.2
      },
      {
        id: '4',
        type: 'Information Disclosure',
        severity: 'low' as const,
        title: 'Server Information Disclosure',
        description: 'The server is revealing version information in HTTP headers.',
        recommendation: 'Configure the server to hide version information from HTTP headers.',
        cwe: 'CWE-200',
        cvss: 2.8
      }
    ];

    // Randomly add vulnerabilities
    if (Math.random() > 0.3) vulnerabilities.push(randomVulns[0]);
    if (Math.random() > 0.5) vulnerabilities.push(randomVulns[1]);

    return vulnerabilities;
  };

  const calculateSecurityScore = (vulnerabilities: Vulnerability[]): number => {
    if (vulnerabilities.length === 0) return 100;
    
    let totalDeduction = 0;
    vulnerabilities.forEach(vuln => {
      switch (vuln.severity) {
        case 'critical': totalDeduction += 25; break;
        case 'high': totalDeduction += 15; break;
        case 'medium': totalDeduction += 10; break;
        case 'low': totalDeduction += 5; break;
        case 'info': totalDeduction += 2; break;
      }
    });
    
    return Math.max(0, 100 - totalDeduction);
  };

  const clearHistory = () => {
    setScans([]);
    localStorage.removeItem('thandev-scans');
  };

  return (
    <div className="space-y-8">
      {/* Stats */}
      <ScanStats scans={scans} />

      {/* Scan Form */}
      <ScanForm onScan={handleScan} loading={loading} />

      {/* Current Scan Results */}
      {currentScan && (
        <ScanResults scan={currentScan} />
      )}

      {/* Error Display */}
      {error && (
        <div className="relative overflow-hidden rounded-2xl border border-red-200/50 bg-gradient-to-br from-red-50/50 to-red-100/30 p-6 backdrop-blur-sm dark:border-red-800/50 dark:from-red-950/40 dark:to-red-900/20">
          <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="flex items-center gap-3 mb-2">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm font-semibold text-red-600 dark:text-red-400">SCAN ERROR</span>
            </div>
            <p className="text-red-600 dark:text-red-300">{error}</p>
          </div>
        </div>
      )}

      {/* Scan History */}
      <ScanHistory scans={scans} onClear={clearHistory} />
    </div>
  );
}
