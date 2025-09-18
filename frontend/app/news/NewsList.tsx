import Link from 'next/link';
import { headers } from 'next/headers';

type Item = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string;
  summary: string;
  category: 'cyber' | 'tech';
  image?: string | null;
  certified: boolean;
};

const toB64Url = (s: string) => {
  const b64 = Buffer.from(s, 'utf8').toString('base64');
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

const timeAgo = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
};

function absoluteUrl(path: string) {
  const h = headers();
  const proto = h.get('x-forwarded-proto') ?? 'http';
  const host = h.get('x-forwarded-host') ?? h.get('host') ?? 'localhost:3000';
  return `${proto}://${host}${path.startsWith('/') ? path : `/${path}`}`;
}

export default async function NewsList() {
  const res = await fetch(
    absoluteUrl('/api/news?certifiedOnly=1&sinceDays=21&limit=60'),
    { cache: 'no-store' }
  );
  if (!res.ok) throw new Error('Failed to load news');
  const data = (await res.json()) as { items: Item[] };
  const items = data.items ?? [];
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-6 text-slate-300">
        No news found. Try again shortly.
      </div>
    );
  }

  const [featured, ...rest] = items;

  return (
    <div>
      {/* Featured */}
      <Link
        href={`/news/a/${toB64Url(featured.url)}`}
        className="group block overflow-hidden rounded-2xl border border-white/10 bg-white/5"
      >
        <div className="grid md:grid-cols-2">
          <div className="aspect-[16/9] md:aspect-auto md:h-full bg-black/40">
            {featured.image ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={featured.image}
                alt=""
                className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
              />
            ) : null}
          </div>
          <div className="p-5">
            <div className="flex items-center gap-2 text-xs text-slate-300">
              <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-emerald-300">Certified</span>
              <span className="rounded bg-white/10 px-2 py-0.5">{featured.source}</span>
              <span className="text-slate-400">{timeAgo(featured.publishedAt)}</span>
            </div>
            <h1 className="mt-2 text-2xl font-semibold leading-snug group-hover:underline">
              {featured.title}
            </h1>
            <p className="mt-2 line-clamp-3 text-slate-300">{featured.summary}</p>
            <div className="mt-4 text-sm text-sky-300">Read full article →</div>
          </div>
        </div>
      </Link>

      {/* Grid */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rest.map((it) => (
          <Link
            key={it.id}
            href={`/news/a/${toB64Url(it.url)}`}
            className="group overflow-hidden rounded-2xl border border-white/10 bg-white/5"
          >
            <div className="aspect-[16/9] w-full bg-black/40">
              {it.image ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={it.image}
                  alt=""
                  className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
                />
              ) : null}
            </div>
            <div className="p-4">
              <div className="flex items-center justify-between text-xs">
                <span className="rounded bg-white/10 px-2 py-0.5">{it.source}</span>
                <span className="text-slate-400">{timeAgo(it.publishedAt)}</span>
              </div>
              <h3 className="mt-2 line-clamp-2 text-base font-semibold group-hover:underline">
                {it.title}
              </h3>
              <p className="mt-1 line-clamp-2 text-sm text-slate-300">{it.summary}</p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
