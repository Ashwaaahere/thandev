'use client';
import Link from 'next/link';
import { useState } from 'react';
import ThemeToggle from './ThemeToggle';

export default function Navbar() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const closeMobileMenu = () => {
    setIsMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 backdrop-blur border-b card-border"
        style={{ background: 'color-mix(in oklab, var(--bg) 70%, transparent)' }}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
          <span className="text-lg font-semibold tracking-tight">Thandev</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden gap-6 text-sm opacity-80 md:flex">
          <Link href="/news" className="hover:opacity-100">News</Link>
          <Link href="/exploits" className="hover:opacity-100">Exploit feed</Link>
          <Link href="/docs" className="hover:opacity-100">Docs</Link>
        </nav>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          
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
            <Link
              href="/news"
              onClick={closeMobileMenu}
              className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
            >
              📰 News
            </Link>
            <Link
              href="/exploits"
              onClick={closeMobileMenu}
              className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
            >
              🔍 Exploit feed
            </Link>
            <Link
              href="/docs"
              onClick={closeMobileMenu}
              className="block px-4 py-3 rounded-lg hover:bg-white/10 transition-colors text-sm font-medium"
            >
              📚 Docs
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
