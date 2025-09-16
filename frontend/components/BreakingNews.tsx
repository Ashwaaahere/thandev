'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

type Item = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string;
  summary: string;
  image?: string | null;
  category: 'cyber' | 'ai' | 'tech';
};

export default function BreakingNews() {
  const [items, setItems] = useState<Item[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    try {
      const res = await fetch('/api/news?strict=1&category=cyber&breaking=1&limit=8', { cache: 'no-store' });
      if (!res.ok) throw new Error('Failed to load breaking news');
      const data = await res.json();
      setItems(data.items as Item[]);
    } catch (e: any) {
      setErr(e.message || 'Error');
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000); // refresh every 30s
    return () => clearInterval(t);
  }, []);

  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="relative inline-flex">
          {/* blinking red dot */}
          <span className="absolute inline-flex h-2.5 w-2.5 animate-ping rounded-full bg-red-500 opacity-75"></span>
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500"></span>
        </span>
        <h3 className="text-sm font-semibold">Live Breaking</h3>
      </div>

      {err && <div className="rounded-lg border border-red-800 bg-red-950/40 p-3 text-xs text-red-200">{err}</div>}

      {!err && (
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
          {items.map((it, i) => (
            <motion.a
              key={it.id}
              href={it.url}
              target="_blank"
              rel="noreferrer"
              className="group overflow-hidden rounded-xl border border-white/10 bg-slate-950/60"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03, duration: 0.25 }}
            >
              {/* thumb */}
              <div className="aspect-[16/9] w-full overflow-hidden bg-black/40">
                {it.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={it.image}
                    alt=""
                    className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                  />
                ) : null}
              </div>
              <div className="p-3">
                <div className="flex items-center justify-between">
                  <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-300">
                    {it.source}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {timeAgo(it.publishedAt)}
                  </span>
                </div>
                <div className="mt-1 line-clamp-2 text-sm font-medium text-slate-100 group-hover:underline">
                  {it.title}
                </div>
              </div>
            </motion.a>
          ))}
        </div>
      )}
    </div>
  );
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
