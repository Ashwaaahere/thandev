// components/News/TopSourcesBox.tsx
"use client";

import clsx from "clsx";

export type SourceCount = { name: string; count: number };

type Props = {
  className?: string;
  sources?: SourceCount[];
  title?: string;
};

const defaultSources: SourceCount[] = [
  { name: "The Hacker News", count: 37 },
  { name: "BleepingComputer", count: 12 },
  { name: "SANS ISC Diary", count: 10 },
];

export default function TopSourcesBox({
  className,
  sources = defaultSources,
  title = "Top sources this week",
}: Props) {
  const max = Math.max(...sources.map((s) => s.count), 1);

  return (
    <section
      className={clsx(
        "rounded-xl bg-[var(--surface)] border card-border shadow-soft p-3",
        className
      )}
    >
      <h3 className="mb-2 text-sm font-semibold text-[var(--fg)]">{title}</h3>
      <div className="space-y-2">
        {sources.map((s) => (
          <div key={s.name}>
            <div className="flex items-center justify-between text-xs">
              <span className="truncate text-[var(--muted)]">{s.name}</span>
              <span className="ml-2 tabular-nums text-[var(--muted)]">{s.count}</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-white/5 dark:bg-white/10">
              <div
                className="h-1.5 rounded-full bg-[var(--brand)]"
                style={{ width: `${(s.count / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
