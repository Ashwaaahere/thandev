'use client';

import { useSession } from 'next-auth/react';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';
import { useState } from 'react';

export default function SupportPage() {
  const { data: session } = useSession();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <DashboardHeader sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
      <div className="flex">
        <DashboardSidebar sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} />
        <main className="flex-1 p-8">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold text-white mb-6">Help & Support</h1>
            <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
              <p className="text-slate-300">Support page coming soon.</p>
              <p className="text-slate-400 text-sm mt-2">
                Get help, contact support, or browse documentation.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

