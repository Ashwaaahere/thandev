import Link from "next/link";
import { b64urlEncode } from "@/components/utils/base64url";

type Item = {
  id?: string;
  title?: string;
  url?: string;
  source?: string;
  image?: string | null;
  summary?: string | null;
  published_at?: string | number | Date;
  publishedAt?: string | number | Date; // Support both field names
};

/**
 * NewsList – robust server component
 * - Defensive against undefined/empty items
 * - Shows a featured card (first item) + grid for the rest
 * - Gracefully handles missing images
 */
export default function NewsList({
  items: rawItems,
}: {
  items?: Item[] | null;
}) {
  // Always normalize to an array
  const items: Item[] = Array.isArray(rawItems) ? rawItems : [];

  if (items.length === 0) {
    return (
      <div className="relative overflow-hidden rounded-3xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-16 text-center backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/5 to-transparent" />
        <div className="relative z-10">
          <div className="mx-auto mb-6 h-20 w-20 rounded-full bg-gradient-to-br from-[var(--brand)]/20 to-[var(--brand)]/10 flex items-center justify-center">
            <div className="text-3xl">📰</div>
          </div>
          <h3 className="text-2xl font-bold text-[var(--fg)] mb-3">No Stories Available</h3>
          <p className="text-lg text-[var(--muted)] mb-6 max-w-md mx-auto">
            We're currently updating our news feed. Please check back in a few moments for the latest security updates.
          </p>
          <div className="flex items-center justify-center gap-2 text-sm text-[var(--brand)]">
            <div className="h-2 w-2 rounded-full bg-[var(--brand)] animate-pulse" />
            <span>Refreshing content...</span>
          </div>
        </div>
      </div>
    );
  }

  const featured = items[0];
  const rest = items.slice(1);

  const toHref = (u?: string) => {
    if (!u) return "#";
    // Encode URL for article page
    return `/news/a/${b64urlEncode(u)}`;
  };

  return (
    <div className="space-y-8">
      {/* Featured */}
      {featured && (
        <article className="group relative overflow-hidden rounded-3xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] shadow-xl shadow-[var(--brand)]/10 featured-card news-card transition-shadow duration-300 hover:shadow-[var(--brand)]/20">
          <Link
            href={toHref(featured.url)}
            className="block focus:outline-none"
          >
            {/* image */}
            <div className="relative h-64 w-full overflow-hidden sm:h-72 md:h-[24rem]">
              {featured.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={featured.image}
                  alt={featured.title ?? "story image"}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-102"
                  loading="lazy"
                />
              ) : (
                <div className="h-full w-full bg-gradient-to-br from-[var(--brand)]/10 to-[var(--brand)]/5" />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent" />
              <div className="absolute top-4 right-4">
                <div className="rounded-full bg-[var(--brand)] px-3 py-1 text-xs font-bold text-white">
                  FEATURED
                </div>
              </div>
            </div>

            {/* content */}
            <div className="relative p-6 sm:p-8">
              <div className="mb-4 flex items-center gap-3 text-sm text-[var(--muted)]">
                {featured.source && (
                  <span className="rounded-full bg-[var(--brand)]/10 px-3 py-1 text-[var(--brand)] font-semibold">
                    {featured.source}
                  </span>
                )}
              </div>

              <h3 className="text-2xl font-bold leading-tight text-[var(--fg)] sm:text-3xl group-hover:text-[var(--brand)] transition-colors duration-200">
                {featured.title ?? "Untitled"}
              </h3>

              {featured.summary && (
                <p className="mt-3 line-clamp-3 text-base text-[var(--muted)] leading-relaxed">
                  {featured.summary}
                </p>
              )}

              <div className="mt-4 flex items-center text-sm text-[var(--brand)] font-semibold">
                Read More →
              </div>
            </div>
          </Link>
        </article>
      )}

      {/* Grid for the rest */}
      {rest.length > 0 && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {rest.map((it, idx) => (
            <article
              key={it.id ?? `${it.url ?? "row"}-${idx}`}
              className="group relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] shadow-lg hover:shadow-xl hover:shadow-[var(--brand)]/15 news-card transition-shadow duration-300 hover:border-[var(--brand)]/30"
            >
              <Link
                href={toHref(it.url)}
                className="block focus:outline-none"
              >
                <div className="relative h-48 w-full overflow-hidden">
                  {it.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={it.image}
                      alt={it.title ?? "story image"}
                      className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                      loading="lazy"
                    />
                  ) : (
                    <div className="h-full w-full bg-gradient-to-br from-[var(--brand)]/10 to-[var(--brand)]/5" />
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/20 to-transparent" />
                </div>

                <div className="relative p-5">
                  <div className="mb-3 flex items-center gap-2 text-xs text-[var(--muted)]">
                    {it.source && (
                      <span className="rounded-full bg-[var(--brand)]/10 px-2 py-1 text-[var(--brand)] font-semibold">
                        {it.source}
                      </span>
                    )}
                  </div>

                  <h4 className="line-clamp-2 text-lg font-bold text-[var(--fg)] group-hover:text-[var(--brand)] transition-colors duration-200">
                    {it.title ?? "Untitled"}
                  </h4>

                  {it.summary && (
                    <p className="mt-2 line-clamp-2 text-sm text-[var(--muted)] leading-relaxed">
                      {it.summary}
                    </p>
                  )}

                  <div className="mt-3 text-xs text-[var(--brand)] font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    Read Article →
                  </div>
                </div>
              </Link>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
