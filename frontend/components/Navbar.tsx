'use client';
import Link from 'next/link';
import ThemeToggle from './ThemeToggle';

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 backdrop-blur border-b card-border"
        style={{ background: 'color-mix(in oklab, var(--bg) 70%, transparent)' }}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
          <span className="text-lg font-semibold tracking-tight">Thandev</span>
        </Link>

        <nav className="hidden gap-6 text-sm opacity-80 md:flex">
          <Link href="/news" className="hover:opacity-100">News</Link>
          <Link href="/exploits" className="hover:opacity-100">Exploit feed</Link>
          <Link href="/pricing" className="hover:opacity-100">Docs</Link>
        </nav>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          {/* <Link href="/signin" className="rounded-xl px-3 py-2 text-sm opacity-80 hover:opacity-100">Sign in</Link>
          <Link href="/signup" className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-200">
            Get started
          </Link> */}
        </div>
      </div>
    </header>
  );
}
