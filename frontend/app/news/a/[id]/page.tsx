// app/news/a/[id]/page.tsx
import type { Metadata } from "next";
import Link from "next/link";
import { b64urlDecode } from "@/components/utils/base64url";
import { normalizeExternalUrl, isHttpUrl } from "@/components/utils/urls";

// Server-side libs to extract readable content
import { JSDOM } from "jsdom";
import { Readability } from "@mozilla/readability";

export const revalidate = 300; // cache parsed article for 5 min

type Props = { params: { id: string } };

function decodeIdToUrl(id: string): string | null {
  if (!id) return null;

  // 1) Try base64url first
  try {
    const decoded = b64urlDecode(id);
    if (isHttpUrl(decoded)) return decoded;
  } catch {}

  // 2) Try decodeURIComponent (when you directly put encoded URL in the route)
  try {
    const decoded = decodeURIComponent(id);
    if (isHttpUrl(decoded)) return decoded;
  } catch {}

  // 3) Last resort, treat as raw and try to normalize
  const normalized = normalizeExternalUrl(id);
  if (isHttpUrl(normalized)) return normalized;

  return null;
}

async function fetchHtml(targetUrl: string): Promise<string | null> {
  try {
    const res = await fetch(targetUrl, {
      // Pretend we're a browser; some sites gate by UA
      headers: {
        "User-Agent":
          "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        Accept:
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
      },
      // do not forward cookies
      cache: "no-store",
    });
    if (!res.ok) return null;
    const html = await res.text();
    return html || null;
  } catch {
    return null;
  }
}

function extractMeta(doc: Document) {
  const get = (sel: string) => doc.querySelector<HTMLMetaElement>(sel)?.content?.trim() || "";
  const text = (sel: string) => doc.querySelector(sel)?.textContent?.trim() || "";

  const title =
    get('meta[property="og:title"]') ||
    get('meta[name="twitter:title"]') ||
    text("title");

  const description =
    get('meta[property="og:description"]') ||
    get('meta[name="description"]') ||
    get('meta[name="twitter:description"]');

  const image =
    get('meta[property="og:image"]') ||
    get('meta[name="twitter:image"]') ||
    "";

  const siteName = get('meta[property="og:site_name"]') || "";

  return { title, description, image, siteName };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const url = decodeIdToUrl(params.id);
  if (!url) {
    return { title: "Article not found" };
  }
  // Light metadata; we’ll refine in page() after parsing
  return {
    title: "Article • Thandev",
    openGraph: {
      url,
      title: "Article • Thandev",
    },
  };
}

