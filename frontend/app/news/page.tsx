// app/news/page.tsx
import NewsClientWrapper from "@/components/News/NewsClientWrapper";
import RightSidebar from "@/components/News/RightSidebar";
import { calculateSourceCounts } from "@/components/News/TopSourcesBox";

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

// Server-side data fetching
async function getNewsData() {
  try {
    // Use absolute URL for server-side fetching in Vercel
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 
                   (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000');
    const res = await fetch(`${baseUrl}/api/news?category=cyber&limit=100`, {
      next: { revalidate: 300 }, // Revalidate every 5 minutes
      headers: {
        'User-Agent': 'thandev-server/1.0',
      }
    });
    
    if (!res.ok) {
      throw new Error(`Failed to fetch news: ${res.status}`);
    }
    
    const data = await res.json();
    return data.items || [];
  } catch (error) {
    console.error('Failed to fetch news data:', error);
    // Return empty array instead of throwing error to prevent page crash
    return [];
  }
}

export default async function NewsPage() {
  const allNews = await getNewsData();
  const latest = allNews.slice(0, 31); // Show first 31 articles
  const pinned = latest.slice(0, 5);
  const sourceCounts = calculateSourceCounts(allNews);

  // Structured data for news articles
  const newsStructuredData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Cybersecurity News Feed",
    "description": "Real-time cybersecurity news aggregation from trusted sources",
    "url": "https://thandev.com/news",
    "mainEntity": {
      "@type": "ItemList",
      "numberOfItems": allNews.length,
      "itemListElement": latest.slice(0, 10).map((article, index) => ({
        "@type": "NewsArticle",
        "position": index + 1,
        "headline": article.title,
        "description": article.summary,
        "url": article.url,
        "datePublished": article.publishedAt,
        "author": {
          "@type": "Organization",
          "name": article.source
        },
        "publisher": {
          "@type": "Organization",
          "name": "Thandev",
          "logo": {
            "@type": "ImageObject",
            "url": "https://thandev.com/logo.png"
          }
        },
        "image": article.image ? {
          "@type": "ImageObject",
          "url": article.image
        } : undefined
      }))
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
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">{latest.length}</div>
            <div className="text-sm text-[var(--muted)] font-medium">Articles Shown</div>
          </div>
        </div>
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
          <div className="relative z-10">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{allNews.length}</div>
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
            <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">{sourceCounts.length}</div>
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
          <NewsClientWrapper initialNews={latest} totalCount={allNews.length} />
        </div>
        <aside className="lg:col-span-1">
          <RightSidebar pinned={pinned} latest={latest} />
        </aside>
      </section>
      </main>
    </>
  );
}
