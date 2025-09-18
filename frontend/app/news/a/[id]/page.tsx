// app/news/a/[id]/page.tsx
import Link from "next/link";

function decodeRouteId(id: string): string | null {
  try {
    const u = decodeURIComponent(id);
    if (/^https?:\/\//i.test(u)) return u;
  } catch {}
  return null;
}

export default async function ArticlePage({
  params,
}: {
  params: { id: string };
}) {
  const originalUrl = decodeRouteId(params.id);

  if (!originalUrl) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <h1 className="text-xl font-semibold mb-2">Invalid article link</h1>
        <p className="text-[var(--muted)]">
          The link could not be decoded. If you followed a link from the feed,
          please try again.
        </p>
      </main>
    );
  }

  // Try to fetch the article HTML (many publishers may block; we fall back to a source link)
  const ua =
    "thandev-news/1.0 (+https://github.com/Ashwaaehere/thandev)";
  let html = "";
  let status = 0;

  try {
    const res = await fetch(originalUrl, {
      headers: { "user-agent": ua },
      // Don’t cache per-user to avoid showing blocked pages repeatedly
      cache: "no-store",
    });
    status = res.status;
    if (res.ok) html = await res.text();
  } catch {
    // ignore; we'll just show a fallback
  }

  if (!html) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <h1 className="text-xl font-semibold mb-3">Open at source</h1>
        <p className="mb-4 text-[var(--muted)]">
          We couldn’t render a preview from the publisher (status {status || "N/A"}).
        </p>
        <Link
          href={originalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-brand inline-block"
        >
          Read on publisher site ↗
        </Link>
      </main>
    );
  }

  // Minimal preview renderer — you can replace with JSDOM parsing later
  return (
    <main className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Article</h1>
        <Link
          href={originalUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm underline"
        >
          View original ↗
        </Link>
      </div>

      <article className="prose prose-invert max-w-none dark:prose-invert">
        {/* very basic, safe-ish container — ideally sanitize/parse */}
        <iframe
          srcDoc={html}
          className="w-full h-[70vh] rounded-xl border card-border"
          sandbox="allow-same-origin allow-popups allow-forms allow-scripts"
        />
      </article>
    </main>
  );
}
