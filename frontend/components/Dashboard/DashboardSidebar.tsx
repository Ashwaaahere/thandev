'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface DashboardSidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  sidebarOpen?: boolean;
  setSidebarOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  showLogo?: boolean;
}

export default function DashboardSidebar({ 
  isOpen: propIsOpen, 
  onClose: propOnClose, 
  sidebarOpen: propSidebarOpen,
  setSidebarOpen: propSetSidebarOpen,
  showLogo = true 
}: DashboardSidebarProps) {
  // Support both prop patterns: isOpen/onClose and sidebarOpen/setSidebarOpen
  const [internalOpen, setInternalOpen] = React.useState(false);
  
  // Determine which props to use
  const isOpen = propSidebarOpen ?? propIsOpen ?? internalOpen;
  const handleClose = propSetSidebarOpen 
    ? () => propSetSidebarOpen(false)
    : (propOnClose ?? (() => setInternalOpen(false)));
  const pathname = usePathname();

  // CORE PLATFORM navigation items
  const corePlatformNav = [
    { name: 'Overview', href: '/dashboard', icon: 'M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0h8v8h-8v-8z' }, // Grid icon (4 squares in 2x2)
    { name: 'Projects', href: '/projects', icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-4l-2-2H5a2 2 0 00-2 2z' }, // Folder icon
    { name: 'Security Scanner', href: '/dashboard/scan', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 8c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z' }, // Target/scanner icon (circle with dot in center)
    { name: 'History', href: '/dashboard/history', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' }, // Clock icon
    { name: 'Reports', href: '/dashboard/reports', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' }, // Bar chart icon (3 vertical bars)
    { name: 'Vulnerabilities', href: '/dashboard/vulnerabilities', icon: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z' }, // Bug icon
  ];

  // ACCOUNT navigation items
  const accountNav = [
    { name: 'Profile', href: '/dashboard/profile', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
    { name: 'Settings', href: '/dashboard/settings', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' },
    { name: 'Help & Support', href: '/dashboard/support', icon: 'M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={handleClose}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
      `} style={{ background: 'var(--surface)' }}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          {showLogo && (
            <div className="flex items-center gap-3 px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
              <div className="h-8 w-8 rounded-lg shadow-lg" style={{ background: 'var(--brand)' }} />
              <span className="text-xl font-bold" style={{ color: 'var(--fg)' }}>Thandev</span>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 px-4 py-6 space-y-6 overflow-y-auto">
            {/* CORE PLATFORM Section */}
            <div>
              <h3 className="px-3 mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                CORE PLATFORM
              </h3>
              <div className="space-y-1">
                {corePlatformNav.map((item) => {
                  // Check if pathname starts with item.href for active state (handles /projects and /projects/[id])
                  const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname?.startsWith(item.href));
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={{
                        background: isActive ? '#3b82f6' : 'transparent',
                        color: isActive ? 'white' : 'white'
                      }}
                      onClick={() => handleClose()}
                      aria-current={isActive ? 'page' : undefined}
                    >
                      <svg 
                        className="w-5 h-5" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                        style={{
                          color: isActive ? 'white' : '#9ca3af'
                        }}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                      </svg>
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            </div>

            {/* ACCOUNT Section */}
            <div>
              <h3 className="px-3 mb-3 text-xs font-semibold uppercase tracking-wider text-gray-400">
                ACCOUNT
              </h3>
              <div className="space-y-1">
                {accountNav.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={{
                        background: isActive ? '#3b82f6' : 'transparent',
                        color: isActive ? 'white' : 'white'
                      }}
                      onClick={() => handleClose()}
                    >
                      <svg 
                        className="w-5 h-5" 
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                        style={{
                          color: isActive ? 'white' : '#9ca3af'
                        }}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
                      </svg>
                      {item.name}
                    </Link>
                  );
                })}
              </div>
            </div>
          </nav>

          {/* Footer */}
          <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
            <div className="text-xs" style={{ color: 'var(--muted)' }}>
              <p>Thandev v1.0.0</p>
              <p>Security Testing Platform</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
