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
        rounded-2xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]
        shadow-xl shadow-[var(--brand)]/10
        overflow-hidden
        flex flex-col
        h-full
        pinned-timeline
        backdrop-blur-sm
      "
    >
      {/* Title */}
      <div className="flex items-center gap-2 px-4 py-3 text-sm font-medium text-[var(--fg)]/80 flex-shrink-0">
        <span className="inline-flex h-2.5 w-2.5 rounded-full bg-rose-500 animate-pulse" />
        Top 5 of the week
      </div>

      {/* Content container */}
      <div
        className="
          pr-1 pb-4
          flex-1
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
            <li key={it.id ?? it.url} className="relative timeline-item mb-2">
              {/* dot */}
              <span className="absolute left-[14px] top-4 h-2.5 w-2.5 rounded-full bg-amber-400 ring-2 ring-[var(--surface)]" />

              <Link
                href={`/news/a/${encodeURIComponent(it.url)}`}
                className="
                  group block rounded-lg px-8 py-4
                  hover:bg-[var(--surface-2)]
                  transition-colors duration-200
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]
                  w-full
                  min-h-[80px]
                "
              >
                <div className="flex items-start gap-2 h-full">
                  <span className="text-[10px] mt-1 rounded bg-[var(--hairline)]/35 px-1.5 py-0.5 text-[var(--muted)] flex-shrink-0">
                    {it.source}
                  </span>
                  <span className="text-sm leading-relaxed text-[var(--fg)] group-hover:underline flex-1">
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
