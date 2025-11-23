import 'server-only';
import { NextResponse } from 'next/server';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

// Force dynamic rendering for API routes
export const dynamic = 'force-dynamic';
export const revalidate = 0;

export const revalidate = 0;

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const url = searchParams.get('url');
  if (!url) return NextResponse.json({ error: 'Missing url' }, { status: 400 });

  try {
    const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' }, cache: 'no-store' });
    if (!r.ok) return NextResponse.json({ error: `Upstream ${r.status}` }, { status: 502 });

    const html = await r.text();
    const dom = new JSDOM(html, { url });
    const reader = new Readability(dom.window.document);
    const article = reader.parse();

    if (!article) return NextResponse.json({ error: 'Parse failed' }, { status: 500 });

    return NextResponse.json({
      title: article.title,
      byline: article.byline,
      excerpt: article.excerpt,
      siteName: (dom.window.document.querySelector('meta[property="og:site_name"]') as HTMLMetaElement)?.content || '',
      image: (dom.window.document.querySelector('meta[property="og:image"]') as HTMLMetaElement)?.content || '',
      content: article.content, // sanitized HTML from Readability
      url,
    });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Fetch error' }, { status: 500 });
  }
}
