// app/news/page.tsx
import NewsClient from "@/components/News/NewsClient";

export default function NewsPage() {
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

          {/* Use client component for data fetching */}
          <NewsClient />
        </div>

        <div className="h-16" />
      </section>
    </main>
  );
}
