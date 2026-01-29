// app/news/page.tsx
import NewsPageClient from "@/components/News/NewsPageClient";

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
    url: "https://thandev.io/news",
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

      {/* Client-side news page with dynamic stats */}
      <NewsPageClient />
      </main>
    </>
  );
}
