'use client';

import { useState } from 'react';
import { Session } from 'next-auth';
import AppShell from '@/components/layout/AppShell';
import DashboardStats from './DashboardStats';
import RecentScans from './RecentScans';
import QuickActions from './QuickActions';
import SecurityInsights from './SecurityInsights';

interface DashboardClientProps {
  user: any;
  session: Session | null;
}

export default function DashboardClient({ user, session }: DashboardClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <AppShell user={user} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen}>
      {/* Welcome Section — same rhythm as other dashboard pages */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-1.5" style={{ color: 'var(--text)' }}>
          Welcome back, {user.name || user.email?.split('@')[0]}!
        </h1>
        <p className="text-base" style={{ color: 'var(--muted)' }}>
          Here&apos;s what&apos;s happening with your security testing today.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
        <DashboardStats session={session} />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
        <div className="lg:col-span-2">
          <RecentScans session={session} />
        </div>
        <div className="lg:col-span-1">
          <QuickActions />
        </div>
      </div>

      {/* Security Insights */}
      <div className="mb-6">
        <SecurityInsights />
      </div>
    </AppShell>
  );
}
