import 'server-only';
import { NextResponse } from 'next/server';
import Parser from 'rss-parser';

type FeedItem = {
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

const parser = new Parser({
  headers: { 'User-Agent': 'thandev-news/1.0 (https://github.com/Ashwaaahere/thandev)' },
});

// ✅ CERTIFIED SOURCES ONLY (curated)
const SOURCES_RSS: Array<{ url: string; source: string; category: FeedItem['category']; certified: boolean }> = [
  // Cybersecurity
  { url: 'https://feeds.feedburner.com/TheHackersNews',         source: 'The Hacker News',        category: 'cyber', certified: true },
  { url: 'https://www.bleepingcomputer.com/feed/',              source: 'BleepingComputer',       category: 'cyber', certified: true },
  { url: 'https://krebsonsecurity.com/feed/',                   source: 'Krebs on Security',      category: 'cyber', certified: true },
  { url: 'https://isc.sans.edu/rssfeed.xml',                    source: 'SANS ISC Diary',         category: 'cyber', certified: true },
  { url: 'https://msrc.microsoft.com/blog/feed/',               source: 'MSRC',                   category: 'cyber', certified: true },
  { url: 'https://www.zerodayinitiative.com/blog?format=rss',   source: 'ZDI',                    category: 'cyber', certified: true },
  { url: 'https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss',
                                                               source: 'Project Zero',            category: 'cyber', certified: true },

  // Tech (Security section)
  { url: 'https://feeds.arstechnica.com/arstechnica/security',  source: 'Ars Technica Security',  category: 'tech',  certified: true },
];

// Recency filter helpers
function daysAgo(n: number) { return Date.now() - n*24*60*60*1000; }
function isRecent(iso: string, sinceMs: number) {
  const t = new Date(iso).getTime(); return !Number.isNaN(t) && t >= sinceMs;
}

// Try to extract image
function extractImage(it: any): string | null {
  if (it?.enclosure?.url) return it.enclosure.url as string;
  const media = (it as any)['media:content'] || (it as any)['media:thumbnail'];
  if (media?.url) return media.url as string;
  if (Array.isArray(media) && media[0]?.url) return media[0].url as string;
  const html = (it?.content || it?.['content:encoded'] || '') as string;
  const m = html.match(/<img[^>]+src=["']([^"']+)["']/i);
  if (m?.[1]) return m[1];
  return null;
}

function normalizeRSS(item: any, src: { source: string; category: FeedItem['category']; certified: boolean }): FeedItem | null {
  const title = (item?.title ?? '').toString();
  const link  = (item?.link  ?? '').toString();
  if (!title || !link) return null;

  const dateRaw = item.isoDate || item.pubDate || '';
  const publishedAt = dateRaw ? new Date(dateRaw).toISOString() : new Date().toISOString();

  const plain = (item.contentSnippet || item.content || '').toString().replace(/<[^>]+>/g,'').trim();
  const image = extractImage(item);

  return {
    id: `${src.source}:${link}`,
    title, url: link, source: src.source,
    publishedAt, summary: plain.slice(0, 260),
    category: src.category, image: image || null,
    certified: !!src.certified,
  };
}

export const revalidate = 600;

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const category = (searchParams.get('category') as FeedItem['category'] | null) ?? null;
  const sinceDays = parseInt(searchParams.get('sinceDays') || '21', 10); // default 3 weeks
  const limit     = parseInt(searchParams.get('limit')     || '60', 10);
  const sinceMs   = daysAgo(Math.max(1, sinceDays));
  const certifiedOnly = (searchParams.get('certifiedOnly') ?? '1') === '1'; // default: yes
  const q = (searchParams.get('q') || '').toLowerCase();

  const all: FeedItem[] = [];
  await Promise.all(SOURCES_RSS.map(async (s) => {
    if (category && s.category !== category) return;
    try {
      const feed = await parser.parseURL(s.url);
      for (const it of feed.items || []) {
        const n = normalizeRSS(it, s);
        if (n) all.push(n);
      }
    } catch (e: any) {
      console.error('[news] source failed', s.source, e?.message || e);
    }
  }));

  // de-dup
  const map = new Map<string, FeedItem>();
  for (const i of all) if (!map.has(i.url)) map.set(i.url, i);

  let items = Array.from(map.values())
    .filter(i => isRecent(i.publishedAt, sinceMs))
    .sort((a,b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));

  if (certifiedOnly) items = items.filter(i => i.certified);

  if (q) {
    const text = (s: string) => s.toLowerCase();
    items = items.filter(i => text(i.title+ ' ' +i.summary+ ' ' +i.source).includes(q));
  }

  return NextResponse.json({ items: items.slice(0, limit) });
}
