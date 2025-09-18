// app/news/page.tsx
import Link from "next/link";
import PinnedTop from "@/components/PinnedTop";
import { scoreItem, NewsItem } from "@/lib/importance";

const ORIGIN =
  process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

async function getNews(): Promise<{ pinned: NewsItem[]; latest: NewsItem[] }> {
  const url = `${ORIGIN}/api/news?strict=1&category=cyber`;
  const res = await fetch(url, { next: { revalidate: 60 } });
  if (!res.ok) return { pinned: [], latest: [] };

  const data = await res.json();
  const items: NewsItem[] = Array.isArray(data.items) ? data.items : [];

  // Rank by score, split top 5 vs the rest
  const ranked = [...items].sort((a, b) => scoreItem(b) - scoreItem(a));
  const pinned = ranked.slice(0, 5);
  const latest = ranked.slice(5, 41);

  return { pinned, latest };
}

export default async function NewsPage() {
  const { pinned, latest } = await getNews();

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <h1 className="mb-6 text-2xl font-semibold">Latest News</h1>

        {/* Pinned / Top 5 */}
        <PinnedTop items={pinned} />

        {/* All news */}
        <section className="mt-10">
          <div className="mb-3 text-[13px] font-semibold text-[var(--muted)]">All news</div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {latest.map((it) => {
              const id = encodeURIComponent(it.url);
              return (
                <Link
                  key={it.id ?? it.url}
                  href={`/news/a/${id}`}
                  className="group overflow-hidden rounded-2xl bg-[var(--surface)] border card-border shadow-soft"
                >
                  <div className="aspect-[16/9] w-full bg-[rgba(0,0,0,.05)] dark:bg-white/5">
                    {it.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={it.image}
                        alt=""
                        className="h-full w-full object-cover pointer-events-none group-hover:scale-[1.02] transition-transform duration-300"
                        loading="lazy"
                      />
                    ) : null}
                  </div>
                  <div className="p-3">
                    <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
                      {it.source ?? "Source"}
                    </div>
                    <h3 className="mt-1 line-clamp-2 text-sm font-semibold">
                      {it.title}
                    </h3>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}
