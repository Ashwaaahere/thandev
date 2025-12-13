'use client';

import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import ScanHistoryContent from './ScanHistoryContent';
import PerformanceHistoryContent from './PerformanceHistoryContent';
import DashboardHeader from './DashboardHeader';
import DashboardSidebar from './DashboardSidebar';

export default function HistoryClient() {
  const { data: session, status: sessionStatus } = useSession();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'security' | 'performance'>('security');

  if (sessionStatus === 'loading') {
    return (
      <div className="flex h-screen overflow-hidden">
        <DashboardSidebar 
          isOpen={sidebarOpen} 
          onClose={() => setSidebarOpen(false)} 
          showLogo={!sidebarOpen}
        />
        <div className="flex-1 flex flex-col overflow-hidden">
          <DashboardHeader 
            user={session ? session.user : undefined} 
            onMenuClick={() => setSidebarOpen(true)}
            showLogo={sidebarOpen}
          />
          <main className="flex-1 overflow-y-auto p-6" style={{ background: 'var(--bg)' }}>
            <div className="max-w-7xl mx-auto">
              <div className="space-y-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="rounded-xl border p-6 animate-pulse" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                    <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3 mb-2"></div>
                    <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                  </div>
                ))}
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (sessionStatus === 'unauthenticated') {
    router.push('/auth/signin');
    return null;
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        showLogo={!sidebarOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader 
          user={session ? session.user : undefined} 
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main className="flex-1 overflow-y-auto" style={{ background: 'var(--bg)' }}>
          <div className="container mx-auto px-6 py-8">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
                History
              </h1>
              <p className="text-lg" style={{ color: 'var(--muted)' }}>
                View and manage your scan history
              </p>
            </div>

            {/* Tabs */}
            <div className="mb-6">
              <div className="flex gap-2 border-b" style={{ borderColor: 'var(--border)' }}>
                <button
                  onClick={() => setActiveTab('security')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === 'security'
                      ? 'border-b-2 text-white'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                  style={{
                    borderColor: activeTab === 'security' ? 'var(--brand)' : 'transparent',
                    color: activeTab === 'security' ? 'white' : 'var(--muted)'
                  }}
                >
                  Security Scan History
                </button>
                <button
                  onClick={() => setActiveTab('performance')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === 'performance'
                      ? 'border-b-2 text-white'
                      : 'text-gray-400 hover:text-gray-300'
                  }`}
                  style={{
                    borderColor: activeTab === 'performance' ? 'var(--brand)' : 'transparent',
                    color: activeTab === 'performance' ? 'white' : 'var(--muted)'
                  }}
                >
                  Performance Scan History
                </button>
              </div>
            </div>

            {/* Tab Content */}
            <div>
              {activeTab === 'security' ? (
                <ScanHistoryContent user={session ? session.user : undefined} session={session} />
              ) : (
                <PerformanceHistoryContent />
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
