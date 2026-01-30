'use client';

import Link from 'next/link';
import Image from 'next/image';
import { useSession } from 'next-auth/react';
import DocsSearch from './DocsSearch';

export default function DocsHeader() {
  const { data: session, status } = useSession();

  return (
    <header
      className="sticky top-0 z-50 border-b backdrop-blur-sm"
      style={{
        background: 'color-mix(in oklab, var(--bg) 95%, transparent)',
        borderColor: 'var(--border)',
      }}
    >
      <div className="mx-auto flex max-w-[1920px] items-center justify-between px-6 py-4">
        {/* Logo and Brand */}
        <Link href="/" className="flex items-center gap-2">
          <Image
            src="/logo.png"
            alt="Thandev Logo"
            width={28}
            height={28}
            className="flex-shrink-0"
            style={{ objectFit: 'contain' }}
          />
          <span className="text-lg font-semibold tracking-tight" style={{ color: 'var(--fg)' }}>
            Thandev
          </span>
          <span
            className="text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide"
            style={{
              background: 'rgba(59, 130, 246, 0.3)',
              color: 'rgb(191, 219, 254)',
              border: '1px solid rgba(96, 165, 250, 0.5)',
            }}
          >
            Beta
          </span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden gap-6 text-sm md:flex" style={{ color: 'var(--fg)' }}>
          <Link href="/news" className="hover:opacity-80 transition-opacity">
            News
          </Link>
          <Link href="/dashboard/scan" className="hover:opacity-80 transition-opacity">
            Security Scan
          </Link>
          <Link href="/docs" className="hover:opacity-80 transition-opacity font-medium">
            Docs
          </Link>
        </nav>

        {/* Search and Auth */}
        <div className="flex items-center gap-4">
          {/* Search Bar */}
          <div className="hidden lg:block w-64">
            <DocsSearch
              className="w-full"
              onSelect={(item) => {
                window.location.href = item.href;
              }}
            />
          </div>

          {/* Sign In Button */}
          {status === 'loading' ? (
            <div className="px-4 py-2 text-sm rounded-lg" style={{ background: 'var(--surface)' }}>
              <span style={{ color: 'var(--muted)' }}>Loading...</span>
            </div>
          ) : session ? (
            <Link
              href="/dashboard"
              className="px-4 py-2 text-sm rounded-lg transition-colors"
              style={{
                background: 'var(--brand)',
                color: 'white',
              }}
            >
              Dashboard
            </Link>
          ) : (
            <Link
              href="/auth"
              className="px-4 py-2 text-sm rounded-lg transition-colors flex items-center gap-2"
              style={{
                background: 'var(--brand)',
                color: 'white',
              }}
            >
              Sign In
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}

