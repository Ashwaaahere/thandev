'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Session } from 'next-auth';
import DashboardHeader from './DashboardHeader';
import DashboardStats from './DashboardStats';
import RecentScans from './RecentScans';
import QuickActions from './QuickActions';
import SecurityInsights from './SecurityInsights';
import DashboardSidebar from './DashboardSidebar';

interface DashboardClientProps {
  user: any;
  session: Session | null;
}

export default function DashboardClient({ user, session }: DashboardClientProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

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
        
        {/* Dashboard Content */}
        <main className="flex-1 overflow-y-auto p-5" style={{ background: 'var(--bg)' }}>
          <div className="max-w-7xl mx-auto">
            {/* Welcome Section */}
            <div className="mb-6">
              <h1 className="text-3xl font-bold mb-1.5 text-white">
                Welcome back, {user.name || user.email.split('@')[0]}!
              </h1>
              <p className="text-base text-white">
                Here's what's happening with your security testing today.
              </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
              <DashboardStats session={session} />
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-6">
              {/* Recent Scans - Takes 2 columns on large screens */}
              <div className="lg:col-span-2">
                <RecentScans session={session} />
              </div>
              
              {/* Quick Actions - Takes 1 column on large screens */}
              <div className="lg:col-span-1">
                <QuickActions />
              </div>
            </div>

            {/* Security Insights */}
            <div className="mb-6">
              <SecurityInsights />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
