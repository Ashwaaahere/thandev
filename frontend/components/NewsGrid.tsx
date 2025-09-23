// components/NewsGrid.tsx
'use client';

import Link from 'next/link';
import { Item } from './types';
import { timeAgo, hostFromUrl } from './utils/format';
import { useMemo } from 'react';

export default function NewsGrid({ items }: { items: Item[] }) {
  const list = useMemo(() => items ?? [], [items]);

  return (
    <div className="grid gap-4 md:gap-6 sm:grid-cols-2 xl:grid-cols-3">
      {list.map((it) => {
        const id = encodeURIComponent(it.url);
        return (
          <Link
            key={it.id || it.url}
            href={`/news/a/${id}`}
            className="group block rounded-2xl border card-border bg-[var(--surface)] shadow-soft overflow-hidden hover:shadow-deep transition-shadow"
          >
            {/* image */}
            <div className="aspect-[16/9] bg-[rgba(0,0,0,.04)] dark:bg-white/5 overflow-hidden">
              {!!it.image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={it.image}
                  alt=""
                  loading="lazy"
                  className="h-full w-full object-cover scale-[1.02] transition-transform duration-300 group-hover:scale-[1.06]"
                />
              )}
            </div>

            {/* content */}
            <div className="p-4">
              <div className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
                <span className="inline-flex items-center rounded-full border px-2 py-0.5">{it.source}</span>
                <span>{timeAgo(it.publishedAt)}</span>
              </div>
              <h3 className="mt-2 line-clamp-2 font-semibold leading-snug tracking-tight">
                {it.title}
              </h3>
              {it.summary && (
                <p className="mt-1 line-clamp-2 text-[14px] text-[var(--muted)]">{it.summary}</p>
              )}
              <div className="mt-3 text-sm text-[var(--brand)]">{hostFromUrl(it.url)} →</div>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
