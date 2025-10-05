'use client';

import { useState, useEffect } from 'react';

interface Insight {
  id: string;
  title: string;
  description: string;
  type: 'warning' | 'info' | 'success' | 'critical';
  action?: string;
  actionHref?: string;
}

export default function SecurityInsights() {
  const [insights, setInsights] = useState<Insight[]>([]);

  useEffect(() => {
    // Generate insights based on scan history
    const scanHistory = JSON.parse(localStorage.getItem('thandev-scan-history') || '[]');
    const generatedInsights: Insight[] = [];

    if (scanHistory.length === 0) {
      generatedInsights.push({
        id: '1',
        title: 'Welcome to Thandev!',
        description: 'Start your first security scan to begin protecting your applications.',
        type: 'info',
        action: 'Start First Scan',
        actionHref: '/scan'
      });
    } else {
      const totalScans = scanHistory.length;
      const avgScore = scanHistory.reduce((sum: number, scan: any) => sum + (scan.score || 0), 0) / totalScans;
      const criticalVulns = scanHistory.reduce((sum: number, scan: any) => {
        return sum + (scan.vulnerabilities?.filter((v: any) => v.severity === 'critical').length || 0);
      }, 0);

      if (criticalVulns > 0) {
        generatedInsights.push({
          id: '2',
          title: 'Critical Vulnerabilities Detected',
          description: `You have ${criticalVulns} critical vulnerabilities across your scans. Immediate action recommended.`,
          type: 'critical',
          action: 'View Details',
          actionHref: '/dashboard/reports'
        });
      }

      if (avgScore < 60) {
        generatedInsights.push({
          id: '3',
          title: 'Security Score Needs Improvement',
          description: `Your average security score is ${Math.round(avgScore)}/100. Consider implementing security best practices.`,
          type: 'warning',
          action: 'View Recommendations',
          actionHref: '/dashboard/reports'
        });
      } else if (avgScore >= 80) {
        generatedInsights.push({
          id: '4',
          title: 'Excellent Security Posture',
          description: `Your average security score is ${Math.round(avgScore)}/100. Keep up the great work!`,
          type: 'success'
        });
      }

      if (totalScans >= 5) {
        generatedInsights.push({
          id: '5',
          title: 'Regular Scanning Active',
          description: `You've completed ${totalScans} scans. Regular security testing is key to maintaining a secure environment.`,
          type: 'success'
        });
      }

      // Add general security tips
      generatedInsights.push({
        id: '6',
        title: 'Security Tip',
        description: 'Keep your dependencies updated and regularly scan for known vulnerabilities.',
        type: 'info'
      });
    }

    setInsights(generatedInsights.slice(0, 3)); // Show max 3 insights
  }, []);

  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'critical':
        return 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z';
      case 'warning':
        return 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z';
      case 'success':
        return 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z';
      case 'info':
        return 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
      default:
        return 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z';
    }
  };

  const getInsightColor = (type: string) => {
    switch (type) {
      case 'critical':
        return 'text-red-600 bg-red-100 dark:text-red-400 dark:bg-red-900/20';
      case 'warning':
        return 'text-orange-600 bg-orange-100 dark:text-orange-400 dark:bg-orange-900/20';
      case 'success':
        return 'text-green-600 bg-green-100 dark:text-green-400 dark:bg-green-900/20';
      case 'info':
        return 'text-blue-600 bg-blue-100 dark:text-blue-400 dark:bg-blue-900/20';
      default:
        return 'text-gray-600 bg-gray-100 dark:text-gray-400 dark:bg-gray-900/20';
    }
  };

  if (insights.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      {/* Header */}
      <div className="px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
          Security Insights
        </h2>
      </div>

      {/* Content */}
      <div className="p-6">
        <div className="space-y-4">
          {insights.map((insight) => (
            <div key={insight.id} className="flex items-start gap-4 p-4 rounded-lg border" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
              <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${getInsightColor(insight.type)}`}>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getInsightIcon(insight.type)} />
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-medium mb-1" style={{ color: 'var(--fg)' }}>
                  {insight.title}
                </h3>
                <p className="text-sm mb-3" style={{ color: 'var(--muted)' }}>
                  {insight.description}
                </p>
                {insight.action && insight.actionHref && (
                  <a
                    href={insight.actionHref}
                    className="inline-flex items-center gap-1 text-sm font-medium hover:opacity-80 transition-opacity"
                    style={{ color: 'var(--brand)' }}
                  >
                    {insight.action}
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}




