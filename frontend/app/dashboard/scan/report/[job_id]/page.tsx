'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';

interface ScanReport {
  jobId: string;
  summary: {
    url: string;
    tier: string;
    timestamp: string;
    vulnerabilities: Array<{
      id: string;
      type: string;
      severity: string;
      title: string;
      description: string;
      recommendation: string;
      cwe?: string;
      cvss?: number;
    }>;
    totalVulnerabilities: number;
    severityBreakdown: {
      critical: number;
      high: number;
      medium: number;
      low: number;
      info: number;
    };
    securityScore: number;
    openPorts: number;
    sslIssuesCount: number;
    scanMetadata: {
      toolsUsed: string[];
      scanTime: string;
    };
  };
  artifact_urls: string[];
  created_at: string;
  finished_at: string;
}

export default function ScanReportPage() {
  const params = useParams();
  const jobId = params.job_id as string;
  
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [report, setReport] = useState<ScanReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    if (jobId) {
      fetchReport();
    }
  }, [jobId]);

  const fetchReport = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/security-scan/results/${jobId}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch report');
      }
      
      const data = await response.json();
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load report');
    } finally {
      setLoading(false);
    }
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

  const getTierDisplayName = (tier: string) => {
    switch (tier) {
      case 'level0': return 'Level 0 — Surface (Quick)';
      case 'level1': return 'Level 1 — Discovery (Buzz)';
      case 'level2': return 'Level 2 — Active (Non-destructive)';
      default: return tier;
    }
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
            user={{}} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
              <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-3 border-blue-500 border-t-transparent"></div>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader 
            user={{}} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
              <div className="text-center py-12">
                <div className="text-red-500 text-6xl mb-4">⚠️</div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Report Not Found</h2>
                <p className="text-gray-600 dark:text-gray-300">{error || 'The requested scan report could not be found.'}</p>
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', name: 'Overview' },
    { id: 'vulnerabilities', name: 'Vulnerabilities' },
    { id: 'artifacts', name: 'Artifacts' },
    { id: 'timeline', name: 'Timeline' }
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader 
          user={{}} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        
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
                  <h1 className="text-3xl font-bold" style={{ color: 'var(--fg)' }}>Security Scan Report</h1>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>Detailed analysis and findings</p>
                </div>
              </div>
            </div>

            {/* Report Content */}
            <div className="relative overflow-hidden rounded-2xl border shadow-2xl" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
              {/* Animated Background */}
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5"></div>
              <div className="absolute top-0 right-0 w-96 h-96 bg-gradient-to-bl from-blue-500/10 to-transparent rounded-full -translate-y-48 translate-x-48 animate-pulse"></div>
              <div className="absolute bottom-0 left-0 w-80 h-80 bg-gradient-to-tr from-purple-500/10 to-transparent rounded-full translate-y-40 -translate-x-40 animate-pulse"></div>
              
              {/* Report Header */}
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
                          <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(report.summary.securityScore)}`} style={{ background: 'var(--surface-2)' }}>
                            {report.summary.securityScore >= 80 ? '🛡️ SECURE' : report.summary.securityScore >= 60 ? '⚠️ MODERATE' : '🚨 AT RISK'}
                          </span>
                          <span className="px-3 py-1 rounded-full text-sm font-medium" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                            {getTierDisplayName(report.summary.tier).toUpperCase()}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-6 text-sm" style={{ color: 'var(--muted)' }}>
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                        </svg>
                        <span>{report.summary.url}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>{new Date(report.created_at).toLocaleString()}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span>{report.summary.vulnerabilities.length} issues found</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="relative">
                      <div className="w-32 h-32 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                        <div className="w-24 h-24 rounded-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, var(--brand) 0%, #3b82f6 100%)' }}>
                          <div className={`text-4xl font-bold text-white`}>
                            {report.summary.securityScore}
                          </div>
                        </div>
                      </div>
                      <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2">
                        <div className="text-sm font-bold" style={{ color: 'var(--fg)' }}>Security Score</div>
                        <div className="text-xs" style={{ color: 'var(--muted)' }}>
                          {report.summary.securityScore >= 90 ? 'Excellent' : 
                           report.summary.securityScore >= 80 ? 'Good' : 
                           report.summary.securityScore >= 70 ? 'Fair' : 
                           report.summary.securityScore >= 60 ? 'Poor' : 'Critical'}
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
                            <div className="text-3xl font-bold text-green-600">{report.summary.severityBreakdown.low}</div>
                            <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Low Risk</div>
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className="bg-green-500 h-2 rounded-full" style={{ width: `${(report.summary.severityBreakdown.low / Math.max(report.summary.totalVulnerabilities, 1)) * 100}%` }}></div>
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
                            <div className="text-3xl font-bold text-yellow-600">{report.summary.severityBreakdown.medium}</div>
                            <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Medium Risk</div>
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className="bg-yellow-500 h-2 rounded-full" style={{ width: `${(report.summary.severityBreakdown.medium / Math.max(report.summary.totalVulnerabilities, 1)) * 100}%` }}></div>
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
                            <div className="text-3xl font-bold text-red-600">{report.summary.severityBreakdown.high}</div>
                            <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>High Risk</div>
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className="bg-red-500 h-2 rounded-full" style={{ width: `${(report.summary.severityBreakdown.high / Math.max(report.summary.totalVulnerabilities, 1)) * 100}%` }}></div>
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
                            <div className="text-3xl font-bold text-purple-600">{report.summary.severityBreakdown.critical}</div>
                            <div className="text-sm font-medium" style={{ color: 'var(--muted)' }}>Critical</div>
                          </div>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div className="bg-purple-500 h-2 rounded-full" style={{ width: `${(report.summary.severityBreakdown.critical / Math.max(report.summary.totalVulnerabilities, 1)) * 100}%` }}></div>
                        </div>
                      </div>
                    </div>

                    {/* Tools Used */}
                    <div className="p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                      <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Tools Used</h3>
                      <div className="flex flex-wrap gap-2">
                        {report.summary.scanMetadata.toolsUsed.map((tool, index) => (
                          <span key={index} className="px-3 py-1 rounded-full text-sm font-medium" style={{ background: 'var(--brand)', color: 'white' }}>
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {activeTab === 'vulnerabilities' && (
                  <div className="space-y-6">
                    {report.summary.vulnerabilities.length === 0 ? (
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
                      report.summary.vulnerabilities.map((vuln, index) => (
                        <div key={vuln.id || index} className="relative p-6 rounded-xl border shadow-lg hover:shadow-xl transition-all duration-200" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
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

                {activeTab === 'artifacts' && (
                  <div className="space-y-6">
                    <div className="p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                      <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Scan Artifacts</h3>
                      {report.artifact_urls.length === 0 ? (
                        <p className="text-gray-500">No artifacts available for this scan.</p>
                      ) : (
                        <div className="space-y-2">
                          {report.artifact_urls.map((url, index) => (
                            <div key={index} className="flex items-center justify-between p-3 rounded-lg" style={{ background: 'var(--surface)' }}>
                              <span className="font-mono text-sm" style={{ color: 'var(--fg)' }}>{url}</span>
                              <button className="px-3 py-1 rounded text-sm font-medium" style={{ background: 'var(--brand)', color: 'white' }}>
                                Download
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {activeTab === 'timeline' && (
                  <div className="space-y-6">
                    <div className="p-6 rounded-xl border shadow-lg" style={{ borderColor: 'var(--border)', background: 'linear-gradient(135deg, var(--surface-2) 0%, var(--surface) 100%)' }}>
                      <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--fg)' }}>Scan Timeline</h3>
                      <div className="space-y-4">
                        <div className="flex items-center gap-4">
                          <div className="w-3 h-3 rounded-full bg-green-500"></div>
                          <div>
                            <div className="font-medium" style={{ color: 'var(--fg)' }}>Scan Started</div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>{new Date(report.created_at).toLocaleString()}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                          <div>
                            <div className="font-medium" style={{ color: 'var(--fg)' }}>Scan Completed</div>
                            <div className="text-sm" style={{ color: 'var(--muted)' }}>{new Date(report.finished_at).toLocaleString()}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
