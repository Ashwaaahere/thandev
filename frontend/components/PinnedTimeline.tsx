// components/PinnedTimeline.tsx
'use client';

import Link from 'next/link';

type Item = {
  id?: string | number;
  url: string;
  title: string;
  source?: string;
  publishedAt?: string; // ISO
};

function formatAgo(iso?: string) {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  const now = Date.now();
  const m = Math.max(0, Math.round((now - t) / 60000));
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}

export default function PinnedTimeline({ items }: { items: Item[] }) {
  return (
    <div className="rounded-2xl border card-border bg-[var(--surface)] shadow-soft p-5 sm:p-6">
      <div className="mb-4 flex items-center gap-2">
        <span className="inline-flex h-3 w-3 animate-pulse rounded-full bg-red-500" />
        <span className="text-sm font-semibold text-slate-300 dark:text-slate-200">
          Top 5 of the week
        </span>
      </div>

      <ol className="relative ml-4 space-y-6 border-l border-slate-700/30 dark:border-slate-200/10">
        {items.map((it, i) => (
          <li key={it.id ?? it.url} className="pl-4">
            {/* timeline dot */}
            <span className="absolute -left-[7px] mt-1.5 inline-block h-3 w-3 rounded-full border-2 border-slate-900 bg-amber-400 dark:border-slate-800" />

            {/* time */}
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {formatAgo(it.publishedAt)}
            </div>

            {/* title + source */}
            <div className="mt-1">
              {it.source && (
                <span className="mr-2 inline-flex rounded bg-slate-200/80 px-1.5 py-0.5 text-[10px] font-medium text-slate-700 dark:bg-white/10 dark:text-slate-200">
                  {it.source}
                </span>
              )}

              <Link
                href={`/news/a/${encodeURIComponent(it.url)}`}
                className="block text-[15px] font-medium leading-snug hover:underline underline-offset-2"
              >
                {it.title}
              </Link>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
