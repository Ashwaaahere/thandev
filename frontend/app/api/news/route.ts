// app/api/news/route.ts
import 'server-only';
import { NextResponse } from 'next/server';
import Parser from 'rss-parser';

type RSSItem = {
  title?: string;
  link?: string;
  isoDate?: string;
  pubDate?: string;
  contentSnippet?: string;
  content?: string;
  creator?: string;
};

type FeedItem = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string; // ISO
  summary: string;
  category: 'cyber' | 'ai' | 'tech';
};

const parser = new Parser({
  headers: { 'User-Agent': 'thandev-news/1.0 (+https://github.com/Ashwaaahere/thandev)' },
});

const SOURCES: Array<{
  url: string;
  source: string;
  category: FeedItem['category'];
}> = [
  // Cybersecurity
  { url: 'https://feeds.feedburner.com/TheHackersNews', source: 'The Hacker News', category: 'cyber' },
  { url: 'https://www.reddit.com/r/netsec/.rss', source: 'r/netsec', category: 'cyber' },
  // AI
  { url: 'https://www.reddit.com/r/MachineLearning/.rss', source: 'r/MachineLearning', category: 'ai' },
  { url: 'https://hnrss.org/newest?points=50&count=50', source: 'Hacker News (AI/Tech)', category: 'ai' },
  // General tech
  { url: 'https://hnrss.org/frontpage', source: 'Hacker News', category: 'tech' },
  { url: 'https://feeds.arstechnica.com/arstechnica/index', source: 'Ars Technica', category: 'tech' },
];

function normalize(item: RSSItem, source: string, category: FeedItem['category']): FeedItem | null {
  if (!item?.title || !item?.link) return null;
  const dateRaw = item.isoDate || item.pubDate || '';
  const publishedAt = dateRaw ? new Date(dateRaw).toISOString() : new Date().toISOString();
  const text = (item.contentSnippet || item.content || '').replace(/<[^>]+>/g, '').trim();
  return {
    id: `${source}:${item.link}`,
    title: item.title,
    url: item.link!,
    source,
    publishedAt,
    summary: text.slice(0, 240),
    category,
  };
}

export const revalidate = 600; // 10 minutes cache on Vercel/Next ISR

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const categoryParam = (searchParams.get('category') as FeedItem['category'] | null) ?? null;
  const q = searchParams.get('q')?.toLowerCase() || '';

  const results: FeedItem[] = [];
  // Fetch in parallel, but be gentle
  await Promise.all(
    SOURCES.map(async (src) => {
      try {
        if (categoryParam && src.category !== categoryParam) return;
        const feed = await parser.parseURL(src.url);
        for (const it of feed.items || []) {
          const norm = normalize(it as RSSItem, src.source, src.category);
          if (norm) results.push(norm);
        }
      } catch (e) {
        // swallow errors per-source to keep others working
        console.error(`[news] Failed ${src.source}:`, (e as Error).message);
      }
    })
  );

  // Deduplicate by URL, sort by publishedAt desc
  const unique = new Map<string, FeedItem>();
  for (const r of results) {
    if (!unique.has(r.url)) unique.set(r.url, r);
  }
  let items = Array.from(unique.values()).sort(
    (a, b) => new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
  );

  if (q) {
    items = items.filter(
      (i) => i.title.toLowerCase().includes(q) || i.summary.toLowerCase().includes(q) || i.source.toLowerCase().includes(q)
    );
  }

  // Clamp to a reasonable number
  items = items.slice(0, 120);

  return NextResponse.json({ items });
}
