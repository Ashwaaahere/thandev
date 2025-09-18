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
<<<<<<< HEAD
  category: 'cyber' | 'tech';
  image?: string | null;
  certified: boolean;
=======
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;
>>>>>>> origin/main
};

const parser = new Parser({
  headers: { 'User-Agent': 'thandev-news/1.0 (https://github.com/Ashwaaahere/thandev)' },
});

<<<<<<< HEAD
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
=======
/* ----------------------- SOURCES (focused) ----------------------- */
const SOURCES_RSS: Array<{ url: string; source: string; category: FeedItem['category'] }> = [
  // Cybersecurity
  { url: 'https://feeds.feedburner.com/TheHackersNews', source: 'The Hacker News', category: 'cyber' },
  { url: 'https://www.bleepingcomputer.com/feed/', source: 'BleepingComputer', category: 'cyber' },
  { url: 'https://krebsonsecurity.com/feed/', source: 'Krebs on Security', category: 'cyber' },
  { url: 'https://isc.sans.edu/rssfeed.xml', source: 'SANS ISC Diary', category: 'cyber' },
  { url: 'https://msrc.microsoft.com/blog/feed/', source: 'MSRC', category: 'cyber' },
  { url: 'https://www.zerodayinitiative.com/blog?format=rss', source: 'ZDI', category: 'cyber' },
  { url: 'https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss', source: 'Project Zero', category: 'cyber' },

  // Tech (security section only)
  { url: 'https://feeds.arstechnica.com/arstechnica/security', source: 'Ars Technica Security', category: 'tech' },

  // HN filtered to security keywords
  {
    url: 'https://hnrss.org/newest?q=security%20OR%20cve%20OR%20ransomware%20OR%20vulnerability%20OR%20exploit&count=50',
    source: 'Hacker News (security)',
    category: 'cyber',
  },
];

// Optional JSON (CISA KEV)
const SOURCES_JSON: Array<{ url: string; source: string; category: FeedItem['category']; kind: 'cisa-kev' }> = [
  { url: 'https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json', source: 'CISA KEV', category: 'cyber', kind: 'cisa-kev' },
];

/* ------------------ helpers ------------------ */
const ALLOW = [
  'cve', 'vulnerability', 'vulnerabilities', 'exploit', 'exploited',
  'poc', 'zero-day', 'zeroday', 'rce', 'lpe', 'xss', 'sql injection',
  'ransomware', 'breach', 'data leak', 'advisory', 'patch tuesday',
  'mitre', 'nvd', 'kev', 'msrc', 'project zero', 'zdi', 'ics', 'ot security'
];
const BLOCK = [
  'ask hn', 'show hn', 'who is hiring', 'hiring', 'career', 'opinion',
  'weekly thread', 'discussion thread'
];

function scoreItem(title: string, summary: string, source: string) {
  const text = `${title} ${summary} ${source}`.toLowerCase();
  let score = 0;
  for (const k of ALLOW) if (text.includes(k)) score += 2;
  for (const k of BLOCK) if (text.includes(k)) score -= 3;
  if (source.includes('Hacker News')) score -= 1; // tighten HN
  if (['The Hacker News', 'BleepingComputer', 'Krebs on Security'].includes(source)) score += 1;
  return score;
}

// Try to extract image from common RSS fields
function extractImage(it: any): string | null {
  // 1) enclosure
  if (it?.enclosure?.url) return it.enclosure.url as string;

  // 2) media:content variations
  const media = (it as any)['media:content'] || (it as any)['media:thumbnail'];
  if (media?.url) return media.url as string;
  if (Array.isArray(media) && media[0]?.url) return media[0].url as string;

  // 3) content HTML <img ...>
  const html = (it?.content || it?.['content:encoded'] || '') as string;
  const m = html.match(/<img[^>]+src=["']([^"']+)["']/i);
  if (m && m[1]) return m[1];

  // 4) description HTML <img ...>
  const html2 = (it?.contentSnippet || it?.summary || '') as string;
  const m2 = html2.match(/<img[^>]+src=["']([^"']+)["']/i);
  if (m2 && m2[1]) return m2[1];

  return null;
}

function normalizeRSS(item: any, source: string, category: FeedItem['category']): FeedItem | null {
  const title = item?.title?.toString() ?? '';
  const link = item?.link?.toString() ?? '';
  if (!title || !link) return null;
  const dateRaw = item.isoDate || item.pubDate || '';
  const publishedAt = dateRaw ? new Date(dateRaw).toISOString() : new Date().toISOString();
  const text = (item.contentSnippet || item.content || '').toString().replace(/<[^>]+>/g, '').trim();
  const image = extractImage(item);
  return {
    id: `${source}:${link}`,
    title,
    url: link,
    source,
    publishedAt,
    summary: text.slice(0, 240),
    category,
    image: image || null,
  };
}