export default async function ArticlePage({ params }: Props) {
  const targetUrl = decodeIdToUrl(params.id);

  if (!targetUrl) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="relative overflow-hidden rounded-2xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-8 backdrop-blur-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/5 to-transparent" />
          <div className="relative z-10">
            <div className="mb-4 flex items-center gap-3">
              <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-sm font-semibold text-[var(--brand)]">ERROR</span>
            </div>
            <h1 className="text-2xl font-bold title-future mb-4">Invalid Article Link</h1>
            <p className="text-[var(--muted)] mb-6">
              We couldn't understand this article link. It may be corrupted or invalid.
            </p>
            <Link 
              className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)]/10 px-4 py-2 text-sm font-semibold text-[var(--brand)] hover:bg-[var(--brand)]/20 transition-all duration-300 border border-[var(--brand)]/30" 
              href="/news"
            >
              ← Back to News
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const html = await fetchHtml(targetUrl);

  // If we can't fetch HTML, show a simple "open original" card
  if (!html) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="relative overflow-hidden rounded-2xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-8 backdrop-blur-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/5 to-transparent" />
          <div className="relative z-10">
            <div className="mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-2 w-2 rounded-full bg-yellow-500 animate-pulse" />
                <span className="text-sm font-semibold text-[var(--brand)]">EXTERNAL LINK</span>
              </div>
              <a
                href={targetUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)]/10 px-4 py-2 text-sm font-semibold text-[var(--brand)] hover:bg-[var(--brand)]/20 transition-all duration-300 border border-[var(--brand)]/30"
              >
                View Source ↗
              </a>
            </div>
            <h1 className="text-2xl font-bold title-future mb-4">External Article</h1>
            <p className="text-[var(--muted)] mb-6">
              This article is hosted externally. Click the button above to view the full content at the source.
            </p>
            <div className="flex items-center gap-4">
              <Link 
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--muted)]/10 px-4 py-2 text-sm font-semibold text-[var(--muted)] hover:bg-[var(--muted)]/20 transition-all duration-300 border border-[var(--muted)]/30" 
                href="/news"
              >
                ← Back to News
              </Link>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // Parse with JSDOM + Readability
  const dom = new JSDOM(html, { url: targetUrl });
  const doc = dom.window.document;

  const meta = extractMeta(doc);
  const reader = new Readability(doc);
  const parsed = reader.parse(); // { title, content, textContent, byline, length, excerpt, siteName }

  const articleTitle = parsed?.title || meta.title || "Article";
  const articleHtml = parsed?.content || ""; // already HTML
  const articleExcerpt = parsed?.excerpt || meta.description || "";
  const heroImage = meta.image || "";

  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      {/* Top navigation bar */}
      <div className="mb-8 flex items-center justify-between">
        <Link 
          href="/news"
          className="inline-flex items-center gap-2 text-sm text-[var(--muted)] hover:text-[var(--brand)] transition-colors duration-300"
        >
          ← Back to News
        </Link>
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-semibold text-[var(--brand)]">LIVE</span>
          <a
            href={targetUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)]/10 px-4 py-2 text-sm font-semibold text-[var(--brand)] hover:bg-[var(--brand)]/20 transition-all duration-300 border border-[var(--brand)]/30"
          >
            {new URL(targetUrl).hostname} ↗
          </a>
        </div>
      </div>

      {/* Hero section */}
      <div className="relative mb-8 overflow-hidden rounded-3xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/5 to-transparent" />
        
        {heroImage ? (
          <div className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-t from-[var(--bg)]/80 via-transparent to-transparent z-10" />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={heroImage}
              alt=""
              className="h-64 w-full object-cover md:h-96"
              loading="lazy"
            />
          </div>
        ) : null}

        <div className="relative z-10 p-6 md:p-8">
          <h1 className="text-3xl font-bold title-future mb-4 md:text-4xl">
            {articleTitle}
          </h1>

          {articleExcerpt ? (
            <p className="text-lg text-[var(--muted)] leading-relaxed mb-6">
              {articleExcerpt}
            </p>
          ) : null}

          <div className="flex items-center gap-4 text-sm text-[var(--muted)]">
            <span>Source: {new URL(targetUrl).hostname}</span>
            <span>•</span>
            <span>Read time: ~{Math.ceil((articleHtml?.length || 0) / 1000)} min</span>
          </div>
        </div>
      </div>

      {/* Article content */}
      <article className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 md:p-8 backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/2 to-transparent" />
        
        <div className="relative z-10">
          {articleHtml ? (
            <div
              className="prose prose-lg prose-invert max-w-none prose-headings:scroll-mt-24 prose-headings:text-[var(--fg)] prose-headings:font-bold prose-p:text-[var(--muted)] prose-p:leading-relaxed prose-a:text-[var(--brand)] prose-a:no-underline hover:prose-a:underline prose-strong:text-[var(--fg)] prose-code:text-[var(--brand)] prose-code:bg-[var(--surface-2)] prose-code:px-2 prose-code:py-1 prose-code:rounded prose-pre:bg-[var(--surface-2)] prose-pre:border prose-pre:border-[var(--border)]/50"
              dangerouslySetInnerHTML={{ __html: articleHtml }}
            />
          ) : (
            <div className="rounded-lg border border-[var(--brand)]/20 bg-[var(--brand)]/5 p-6 text-center">
              <div className="mb-4 text-4xl">📄</div>
              <h3 className="text-lg font-semibold text-[var(--brand)] mb-2">Content Unavailable</h3>
              <p className="text-[var(--muted)] mb-4">
                We couldn't extract the article body. Use the source link above to read it.
              </p>
              <a
                href={targetUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)]/10 px-4 py-2 text-sm font-semibold text-[var(--brand)] hover:bg-[var(--brand)]/20 transition-all duration-300 border border-[var(--brand)]/30"
              >
                Read Original ↗
              </a>
            </div>
          )}
        </div>
      </article>

      {/* Bottom navigation */}
      <div className="mt-8 flex items-center justify-between">
        <Link 
          href="/news"
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--muted)]/10 px-4 py-2 text-sm font-semibold text-[var(--muted)] hover:bg-[var(--muted)]/20 transition-all duration-300 border border-[var(--muted)]/30"
        >
          ← All News
        </Link>
        <a
          href={targetUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--brand)]/10 px-4 py-2 text-sm font-semibold text-[var(--brand)] hover:bg-[var(--brand)]/20 transition-all duration-300 border border-[var(--brand)]/30"
        >
          View Original ↗
        </a>
      </div>
    </main>
  );
}
