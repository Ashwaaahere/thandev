// app/news/page.tsx (only the layout section shown)
import { headers } from "next/headers";
import RightSidebar from "@/components/News/RightSidebar";
import NewsList from "./NewsList";

// Optionally precompute sidebar data server-side
const sidebarSources = [
  { name: "The Hacker News", count: 37 },
  { name: "BleepingComputer", count: 12 },
  { name: "SANS ISC Diary", count: 10 },
];
const sidebarFilters = [
  { label: "The Hacker News", q: { source: "The Hacker News" } },
  { label: "BleepingComputer", q: { source: "BleepingComputer" } },
  { label: "SANS ISC Diary", q: { source: "SANS ISC Diary" } },
];
async function getNews() {
  try {
    // Prefer explicit base from env, else infer from the incoming request
    const explicit = process.env.NEXT_PUBLIC_API_BASE;         // e.g. https://api.thandev.dev
    const h = headers();
    const proto = h.get("x-forwarded-proto") ?? "http";
    const host  = h.get("x-forwarded-host") ?? h.get("host") ?? "localhost:3000";
    const inferredBase = `${proto}://${host}`;
    const base = explicit || inferredBase;

    // Build a proper absolute URL
    const url = new URL("/api/news", base);
    url.searchParams.set("category", "cyber");

    const res = await fetch(url.toString(), { next: { revalidate: 60 } });
    if (!res.ok) {
      console.error("News fetch failed:", res.status, res.statusText);
      return []; // Return empty array on failure
    }

    const data = await res.json().catch(() => ({}));
    // Always return an array to keep the UI defensive
    return Array.isArray(data?.items) ? data.items : [];
  } catch (error) {
    console.error("News fetch error:", error);
    return []; // Return empty array on error
  }
}


export default async function NewsPage() {
  const latest = await getNews();
  const pinned = latest.slice(0, 5); // Derive pinned from latest (top 5 items)
  return (
    <main>
      <section className="relative">
        {/* hero glow backdrop kept as you had */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(50% 55% at 12% 0%, var(--orb-indigo) 0%, transparent 60%), radial-gradient(36% 50% at 96% 0%, var(--orb-emerald) 0%, transparent 60%)",
            opacity: 0.6,
            filter: "saturate(1.05) blur(12px)",
          }}
        />

        <div className="relative mx-auto max-w-7xl px-6 pt-10">
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">Latest News</h1>

            {/* main grid: content + fixed-width sidebar */}
            <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
              {/* left: content */}
              <div>
                <NewsList items={latest ?? []} />
              </div>

              {/* right: sidebar */}
              <RightSidebar pinned={pinned ?? []} latest={latest ?? []} />
            </div>
          </div>

        <div className="h-16" />
      </section>
    </main>
  );
}
