'use client';

import { useState } from 'react';
import DocsSidebar from '@/components/docs/DocsSidebar';
import DocsHeader from '@/components/docs/DocsHeader';

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex flex-col min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <DocsHeader />

      {/* Main Layout */}
      <div className="flex flex-1">
        {/* Sidebar */}
        <DocsSidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

        {/* Mobile menu button */}
        <button
          onClick={() => setSidebarOpen(true)}
          className="lg:hidden fixed bottom-4 right-4 z-50 p-3 rounded-full shadow-lg transition-colors"
          style={{
            background: 'var(--brand)',
            color: 'white',
          }}
          aria-label="Open menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        {/* Content */}
        <main className="flex-1 flex flex-col min-w-0">
          {children}
        </main>
      </div>
    </div>
  );
}


