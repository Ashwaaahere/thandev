'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

type Article = {
  title: string;
  byline?: string;
  excerpt?: string;
  siteName?: string;
  image?: string;
  content: string;
  url: string;
};

// portable base64url decoder
const fromB64Url = (s: string) => {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/') + pad;
  return typeof window === 'undefined'
    ? Buffer.from(b64, 'base64').toString('utf8')
    : decodeURIComponent(escape(atob(b64)));
};

export default function ArticlePage({ params }: { params: { id: string } }) {
  const url = fromB64Url(params.id);
  const [data, setData] = useState<Article | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await fetch(`/api/article?url=${encodeURIComponent(url)}`, { cache: 'no-store' });
        if (!r.ok) throw new Error('Failed to load article');
        const json = await r.json();
        if ((json as any)?.error) throw new Error((json as any).error);
        setData(json as Article);
      } catch (e: any) {
        setErr(e?.message || 'Error loading article');
      }
    };
    if (url) load();
  }, [url]);

  if (!url) return <div className="p-6 text-red-300">Bad link.</div>;
  if (err)  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-3xl px-4 py-8">
        <Link href="/news" className="text-sky-300 hover:underline">← Back to News</Link>
        <div className="mt-4 rounded-xl border border-red-800 bg-red-950/40 p-4 text-red-200">{err}</div>
      </div>
    </main>
  );
  if (!data) return null; // route-level loader will show

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <article className="mx-auto max-w-3xl px-4 py-8">
        <Link href="/news" className="text-sky-300 hover:underline">← Back to News</Link>
        <h1 className="mt-4 text-3xl font-semibold">{data.title}</h1>
        <div className="mt-2 text-sm text-slate-400">
          {data.siteName ? <span>{data.siteName}</span> : null}
          {data.byline ? <span> • {data.byline}</span> : null}
        </div>
        {data.image ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={data.image} alt="" className="mt-6 w-full rounded-xl border border-white/10" />
        ) : null}
        <div
          className="prose prose-invert prose-slate mt-6 max-w-none prose-a:text-sky-300 prose-img:rounded-xl"
          dangerouslySetInnerHTML={{ __html: data.content }}
        />
        <div className="mt-8 text-sm">
          <a href={data.url} target="_blank" rel="noreferrer" className="text-sky-300 hover:underline">
            View original →
          </a>
        </div>
      </article>
    </main>
  );
}