async function fetchRSS(categoryParam: FeedItem['category'] | null): Promise<FeedItem[]> {
  const results: FeedItem[] = [];
  await Promise.all(
    SOURCES_RSS.map(async (src) => {
      try {
        if (categoryParam && src.category !== categoryParam) return;
        const feed = await parser.parseURL(src.url);
        for (const it of feed.items || []) {
          const norm = normalizeRSS(it, src.source, src.category);
          if (norm) results.push(norm);
        }
      } catch (e: any) {
        console.error(`[news] Failed ${src.source}: ${e?.message || e}`);
      }
    })
  );
  return results;
}

async function fetchJSON(categoryParam: FeedItem['category'] | null): Promise<FeedItem[]> {
  const out: FeedItem[] = [];
  for (const src of SOURCES_JSON) {
    if (categoryParam && src.category !== categoryParam) continue;
    try {
      const res = await fetch(src.url, {
        headers: { 'User-Agent': 'thandev-news/1.0', Accept: 'application/json' },
        cache: 'no-store',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (src.kind === 'cisa-kev') {
        const vulns = Array.isArray(data?.vulnerabilities) ? data.vulnerabilities : [];
        for (const v of vulns) {
          const cve = v?.cveID || 'CVE';
          const title = `${cve}: ${v?.shortDescription || 'Known exploited vulnerability'}`;
          const date = v?.dateAdded ? new Date(v.dateAdded).toISOString() : new Date().toISOString();
          const url = 'https://www.cisa.gov/known-exploited-vulnerabilities-catalog';
          out.push({
            id: `${src.source}:${cve}`,
            title,
            url,
            source: src.source,
            publishedAt: date,
            summary: [
              v?.vendorProject && `Vendor: ${v.vendorProject}`,
              v?.product && `Product: ${v.product}`,
              v?.dueDate && `Due: ${v.dueDate}`,
            ].filter(Boolean).join(' · ').slice(0, 240),
            category: src.category,
            image: null,
          });
        }
      }
    } catch (e: any) {
      console.error(`[news] Failed ${src.source}: ${e?.message || e}`);
    }
  }
  return out;
}
>>>>>>> origin/main

export const revalidate = 600;

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const categoryParam = (searchParams.get('category') as FeedItem['category'] | null) ?? null;
  const q = (searchParams.get('q') || '').toLowerCase();
  const strict = (searchParams.get('strict') ?? '1') === '1';
  const breaking = (searchParams.get('breaking') ?? '0') === '1'; // NEW
  const limitParam = parseInt(searchParams.get('limit') || '0', 10);

  const [rssItems, jsonItems] = await Promise.all([fetchRSS(categoryParam), fetchJSON(categoryParam)]);
  let items = [...rssItems, ...jsonItems];

  // De-dup + sort newest
  const unique = new Map<string, FeedItem>();
  for (const r of items) if (!unique.has(r.id)) unique.set(r.id, r);
  items = Array.from(unique.values()).sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));

  // Strict relevance
  if (strict) items = items.filter((i) => scoreItem(i.title, i.summary, i.source) >= 2);

  // Text search
  if (q) {
<<<<<<< HEAD
    const text = (s: string) => s.toLowerCase();
    items = items.filter(i => text(i.title+ ' ' +i.summary+ ' ' +i.source).includes(q));
  }

  return NextResponse.json({ items: items.slice(0, limit) });
=======
    items = items.filter(
      (i) =>
        i.title.toLowerCase().includes(q) ||
        i.summary.toLowerCase().includes(q) ||
        i.source.toLowerCase().includes(q)
    );
  }

  // Drop obvious HN meta
  items = items.filter((i) => !/^ask hn|^show hn/i.test(i.title));

  // Breaking mode: prioritize hottest keywords & most recent
  if (breaking) {
    const hot = (i: FeedItem) =>
      scoreItem(i.title, i.summary, i.source) +
      (/(cve|zero-?day|ransomware|exploit|kev|actively exploited)/i.test(`${i.title} ${i.summary}`) ? 2 : 0);
    items = items
      .sort((a, b) => {
        const s = hot(b) - hot(a);
        return s !== 0 ? s : +new Date(b.publishedAt) - +new Date(a.publishedAt);
      });
  }

  // Clamp
  const clamp = limitParam > 0 ? limitParam : breaking ? 8 : 100;
  items = items.slice(0, clamp);

  return NextResponse.json({ items });
>>>>>>> origin/main
}
