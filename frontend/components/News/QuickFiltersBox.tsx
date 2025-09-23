// components/News/QuickFiltersBox.tsx
"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export type FilterItem = { label: string; q: Record<string, string> };

type Props = {
  className?: string;
  title?: string;
  filters?: FilterItem[];
};

const defaults: FilterItem[] = [
  { label: "The Hacker News", q: { source: "The Hacker News" } },
  { label: "BleepingComputer", q: { source: "BleepingComputer" } },
  { label: "SANS ISC Diary", q: { source: "SANS ISC Diary" } },
];

export default function QuickFiltersBox({
  className,
  title = "Quick filters",
  filters = defaults,
}: Props) {
  const pathname = usePathname();
  const search = useSearchParams();

  const clearHref = (() => {
    const p = new URLSearchParams(search.toString());
    p.delete("source");
    return `${pathname}?${p.toString()}`;
  })();

  const pillHref = (q: Record<string, string>) => {
    const p = new URLSearchParams(search.toString());
    // apply single-source filter (you can extend to multi)
    if (q.source) p.set("source", q.source);
    return `${pathname}?${p.toString()}`;
  };

  return (
    <section
      className={clsx(
        "rounded-xl bg-[var(--surface)] border card-border shadow-soft p-3",
        className
      )}
    >
      <h3 className="mb-2 text-sm font-semibold text-[var(--fg)]">{title}</h3>
      <div className="flex flex-wrap gap-2">
        {filters.map((f) => (
          <Link
            key={f.label}
            href={pillHref(f.q)}
            className="rounded-full border card-border bg-white/5 dark:bg-white/10 px-2.5 py-1 text-xs text-[var(--fg)] hover:bg-white/10 dark:hover:bg-white/15 transition-colors"
          >
            {f.label}
          </Link>
        ))}
        <Link
          href={clearHref}
          className="rounded-full border card-border bg-transparent px-2.5 py-1 text-xs text-[var(--muted)] hover:bg-white/5 transition-colors"
        >
          Clear
        </Link>
      </div>
    </section>
  );
}
