'use client';

import { useState } from 'react';
import Link from 'next/link';
import GlobalSearch from './GlobalSearch';
import NotificationBell from './NotificationBell';

interface DashboardHeaderProps {
  user: any;
  onMenuClick: () => void;
  showLogo?: boolean;
}

export default function DashboardHeader({ user, onMenuClick, showLogo = false }: DashboardHeaderProps) {
  const [showUserMenu, setShowUserMenu] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('thandev-user');
    localStorage.removeItem('thandev-scan-limit');
    window.location.href = '/';
  };

  // Get user initials for avatar
  const getInitials = () => {
    if (user?.name) {
      const names = user.name.split(' ');
      if (names.length >= 2) {
        return (names[0].charAt(0) + names[names.length - 1].charAt(0)).toUpperCase();
      }
      return user.name.substring(0, 2).toUpperCase();
    }
    if (user?.email) {
      return user.email.substring(0, 2).toUpperCase();
    }
    return 'U';
  };

  // Get truncated name (first name + last initial)
  const getDisplayName = () => {
    if (user?.name) {
      const names = user.name.split(' ');
      if (names.length >= 2) {
        return `${names[0]} ${names[names.length - 1].charAt(0)}.`;
      }
      return user.name;
    }
    return 'User';
  };

  return (
    <header className="border-b backdrop-blur-sm" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
      <div className="px-6" style={{ height: '64px', display: 'flex', alignItems: 'center' }}>
        <div className="flex items-center justify-between gap-4 w-full">
          {/* Left side - Menu button and logo */}
          <div className="flex items-center gap-3" style={{ height: '40px' }}>
            <button
              onClick={onMenuClick}
              className="lg:hidden p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center justify-center"
              style={{ color: 'var(--fg)', height: '40px', width: '40px' }}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            
            {/* Logo - only visible when sidebar is closed */}
            {showLogo && (
              <div className="flex items-center gap-2.5" style={{ height: '40px' }}>
                <div className="h-7 w-7 rounded-lg shadow-lg flex-shrink-0" style={{ background: 'var(--brand)' }} />
                <span className="text-lg font-bold" style={{ color: 'var(--fg)', lineHeight: '1' }}>Thandev</span>
              </div>
            )}
          </div>

          {/* Center - Search */}
          <div className="flex flex-1 max-w-lg" style={{ height: '40px' }}>
            <GlobalSearch />
          </div>

          {/* Right side - Notifications and user menu */}
          <div className="flex items-center gap-3" style={{ height: '40px' }}>
            {/* Notifications */}
            <NotificationBell />

            {/* User Menu */}
            <div className="relative" style={{ height: '40px' }}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                style={{ height: '40px' }}
              >
                <div className="hidden md:block text-left">
                  <p className="text-sm font-medium text-white" style={{ lineHeight: '1.2' }}>
                    {getDisplayName()}
                  </p>
                  <p className="text-xs text-gray-400" style={{ lineHeight: '1.2' }}>
                    {user?.email || 'No email'}
                  </p>
                </div>
                <div className="h-9 w-9 rounded-full flex items-center justify-center text-sm font-semibold text-white bg-blue-500 flex-shrink-0">
                  {getInitials()}
                </div>
                <svg className="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-48 rounded-lg shadow-lg border z-50" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
                  <div className="py-1">
                    <Link href="/dashboard/profile" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" style={{ color: 'var(--fg)' }}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      Profile Settings
                    </Link>
                    <Link href="/dashboard/settings" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" style={{ color: 'var(--fg)' }}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      Settings
                    </Link>
                    <div className="border-t my-1" style={{ borderColor: 'var(--border)' }}></div>
                    <button
                      onClick={handleLogout}
                      className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors w-full text-left"
                      style={{ color: 'var(--fg)' }}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
