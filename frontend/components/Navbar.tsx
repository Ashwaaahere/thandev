'use client';
import Link from 'next/link';
import Image from 'next/image';
import { useState, useEffect } from 'react';

export default function Navbar() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    // Check if user is logged in
    const userData = localStorage.getItem('thandev-user');
    if (userData) {
      setUser(JSON.parse(userData));
    }
  }, []);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('thandev-user');
    setUser(null);
    window.location.href = '/';
  };

  return (
    <header className="sticky top-0 z-50 backdrop-blur border-b card-border"
        style={{ background: 'color-mix(in oklab, var(--bg) 70%, transparent)' }}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <Image 
            src="/logo.png" 
            alt="Thandev Logo" 
            width={28} 
            height={28} 
            className="flex-shrink-0"
            style={{ objectFit: 'contain' }}
          />
          <span className="text-lg font-semibold tracking-tight">Thandev</span>
          <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 uppercase tracking-wide">Beta</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden gap-6 text-sm opacity-80 md:flex">
          {user && <Link href="/dashboard" className="hover:opacity-100">Dashboard</Link>}
          <Link href="/news" className="hover:opacity-100">News</Link>
          {/* Exploit feed button disabled but page kept */}
          {/* <Link href="/exploits" className="hover:opacity-100">Exploit feed</Link> */}
          <Link href="/dashboard/scan" className="hover:opacity-100">Security Scan</Link>
          <Link href="/docs" className="hover:opacity-100">Docs</Link>
        </nav>

        <div className="flex items-center gap-3">
          
          {/* User Menu */}
          {user ? (
            <div className="flex items-center gap-3">
              <span className="hidden md:block text-sm text-[var(--muted)]">
                Welcome, {user.name || user.email}
              </span>
              <button
                onClick={handleLogout}
                className="px-3 py-1 text-sm text-[var(--muted)] hover:text-[var(--fg)] transition-colors"
              >
                Logout
              </button>
            </div>
          ) : (
                   <div className="hidden md:flex items-center gap-3">
                     <Link href="/auth" className="px-3 py-1 text-sm bg-gradient-to-r from-cyan-500 to-blue-500 text-white rounded-lg hover:from-cyan-600 hover:to-blue-600 transition-colors shadow-lg hover:shadow-xl">
                       Sign In / Sign Up
                     </Link>
                   </div>
          )}
          
          {/* Mobile Menu Toggle */}
          <button
            onClick={toggleMobileMenu}
            className="md:hidden p-2 rounded-lg hover:bg-white/10 transition-colors"
            aria-label="Toggle mobile menu"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              {isMobileMenuOpen ? (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              ) : (
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile Navigation Menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-white/10 bg-[var(--bg)]/95 backdrop-blur">
          <nav className="px-6 py-4 space-y-3">
            {user && (
              <Link
                href="/dashboard"
                onClick={closeMobileMenu}
                className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
              >
                📊 Dashboard
              </Link>
            )}
            <Link
              href="/news"
              onClick={closeMobileMenu}
              className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
            >
              📰 News
            </Link>
            {/* Exploit feed button disabled but page kept */}
            {/* <Link
              href="/exploits"
              onClick={closeMobileMenu}
              className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
            >
              🔍 Exploit feed
            </Link> */}
                   <Link
                     href="/dashboard/scan"
                     onClick={closeMobileMenu}
                     className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
                   >
                     🛡️ Surface Scan
                   </Link>
            <Link
              href="/docs"
              onClick={closeMobileMenu}
              className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
            >
              📚 Docs
            </Link>
            
            {/* Mobile Auth Options */}
            {user ? (
              <>
                <div className="px-4 py-3 text-sm text-[var(--muted)]">
                  Welcome, {user.name || user.email}
                </div>
                <button
                  onClick={() => {
                    handleLogout();
                    closeMobileMenu();
                  }}
                  className="block w-full text-left px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
                >
                  🚪 Logout
                </button>
              </>
                   ) : (
                     <Link
                       href="/auth"
                       onClick={closeMobileMenu}
                       className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
                     >
                       🔐 Sign In / Sign Up
                     </Link>
                   )}
          </nav>
        </div>
      )}
    </header>
  );
}
