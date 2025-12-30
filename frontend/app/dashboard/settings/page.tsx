'use client';

import { useSession } from 'next-auth/react';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import { useState } from 'react';

export default function SettingsPage() {
  const { data: session } = useSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <DashboardHeader user={session?.user} onMenuClick={() => setSidebarOpen(true)} />
      <div className="flex">
        <DashboardSidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <main className="flex-1 p-8">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold text-white mb-6">Settings</h1>
            <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
              <p className="text-slate-300">Settings page coming soon.</p>
              <p className="text-slate-400 text-sm mt-2">
                Manage your account preferences, API keys, and notification settings here.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

