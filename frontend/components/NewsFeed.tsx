'use client';

import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

type Item = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string;
  summary: string;
  category: 'cyber' | 'ai' | 'tech';
};

const tabs = [
  { key: 'all', label: 'All' },
  { key: 'cyber', label: 'Cybersecurity' },
  { key: 'ai', label: 'AI' },
  { key: 'tech', label: 'Tech' },
] as const;

export default function NewsFeed() {
  const [active, setActive] = useState<(typeof tabs)[number]['key']>('all');
  const [q, setQ] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const seen = useRef<Set<string>>(new Set());

  const fetchFeed = async (tabKey: string, query: string) => {
    setLoading(true);
    setErr(null);
    try {
      const params = new URLSearchParams();
      if (tabKey !== 'all') params.set('category', tabKey);
      if (query) params.set('q', query);
      const res = await fetch(`/api/news?${params.toString()}`, { cache: 'no-store' });
      if (!res.ok) throw new Error('Failed to load feed');
      const data = (await res.json()) as { items: Item[] };

      // initialize seen set on first load
      if (items.length === 0 && seen.current.size === 0) {
        data.items.forEach((i) => seen.current.add(i.id));
      }
      setItems(data.items);
    } catch (e: any) {
      setErr(e.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  // initial + tab change
  useEffect(() => {
    fetchFeed(active, q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  // search debounce
  useEffect(() => {
    const t = setTimeout(() => fetchFeed(active, q), 350);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, active]);

  // live polling every 25s → prepend new items
  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const params = new URLSearchParams();
        if (active !== 'all') params.set('category', active);
        if (q) params.set('q', q);
        const res = await fetch(`/api/news?${params.toString()}`, { cache: 'no-store' });
        if (!res.ok) return;
        const data = (await res.json()) as { items: Item[] };

        // find truly new
        const incoming = data.items.filter((i) => !seen.current.has(i.id));
        if (incoming.length) {
          incoming.forEach((i) => seen.current.add(i.id));
          // prepend new, then keep rest (de-dup)
          const map = new Map<string, Item>();
          [...incoming, ...items].forEach((i) => map.set(i.id, i));
          setItems(Array.from(map.values()).slice(0, 120));
        }
      } catch {}
    }, 25000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, q, items]);

  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    return `${d}d ago`;
  };

  const filtered = items; // server already filtered; keep here for future client filters
  const empty = !loading && !err && filtered.length === 0;

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Live News Feed</h1>
        <div className="flex items-center gap-2">
          <div className="rounded-2xl bg-neutral-900 p-1.5 shadow-inner border border-neutral-800">
            <div className="flex gap-1">
              {tabs.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setActive(t.key)}
                  className={`px-3 py-1.5 rounded-xl text-sm transition ${
                    active === t.key
                      ? 'bg-neutral-700 text-white'
                      : 'text-neutral-300 hover:bg-neutral-800'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search titles, sources…"
            className="h-10 w-60 rounded-xl border border-neutral-800 bg-neutral-900 px-3 text-sm text-neutral-200 outline-none focus:ring-2 focus:ring-neutral-600"
          />
        </div>
      </div>

      {/* Ticker */}
      <div className="mt-4 overflow-hidden rounded-xl border border-neutral-800 bg-neutral-950">
        <div className="flex gap-6 animate-[scrollX_30s_linear_infinite] whitespace-nowrap px-4 py-2 text-sm text-neutral-300"
             style={{ maskImage: 'linear-gradient(90deg, transparent, black 10%, black 90%, transparent)' }}>
          {filtered.slice(0, 5).map((it) => (
            <span key={it.id} className="inline-flex items-center gap-2">
              <span className="rounded-md bg-neutral-800 px-2 py-0.5 text-xs">{it.source}</span>
              <a href={it.url} target="_blank" rel="noreferrer" className="hover:underline">{it.title}</a>
            </span>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="mt-6">
        {loading && (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-32 rounded-2xl border border-neutral-800 bg-neutral-950 animate-pulse" />
            ))}
          </div>
        )}

        {err && (
          <div className="rounded-xl border border-red-800 bg-red-950/40 p-4 text-red-200">
            {err}
          </div>
        )}

        {empty && (
          <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-6 text-neutral-300">
            No articles found. Try a different tab or search term.
          </div>
        )}

        {!loading && !err && filtered.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2">
            {filtered.map((it, idx) => (
              <motion.a
                key={it.id}
                href={it.url}
                target="_blank"
                rel="noreferrer"
                className="group block rounded-2xl border border-neutral-800 bg-neutral-950 p-4 shadow-sm hover:border-neutral-700"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.01, duration: 0.22 }}
              >
                <div className="flex items-center justify-between">
                  <span className="rounded-md bg-neutral-800 px-2 py-0.5 text-xs text-neutral-200">
                    {it.source}
                  </span>
                  <span className="text-xs text-neutral-400">{timeAgo(it.publishedAt)}</span>
                </div>
                <h3 className="mt-2 line-clamp-2 text-base font-medium text-neutral-100 group-hover:underline">
                  {it.title}
                </h3>
                <p className="mt-1 line-clamp-3 text-sm text-neutral-400">{it.summary}</p>
                <div className="mt-3 text-xs text-neutral-500">Open →</div>
              </motion.a>
            ))}
          </div>
        )}
      </div>

      <style jsx global>{`
        @keyframes scrollX {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
