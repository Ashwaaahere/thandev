'use client';

import { ReactNode } from 'react';
import DashboardHeader from '@/components/Dashboard/DashboardHeader';
import DashboardSidebar from '@/components/Dashboard/DashboardSidebar';

export interface AppShellProps {
  children: ReactNode;
  user?: { name?: string | null; email?: string | null } | null;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
}

/**
 * Shared app shell for dashboard pages: sidebar + header + main content area.
 * Uses consistent padding, max-width, and background so every page feels unified.
 */
export default function AppShell({ children, user, sidebarOpen, setSidebarOpen }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden dashboard-bg">
      <DashboardSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        showLogo={!sidebarOpen}
      />
      <div className="flex-1 flex flex-col overflow-hidden">
        <DashboardHeader
          user={user ?? undefined}
          onMenuClick={() => setSidebarOpen(true)}
          showLogo={sidebarOpen}
        />
        <main
          className="flex-1 overflow-y-auto p-5"
          style={{ background: 'var(--bg)' }}
        >
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
