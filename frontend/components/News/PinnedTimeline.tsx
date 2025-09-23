// components/PinnedTimeline.tsx
'use client';

import Link from 'next/link';

type Item = {
  id?: string;
  url: string;
  title: string;
  source: string;
  publishedAt?: string; // already formatted, or raw ISO if you prefer
};

export default function PinnedTimeline({ items }: { items: Item[] }) {
  const list = (items ?? []).slice(0, 15); // show more to avoid empty space

  return (
    <aside
      className="
        sticky top-24
        rounded-2xl border card-border bg-[var(--surface)]
        shadow-soft
        overflow-hidden
      "
    >
      {/* Title */}
      <div className="flex items-center gap-2 px-4 py-3 text-sm font-medium text-[var(--fg)]/80">
        <span className="inline-flex h-2.5 w-2.5 rounded-full bg-rose-500 animate-pulse" />
        Top 5 of the week
      </div>

      {/* Scroll container */}
      <div
        className="
          max-h-[calc(100vh-160px)]
          overflow-y-auto pr-1
          scrollbar-thin
          timeline-fade-after   /* adds gentle bottom fade */
        "
      >
        <ol className="relative">
          {/* spine */}
          <span
            aria-hidden
            className="pointer-events-none absolute left-[22px] top-0 h-full w-px bg-[var(--hairline)]"
          />

          {list.map((it, i) => (
            <li key={it.id ?? it.url} className="relative">
              {/* dot */}
              <span className="absolute left-[14px] top-4 h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-[var(--surface)]" />

              <Link
                href={`/news/a/${encodeURIComponent(it.url)}`}
                className="
                  group block rounded-lg px-8 py-3
                  hover:bg-[var(--surface-2)]
                  transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]
                "
              >
                <div className="flex items-start gap-2">
                  <span className="text-[10px] mt-1 rounded bg-[var(--hairline)]/35 px-1.5 py-0.5 text-[var(--muted)]">
                    {it.source}
                  </span>
                  <span className="line-clamp-2 text-sm leading-snug text-[var(--fg)] group-hover:underline">
                    {it.title}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </aside>
  );
}
