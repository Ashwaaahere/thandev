'use client';

import { useState, useEffect } from 'react';

interface StatCardProps {
  title: string;
  value: string | number;
  change: string;
  changeType: 'positive' | 'negative' | 'neutral';
  icon: string;
  description: string;
}

function StatCard({ title, value, change, changeType, icon, description }: StatCardProps) {
  const getChangeColor = () => {
    switch (changeType) {
      case 'positive':
        return 'text-green-600 dark:text-green-400';
      case 'negative':
        return 'text-red-600 dark:text-red-400';
      default:
        return 'text-gray-600 dark:text-gray-400';
    }
  };

  const getChangeIcon = () => {
    switch (changeType) {
      case 'positive':
        return 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6';
      case 'negative':
        return 'M13 17h8m0 0V9m0 8l-8-8-4 4-6-6';
      default:
        return 'M20 12H4';
    }
  };

  return (
    <div className="rounded-xl border p-6 shadow-sm hover:shadow-md transition-shadow" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium mb-1" style={{ color: 'var(--muted)' }}>
            {title}
          </p>
          <p className="text-2xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
            {value}
          </p>
          <div className="flex items-center gap-1">
            <svg className={`w-4 h-4 ${getChangeColor()}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={getChangeIcon()} />
            </svg>
            <span className={`text-sm font-medium ${getChangeColor()}`}>
              {change}
            </span>
          </div>
        </div>
        <div className="flex-shrink-0">
          <div className="w-12 h-12 rounded-lg flex items-center justify-center" style={{ background: 'var(--brand)', opacity: 0.1 }}>
            <svg className="w-6 h-6" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
            </svg>
          </div>
        </div>
      </div>
      <p className="text-xs mt-2" style={{ color: 'var(--muted)' }}>
        {description}
      </p>
    </div>
  );
}

export default function DashboardStats() {
  const [stats, setStats] = useState({
    totalScans: 0,
    vulnerabilitiesFound: 0,
    averageScore: 0,
    scansThisMonth: 0
  });

  useEffect(() => {
    // Load stats from localStorage or API
    const scanHistory = JSON.parse(localStorage.getItem('thandev-scan-history') || '[]');
    const totalScans = scanHistory.length;
    const vulnerabilitiesFound = scanHistory.reduce((sum: number, scan: any) => sum + (scan.vulnerabilities?.length || 0), 0);
    const averageScore = totalScans > 0 ? Math.round(scanHistory.reduce((sum: number, scan: any) => sum + (scan.score || 0), 0) / totalScans) : 0;
    
    // Calculate scans this month
    const thisMonth = new Date().getMonth();
    const scansThisMonth = scanHistory.filter((scan: any) => {
      const scanDate = new Date(scan.timestamp);
      return scanDate.getMonth() === thisMonth;
    }).length;

    setStats({
      totalScans,
      vulnerabilitiesFound,
      averageScore,
      scansThisMonth
    });
  }, []);

  return (
    <>
      <StatCard
        title="Total Scans"
        value={stats.totalScans}
        change={`+${stats.scansThisMonth} this month`}
        changeType="positive"
        icon="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        description="Security assessments completed"
      />
      
      <StatCard
        title="Vulnerabilities Found"
        value={stats.vulnerabilitiesFound}
        change="Critical issues detected"
        changeType={stats.vulnerabilitiesFound > 0 ? "negative" : "positive"}
        icon="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
        description="Security issues identified"
      />
      
      <StatCard
        title="Average Score"
        value={`${stats.averageScore}/100`}
        change={stats.averageScore >= 80 ? "Excellent" : stats.averageScore >= 60 ? "Good" : "Needs improvement"}
        changeType={stats.averageScore >= 80 ? "positive" : stats.averageScore >= 60 ? "neutral" : "negative"}
        icon="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
        description="Overall security rating"
      />
      
      <StatCard
        title="This Month"
        value={stats.scansThisMonth}
        change="Active scanning period"
        changeType="positive"
        icon="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
        description="Scans performed this month"
      />
    </>
  );
}




