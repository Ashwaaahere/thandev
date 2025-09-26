// components/News/TopSourcesBox.tsx
import clsx from "clsx";

export type SourceCount = { name: string; count: number };

type Props = {
  className?: string;
  sources?: SourceCount[];
  title?: string;
};

// Helper function to calculate source counts from news items
export function calculateSourceCounts(newsItems: any[]): SourceCount[] {
  const sourceMap = new Map<string, number>();
  
  newsItems.forEach(item => {
    if (item.source) {
      const currentCount = sourceMap.get(item.source) || 0;
      sourceMap.set(item.source, currentCount + 1);
    }
  });
  
  return Array.from(sourceMap.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 5); // Show top 5 sources
}

export default function TopSourcesBox({
  className,
  sources = [],
  title = "Top sources this week",
}: Props) {
  // Handle empty sources gracefully for SSR
  if (!sources || sources.length === 0) {
    return (
      <section
        className={clsx(
          "rounded-xl bg-[var(--surface)] border card-border shadow-soft p-3",
          className
        )}
      >
        <h3 className="mb-2 text-sm font-semibold text-[var(--fg)]">{title}</h3>
        <div className="space-y-2">
          <div className="text-xs text-[var(--muted)] text-center py-4">
            Loading source data...
          </div>
        </div>
      </section>
    );
  }

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
