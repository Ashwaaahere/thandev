// app/news/page.tsx
import NewsClientWrapper from "@/components/News/NewsClientWrapper";
import RightSidebar from "@/components/News/RightSidebar";
import { calculateSourceCounts } from "@/components/News/TopSourcesBox";
import { Suspense } from "react";

export const metadata = {
  title: "Cybersecurity News Feed - Real-time Threat Intelligence",
  description: "Stay updated with the latest cybersecurity news, vulnerabilities, and security insights from trusted sources including The Hacker News, BleepingComputer, Dark Reading, and SANS ISC Diary.",
  keywords: [
    "cybersecurity news",
    "security threats",
    "vulnerability news",
    "cyber attacks",
    "security updates",
    "threat intelligence",
    "CVE news",
    "exploit news",
    "security advisories"
  ],
  openGraph: {
    title: "Cybersecurity News Feed - Real-time Threat Intelligence",
    description: "Stay updated with the latest cybersecurity news, vulnerabilities, and security insights from trusted sources.",
    type: "website",
    url: "https://thandev.com/news",
    images: [
      {
        url: "/og-news.png",
        width: 1200,
        height: 630,
        alt: "Thandev Cybersecurity News Feed",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Cybersecurity News Feed - Real-time Threat Intelligence",
    description: "Stay updated with the latest cybersecurity news, vulnerabilities, and security insights from trusted sources.",
    images: ["/og-news.png"],
  },
  alternates: {
    canonical: "/news",
  },
};

export default function NewsPage() {
  // Remove server-side data fetching - let client components handle it

  // Static structured data for SEO
  const newsStructuredData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Cybersecurity News Feed",
    "description": "Real-time cybersecurity news aggregation from trusted sources",
    "url": "https://thandev.com/news",
    "mainEntity": {
      "@type": "ItemList",
      "numberOfItems": 0,
      "itemListElement": []
    }
  };

  return (
    <>
      {/* Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(newsStructuredData),
        }}
      />
      
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Hero section */}
      <section className="mb-12 text-center">
        <div className="mb-6">
          <h1 className="text-4xl font-bold text-[var(--fg)] mb-4">
            Security News
          </h1>
          <p className="text-lg text-[var(--muted)] max-w-2xl mx-auto">
            Stay updated with the latest cybersecurity news, vulnerabilities, and security insights from trusted sources.
          </p>
        </div>
      </section>

      {/* Stats bar */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">-</div>
            <div className="text-sm text-[var(--muted)] font-medium">Articles Shown</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">-</div>
            <div className="text-sm text-[var(--muted)] font-medium">Total Available</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">Live</div>
            <div className="text-sm text-[var(--muted)] font-medium">Real-time Updates</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">-</div>
            <div className="text-sm text-[var(--muted)] font-medium">Sources</div>
          </div>
        </div>
      </section>

      {/* FEED + RIGHT SIDEBAR */}
      <section className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        <div className="lg:col-span-3 space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-[var(--fg)]">Security News Feed</h2>
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
              <span>Live updates</span>
            </div>
          </div>
          <NewsClientWrapper initialNews={[]} totalCount={0} />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar pinned={[]} latest={[]} />
        </aside>
      </section>
      </main>
    </>
  );
}
