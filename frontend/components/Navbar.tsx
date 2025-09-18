'use client';
import Link from 'next/link';

export default function Navbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-white/10 bg-slate-950/70 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 text-slate-100">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
          <span className="text-lg font-semibold tracking-tight">Thandev</span>
        </Link>

        <nav className="hidden gap-6 text-sm text-slate-300 md:flex">
          <Link href="/news" className="hover:text-white">News</Link>
          <Link href="/docs" className="hover:text-white">Docs</Link>
          <Link href="/pricing" className="hover:text-white">Pricing</Link>
        </nav>

        <div className="flex items-center gap-3">
          <Link href="/signin" className="rounded-xl px-3 py-2 text-sm text-slate-300 hover:text-white">Sign in</Link>
          <Link href="/signup" className="rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-900 hover:bg-slate-200">Get started</Link>
        </div>
      </div>
    </header>
  );
}
