'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';

export default function NotFound() {
  const [q, setQ] = useState('');
  const router = useRouter();

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    router.push(`/news?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <main className="relative grid min-h-[calc(100vh-120px)] place-items-center overflow-hidden bg-slate-950 px-6 py-16 text-slate-100">
      {/* aurora / glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[720px] w-[1200px] -translate-x-1/2 rounded-full opacity-30 blur-3xl"
        style={{
          background:
            'radial-gradient(50% 50% at 50% 50%, rgba(56,189,248,0.25) 0%, rgba(99,102,241,0.25) 30%, rgba(15,23,42,0) 70%)',
        }}
      />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.08),transparent_60%)]" />

      <section className="relative z-10 mx-auto w-full max-w-2xl text-center">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300"
        >
          <span className="relative inline-flex">
            <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-red-500 opacity-75"></span>
            <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500"></span>
          </span>
          Page not found
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.05 }}
          className="mt-4 text-5xl font-extrabold tracking-tight md:text-6xl"
        >
          4<span className="bg-gradient-to-r from-cyan-400 to-indigo-500 bg-clip-text text-transparent">0</span>4
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.1 }}
          className="mx-auto mt-3 max-w-xl text-slate-300"
        >
          We couldn’t find that page. Try searching the news, or head back to safer ground.
        </motion.p>

        {/* search */}
        <motion.form
          onSubmit={onSearch}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.15 }}
          className="mx-auto mt-6 flex max-w-lg items-center gap-2"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search security news (e.g., CVE-2025-1234)…"
            className="h-12 flex-1 rounded-xl border border-white/10 bg-slate-900/80 px-4 text-sm text-slate-100 outline-none placeholder:text-slate-400 focus:border-slate-400"
          />
          <button
            type="submit"
            className="h-12 rounded-xl bg-white px-5 text-sm font-semibold text-slate-900 hover:bg-slate-200"
          >
            Search
          </button>
        </motion.form>

        {/* actions */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.2 }}
          className="mt-6 flex flex-wrap justify-center gap-3"
        >
          <Link
            href="/"
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm hover:bg-white/10"
          >
            ← Back to Home
          </Link>
          <Link
            href="/news"
            className="rounded-xl bg-gradient-to-r from-cyan-400 to-indigo-500 px-4 py-2 text-sm font-semibold text-slate-900 hover:opacity-90"
          >
            Go to News
          </Link>
          <Link
            href="/docs"
            className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm hover:bg-white/10"
          >
            Read Docs
          </Link>
        </motion.div>

        {/* subtle code bar */}
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: '16rem' }}
          transition={{ duration: 1.2, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut' }}
          className="mx-auto mt-8 h-1 rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500"
        />
      </section>
    </main>
  );
}
