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
        <div className="rounded-xl border border-white/10 bg-white/5 p-6">
          <h1 className="text-xl font-semibold">Invalid link</h1>
          <p className="mt-2 text-sm opacity-80">
            We couldn’t understand this article link.
          </p>
          <Link className="mt-4 inline-block text-blue-400 hover:underline" href="/news">
            ← Back to news
          </Link>
        </div>
      </main>
    );
  }

  const html = await fetchHtml(targetUrl);

  // If we can’t fetch HTML, show a simple “open original” card
  if (!html) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-10">
        <div className="rounded-xl border border-white/10 bg-white/5 p-6">
          <div className="mb-4 flex items-center justify-between">
            <h1 className="text-lg font-semibold">Open original</h1>
            <a
              href={targetUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-lg bg-white/10 px-3 py-1.5 text-sm font-semibold hover:bg-white/20"
            >
              View source ↗
            </a>
          </div>
          <p className="text-sm opacity-80">
            You’re viewing a link-out article. Full content is available at the
            source above.
          </p>
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
    <main className="mx-auto max-w-3xl px-6 py-8">
      {/* Top bar */}
      <div className="mb-6 flex items-center justify-between">
        <div className="text-sm opacity-80">Open original on</div>
        <a
          href={targetUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg bg-white/10 px-3 py-1.5 text-sm font-semibold hover:bg-white/20"
        >
          {new URL(targetUrl).hostname} ↗
        </a>
      </div>

      {/* Hero card */}
      <article className="rounded-2xl border border-white/10 bg-white/5 p-5 md:p-7">
        {heroImage ? (
          <div className="mb-5 overflow-hidden rounded-xl border border-white/10 bg-black/10">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={heroImage}
              alt=""
              className="h-64 w-full object-cover md:h-80"
              loading="lazy"
            />
          </div>
        ) : null}

        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          {articleTitle}
        </h1>

        {articleExcerpt ? (
          <p className="mt-3 text-sm opacity-85">{articleExcerpt}</p>
        ) : null}

        {/* Render readable article */}
        {articleHtml ? (
          <div
            className="prose prose-invert mt-6 max-w-none prose-headings:scroll-mt-24 prose-a:text-blue-400 hover:prose-a:text-blue-300"
            dangerouslySetInnerHTML={{ __html: articleHtml }}
          />
        ) : (
          <div className="mt-6 rounded-lg border border-white/10 bg-white/5 p-4 text-sm opacity-85">
            We couldn’t extract the article body. Use the source link above to
            read it.
          </div>
        )}
      </article>
    </main>
  );
}
