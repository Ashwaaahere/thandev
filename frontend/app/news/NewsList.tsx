import Link from "next/link";

type Item = {
  id?: string;
  title?: string;
  url?: string;
  source?: string;
  image?: string | null;
  summary?: string | null;
  published_at?: string | number | Date;
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
      <div className="mt-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8 text-[var(--muted)]">
        No stories right now. Please check back in a bit.
      </div>
    );
  }

  const featured = items[0];
  const rest = items.slice(1);

  const toHref = (u?: string) => {
    // If you want to send through your article page, replace with your encoder:
    // return u ? `/news/a/${btoa(u)}` : "#"
    return u ?? "#";
  };

  return (
    <>
      {/* Featured */}
      {featured && (
        <article className="mb-8 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-soft">
          <Link
            href={toHref(featured.url)}
            className="group block focus:outline-none"
            target={featured.url?.startsWith("http") ? "_blank" : undefined}
            rel={featured.url?.startsWith("http") ? "noopener noreferrer" : undefined}
          >
            {/* image */}
            <div className="relative h-64 w-full overflow-hidden sm:h-72 md:h-[22rem]">
              {featured.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={featured.image}
                  alt={featured.title ?? "story image"}
                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                  loading="lazy"
                />
              ) : (
                <div className="h-full w-full bg-gradient-to-b from-white/5 to-white/0 dark:from-white/10" />
              )}
              <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
            </div>

            {/* content */}
            <div className="p-4 sm:p-6">
              <div className="mb-2 flex items-center gap-2 text-xs text-[var(--muted)]">
                {featured.source && (
                  <span className="rounded bg-black/5 px-2 py-0.5 dark:bg-white/10">
                    {featured.source}
                  </span>
                )}
              </div>

              <h3 className="text-lg font-semibold leading-snug md:text-xl">
                {featured.title ?? "Untitled"}
              </h3>

              {featured.summary && (
                <p className="mt-2 line-clamp-2 text-sm text-[var(--muted)]">
                  {featured.summary}
                </p>
              )}

              <div className="mt-3 text-sm text-[var(--brand)]">
                Read full article →
              </div>
            </div>
          </Link>
        </article>
      )}

      {/* Grid for the rest */}
      {rest.length > 0 && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {rest.map((it, idx) => (
            <article
              key={it.id ?? `${it.url ?? "row"}-${idx}`}
              className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-soft transition-transform duration-200 hover:-translate-y-0.5"
            >
              <Link
                href={toHref(it.url)}
                className="block focus:outline-none"
                target={it.url?.startsWith("http") ? "_blank" : undefined}
                rel={it.url?.startsWith("http") ? "noopener noreferrer" : undefined}
              >
                <div className="relative h-40 w-full overflow-hidden">
                  {it.image ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={it.image}
                      alt={it.title ?? "story image"}
                      className="h-full w-full object-cover transition-transform duration-300 hover:scale-[1.03]"
                      loading="lazy"
                    />
                  ) : (
                    <div className="h-full w-full bg-gradient-to-b from-white/5 to-white/0 dark:from-white/10" />
                  )}
                </div>

                <div className="p-4">
                  <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                    {it.source && (
                      <span className="rounded bg-black/5 px-2 py-0.5 dark:bg-white/10">
                        {it.source}
                      </span>
                    )}
                  </div>

                  <h4 className="line-clamp-2 text-[15px] font-semibold">
                    {it.title ?? "Untitled"}
                  </h4>

                  {it.summary && (
                    <p className="mt-1 line-clamp-2 text-sm text-[var(--muted)]">
                      {it.summary}
                    </p>
                  )}
                </div>
              </Link>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
