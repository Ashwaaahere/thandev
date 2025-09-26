export const metadata = {
  title: "Thandev Documentation - API Reference & Developer Guide",
  description: "Comprehensive documentation for Thandev cybersecurity intelligence platform. API reference, getting started guide, and developer resources for threat monitoring and vulnerability tracking.",
  keywords: [
    "thandev documentation",
    "cybersecurity API",
    "threat intelligence API",
    "security platform docs",
    "vulnerability API",
    "CVE API documentation",
    "security developer guide",
    "threat monitoring API"
  ],
  openGraph: {
    title: "Thandev Documentation - API Reference & Developer Guide",
    description: "Comprehensive documentation for Thandev cybersecurity intelligence platform. API reference, getting started guide, and developer resources.",
    type: "website",
    url: "https://thandev.com/docs",
    images: [
      {
        url: "/og-docs.png",
        width: 1200,
        height: 630,
        alt: "Thandev Documentation",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Thandev Documentation - API Reference & Developer Guide",
    description: "Comprehensive documentation for Thandev cybersecurity intelligence platform. API reference, getting started guide, and developer resources.",
    images: ["/og-docs.png"],
  },
  alternates: {
    canonical: "/docs",
  },
};

export default function DocsPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      {/* Hero Section */}
      <div className="text-center mb-16">
        <h1 className="text-5xl font-bold tracking-tight text-[var(--fg)] mb-6">
          Thandev Documentation
        </h1>
        <p className="text-xl text-[var(--muted)] max-w-3xl mx-auto">
          Comprehensive guide to Thandev - your cybersecurity intelligence platform for real-time threat monitoring, vulnerability tracking, and security news aggregation.
        </p>
      </div>

      {/* Quick Navigation */}
      <div className="mb-16">
        <h2 className="text-2xl font-bold text-[var(--fg)] mb-8">Quick Navigation</h2>
        <div className="grid gap-4 md:grid-cols-3">
          <a href="#overview" className="block p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] hover:from-[var(--brand)]/5 hover:to-[var(--brand)]/10 transition-all duration-300">
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Platform Overview</h3>
            <p className="text-sm text-[var(--muted)]">Learn about Thandev's core features and capabilities</p>
          </a>
          <a href="#api" className="block p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] hover:from-[var(--brand)]/5 hover:to-[var(--brand)]/10 transition-all duration-300">
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">API Reference</h3>
            <p className="text-sm text-[var(--muted)]">Complete API documentation and endpoints</p>
          </a>
          <a href="#getting-started" className="block p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] hover:from-[var(--brand)]/5 hover:to-[var(--brand)]/10 transition-all duration-300">
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Getting Started</h3>
            <p className="text-sm text-[var(--muted)]">Quick start guide for developers and users</p>
          </a>
        </div>
      </div>

      {/* Platform Overview */}
      <section id="overview" className="mb-16">
        <h2 className="text-3xl font-bold text-[var(--fg)] mb-8">Platform Overview</h2>
        
        <div className="grid gap-8 md:grid-cols-2 mb-12">
          <div className="space-y-6">
            <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
              <h3 className="text-xl font-semibold text-[var(--fg)] mb-3">🔒 Security News Aggregation</h3>
              <p className="text-[var(--muted)]">
                Real-time aggregation of cybersecurity news from trusted sources including The Hacker News, 
                BleepingComputer, Dark Reading, SANS ISC Diary, and more. Stay updated with the latest 
                security threats, vulnerabilities, and industry insights.
              </p>
            </div>
            
            <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
              <h3 className="text-xl font-semibold text-[var(--fg)] mb-3">⚡ Exploit Intelligence</h3>
              <p className="text-[var(--muted)]">
                Comprehensive exploit database powered by NVD (National Vulnerability Database) with 
                real-time updates every 6 hours. Track CVE details, exploit availability, and 
                vulnerability severity scores.
              </p>
            </div>
          </div>
          
          <div className="space-y-6">
            <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
              <h3 className="text-xl font-semibold text-[var(--fg)] mb-3">📊 Real-time Analytics</h3>
              <p className="text-[var(--muted)]">
                Advanced analytics and insights including top sources tracking, vulnerability trends, 
                and security metrics. Monitor the cybersecurity landscape with data-driven intelligence.
              </p>
            </div>
            
            <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
              <h3 className="text-xl font-semibold text-[var(--fg)] mb-3">🚀 High Performance</h3>
              <p className="text-[var(--muted)]">
                Built with Next.js 14 and server-side rendering for optimal performance. 
                Fast loading times, efficient data fetching, and responsive design for all devices.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* API Reference */}
      <section id="api" className="mb-16">
        <h2 className="text-3xl font-bold text-[var(--fg)] mb-8">API Reference</h2>
        
        <div className="space-y-8">
          {/* News API */}
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <h3 className="text-xl font-semibold text-[var(--fg)] mb-4">📰 News API</h3>
            <div className="space-y-4">
              <div className="bg-[var(--muted)]/10 p-4 rounded-lg">
                <code className="text-sm font-mono text-[var(--fg)]">
                  GET /api/news?category=cyber&limit=100
                </code>
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">Parameters:</h4>
                <ul className="text-sm text-[var(--muted)] space-y-1 ml-4">
                  <li><code>category</code> - Filter by category (cyber, ai, tech)</li>
                  <li><code>limit</code> - Number of articles to return (default: 60, max: 100)</li>
                  <li><code>sinceDays</code> - Filter articles from last N days</li>
                </ul>
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">Response:</h4>
                <pre className="text-xs bg-[var(--muted)]/10 p-3 rounded overflow-x-auto">
{`{
  "items": [
    {
      "id": "source:url",
      "title": "Article Title",
      "url": "https://example.com/article",
      "source": "Source Name",
      "publishedAt": "2024-01-01T00:00:00Z",
      "summary": "Article summary...",
      "category": "cyber",
      "image": "https://example.com/image.jpg",
      "certified": true
    }
  ]
}`}
                </pre>
              </div>
            </div>
          </div>

          {/* Exploits API */}
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <h3 className="text-xl font-semibold text-[var(--fg)] mb-4">🔓 Exploits API</h3>
            <div className="space-y-4">
              <div className="bg-[var(--muted)]/10 p-4 rounded-lg">
                <code className="text-sm font-mono text-[var(--fg)]">
                  GET /api/exploits?limit=50&severity=high
                </code>
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">Parameters:</h4>
                <ul className="text-sm text-[var(--muted)] space-y-1 ml-4">
                  <li><code>limit</code> - Number of exploits to return (default: 20)</li>
                  <li><code>severity</code> - Filter by severity (low, medium, high, critical)</li>
                  <li><code>cve</code> - Search by CVE ID</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Getting Started */}
      <section id="getting-started" className="mb-16">
        <h2 className="text-3xl font-bold text-[var(--fg)] mb-8">Getting Started</h2>
        
        <div className="space-y-8">
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <h3 className="text-xl font-semibold text-[var(--fg)] mb-4">🚀 Quick Start</h3>
            <div className="space-y-4">
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">1. Explore the News Feed</h4>
                <p className="text-[var(--muted)] text-sm">
                  Visit the <a href="/news" className="text-[var(--brand)] hover:underline">News page</a> to see real-time 
                  cybersecurity news from multiple trusted sources. Use the "Load More" feature to see additional articles.
                </p>
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">2. Browse Exploits</h4>
                <p className="text-[var(--muted)] text-sm">
                  Check the <a href="/exploits" className="text-[var(--brand)] hover:underline">Exploits page</a> to view 
                  the latest vulnerability information from the NVD database, updated every 6 hours.
                </p>
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">3. Use the API</h4>
                <p className="text-[var(--muted)] text-sm">
                  Integrate Thandev data into your applications using our REST API endpoints. 
                  All endpoints return JSON data and support filtering and pagination.
                </p>
              </div>
            </div>
          </div>

          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <h3 className="text-xl font-semibold text-[var(--fg)] mb-4">🔧 Development Setup</h3>
            <div className="space-y-4">
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">Frontend (Next.js)</h4>
                <pre className="text-xs bg-[var(--muted)]/10 p-3 rounded overflow-x-auto">
{`cd frontend
npm install
npm run dev`}
                </pre>
              </div>
              <div className="space-y-2">
                <h4 className="font-semibold text-[var(--fg)]">Backend (Python/FastAPI)</h4>
                <pre className="text-xs bg-[var(--muted)]/10 p-3 rounded overflow-x-auto">
{`cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload`}
                </pre>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mb-16">
        <h2 className="text-3xl font-bold text-[var(--fg)] mb-8">Key Features</h2>
        
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <div className="text-2xl mb-3">📡</div>
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Real-time RSS Feeds</h3>
            <p className="text-sm text-[var(--muted)]">
              Automated RSS feed parsing from 6+ trusted cybersecurity sources with intelligent image extraction.
            </p>
          </div>
          
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <div className="text-2xl mb-3">🔄</div>
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Automated Updates</h3>
            <p className="text-sm text-[var(--muted)]">
              Scheduled data ingestion every 6 hours with PostgreSQL database for persistent storage.
            </p>
          </div>
          
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <div className="text-2xl mb-3">🎨</div>
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Modern UI</h3>
            <p className="text-sm text-[var(--muted)]">
              Beautiful, responsive design with dark/light mode support and smooth animations.
            </p>
          </div>
          
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <div className="text-2xl mb-3">⚡</div>
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Server-side Rendering</h3>
            <p className="text-sm text-[var(--muted)]">
              Optimized performance with Next.js 14 SSR for fast loading and better SEO.
            </p>
          </div>
          
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <div className="text-2xl mb-3">🔍</div>
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Advanced Filtering</h3>
            <p className="text-sm text-[var(--muted)]">
              Filter news by source, category, date range, and search for specific vulnerabilities.
            </p>
          </div>
          
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <div className="text-2xl mb-3">📊</div>
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-2">Analytics Dashboard</h3>
            <p className="text-sm text-[var(--muted)]">
              Real-time statistics showing article counts, source distribution, and trends.
            </p>
          </div>
        </div>
      </section>

      {/* Support */}
      <section className="mb-16">
        <h2 className="text-3xl font-bold text-[var(--fg)] mb-8">Support & Resources</h2>
        
        <div className="grid gap-6 md:grid-cols-2">
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <h3 className="text-xl font-semibold text-[var(--fg)] mb-4">📚 Additional Resources</h3>
            <ul className="space-y-2 text-sm text-[var(--muted)]">
              <li>• <a href="/news" className="text-[var(--brand)] hover:underline">Live News Feed</a> - Real-time security updates</li>
              <li>• <a href="/exploits" className="text-[var(--brand)] hover:underline">Exploit Database</a> - CVE and vulnerability tracking</li>
              <li>• <a href="https://github.com/Ashwaaahere/thandev" className="text-[var(--brand)] hover:underline">GitHub Repository</a> - Source code and contributions</li>
              <li>• <a href="/docs" className="text-[var(--brand)] hover:underline">API Documentation</a> - Complete reference guide</li>
            </ul>
          </div>
          
          <div className="p-6 rounded-xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)]">
            <h3 className="text-xl font-semibold text-[var(--fg)] mb-4">🤝 Contributing</h3>
            <p className="text-sm text-[var(--muted)] mb-4">
              Thandev is open source and welcomes contributions from the cybersecurity community.
            </p>
            <div className="space-y-2 text-sm text-[var(--muted)]">
              <li>• Report bugs and suggest features</li>
              <li>• Contribute to documentation</li>
              <li>• Add new data sources</li>
              <li>• Improve security features</li>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
