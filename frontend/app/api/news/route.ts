import 'server-only';
import { NextResponse } from 'next/server';
import Parser from 'rss-parser';

type FeedItem = {
  id: string;
  title: string;
  url: string;
  source: string;
  publishedAt: string; // ISO
  summary: string;
  category: 'cyber' | 'ai' | 'tech';
  image?: string | null;
  certified: boolean;
};

const parser = new Parser({
  headers: { 'User-Agent': 'thandev-news/1.0 (+https://github.com/Ashwaaahere/thandev)' },
});

/** -------------------- CERTIFIED SOURCES ONLY -------------------- **/
const SOURCES_RSS: Array<{ url: string; source: string; category: FeedItem['category']; certified: boolean }> = [
  // Cybersecurity
  { url: 'https://feeds.feedburner.com/TheHackersNews',         source: 'The Hacker News',       category: 'cyber', certified: true },
  { url: 'https://www.bleepingcomputer.com/feed/',              source: 'BleepingComputer',      category: 'cyber', certified: true },
  { url: 'https://krebsonsecurity.com/feed/',                   source: 'Krebs on Security',     category: 'cyber', certified: true },
  { url: 'https://isc.sans.edu/rssfeed.xml',                    source: 'SANS ISC Diary',        category: 'cyber', certified: true },
  { url: 'https://www.zerodayinitiative.com/blog?format=rss',   source: 'ZDI',                   category: 'cyber', certified: true },
  { url: 'https://www.darkreading.com/rss.xml',                 source: 'Dark Reading',          category: 'cyber', certified: true },

  // Tech / security
  { url: 'https://arstechnica.com/security/feed/',              source: 'Ars Technica Security', category: 'tech',  certified: true },
];

/** -------------------- helpers -------------------- **/
function daysAgo(n: number) { return Date.now() - n * 24 * 60 * 60 * 1000; }
function isRecent(iso: string, sinceMs: number) {
  const t = new Date(iso).getTime();
  return !Number.isNaN(t) && t >= sinceMs;
}

function isValidImageUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  
  try {
    const parsedUrl = new URL(url);
    // Only allow HTTPS images for security
    if (parsedUrl.protocol !== 'https:') return false;
    
    // Check if it's a valid image extension or data URL
    const validExtensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg'];
    const hasValidExtension = validExtensions.some(ext => 
      parsedUrl.pathname.toLowerCase().includes(ext)
    );
    
    return hasValidExtension || url.startsWith('data:');
  } catch {
    return false;
  }
}

async function extractImage(it: any, source: string, articleIndex: number = 0): Promise<string | null> {
  // First try standard RSS image fields
  if (it?.enclosure?.url) {
    const url = it.enclosure.url as string;
    if (isValidImageUrl(url)) return url;
  }
  
  const media = (it as any)['media:content'] || (it as any)['media:thumbnail'];
  if (media?.url) {
    const url = media.url as string;
    if (isValidImageUrl(url)) return url;
  }
  if (Array.isArray(media) && media[0]?.url) {
    const url = media[0].url as string;
    if (isValidImageUrl(url)) return url;
  }
  
  // Try to extract from HTML content
  const html = (it?.content || it?.['content:encoded'] || '') as string;
  const m = html.match(/<img[^>]+src=["']([^"']+)["']/i);
  if (m?.[1]) {
    const url = m[1];
    if (isValidImageUrl(url)) return url;
  }
  
  // For sources that don't provide images in RSS, try to fetch from article page
  // Only fetch for first 2 articles to avoid performance issues in production
  if ((source === 'BleepingComputer' || source === 'Krebs on Security' || source === 'SANS ISC Diary') && it?.link && articleIndex < 2) {
    try {
      const response = await fetch(it.link, {
        headers: { 
          'User-Agent': 'thandev-news/1.0 (+https://github.com/Ashwaaahere/thandev)',
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'Accept-Language': 'en-US,en;q=0.5',
          'Accept-Encoding': 'gzip, deflate',
          'Connection': 'keep-alive',
        },
        signal: AbortSignal.timeout(5000) // Increased timeout for production
      });
      if (response.ok) {
        const html = await response.text();
        
        // Look for article-specific images first (main content area)
        const articleMatch = html.match(/<article[^>]*>[\s\S]*?<img[^>]+(?:data-src|src)=["']([^"']+)["'][\s\S]*?<\/article>/i);
        if (articleMatch?.[1] && isValidImageUrl(articleMatch[1])) return articleMatch[1];
        
        // Look for images in the main content area
        const contentMatch = html.match(/<div[^>]*class="[^"]*content[^"]*"[^>]*>[\s\S]*?<img[^>]+(?:data-src|src)=["']([^"']+)["'][\s\S]*?<\/div>/i);
        if (contentMatch?.[1] && isValidImageUrl(contentMatch[1])) return contentMatch[1];
        
        // Look for lazy-loaded images with data-src attribute (prefer article-specific images)
        const lazyMatches = html.match(/<img[^>]+data-src=["']([^"']+)["']/gi);
        if (lazyMatches) {
          // First pass: look for high-quality article images
          for (const match of lazyMatches) {
            const url = match.match(/data-src=["']([^"']+)["']/i)?.[1];
            if (url && isValidImageUrl(url) && 
                !url.includes('logo') && 
                !url.includes('avatar') &&
                url.includes('hl-images') &&
                !url.includes('thumb')) {
              return url;
            }
          }
          
          // Second pass: accept thumbnail images as fallback
          for (const match of lazyMatches) {
            const url = match.match(/data-src=["']([^"']+)["']/i)?.[1];
            if (url && isValidImageUrl(url) && 
                !url.includes('logo') && 
                !url.includes('avatar') &&
                url.includes('hl-images')) {
              return url;
            }
          }
        }
        
        // Fallback to regular src attribute (prefer article-specific images)
        const srcMatches = html.match(/<img[^>]+src=["']([^"']+)["']/gi);
        if (srcMatches) {
          // First pass: look for high-quality article images
          for (const match of srcMatches) {
            const url = match.match(/src=["']([^"']+)["']/i)?.[1];
            if (url && isValidImageUrl(url) && 
                !url.includes('logo') && 
                !url.includes('avatar') &&
                url.includes('hl-images') &&
                !url.includes('thumb')) {
              return url;
            }
          }
          
          // Second pass: accept thumbnail images as fallback
          for (const match of srcMatches) {
            const url = match.match(/src=["']([^"']+)["']/i)?.[1];
            if (url && isValidImageUrl(url) && 
                !url.includes('logo') && 
                !url.includes('avatar') &&
                url.includes('hl-images')) {
              return url;
            }
          }
        }
      }
    } catch (e) {
      console.warn(`Failed to fetch image from ${it.link}:`, e);
      // Don't throw error, just continue without image
    }
  }
  
  return null;
}

async function normalizeRSS(item: any, src: { source: string; category: FeedItem['category']; certified: boolean }, articleIndex: number = 0): Promise<FeedItem | null> {
  const title = (item?.title ?? '').toString();
  const link  = (item?.link  ?? '').toString();
  if (!title || !link) return null;

  const dateRaw = item.isoDate || item.pubDate || '';
  const publishedAt = dateRaw ? new Date(dateRaw).toISOString() : new Date().toISOString();
  const plain = (item.contentSnippet || item.content || '').toString().replace(/<[^>]+>/g, '').trim();
  const image = await extractImage(item, src.source, articleIndex);

  return {
    id: `${src.source}:${link}`,
    title,
    url: link,
    source: src.source,
    publishedAt,
    summary: plain.slice(0, 260),
    category: src.category,
    image: image || null,
    certified: !!src.certified,
  };
}

/** -------------------- handler -------------------- **/
export const revalidate = 600;

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const category = (searchParams.get('category') as FeedItem['category'] | null) ?? null;
  const sinceDays = parseInt(searchParams.get('sinceDays') || '21', 10);
  const limit     = parseInt(searchParams.get('limit')     || '60', 10);
  const sinceMs   = daysAgo(Math.max(1, sinceDays));
  const certifiedOnly = (searchParams.get('certifiedOnly') ?? '1') === '1';
  const q = (searchParams.get('q') || '').toLowerCase();

  const items: FeedItem[] = [];
  await Promise.all(
    SOURCES_RSS.map(async (s) => {
      if (category && s.category !== category) return;
      try {
        // Add timeout to prevent hanging in production
        const timeoutPromise = new Promise((_, reject) => 
          setTimeout(() => reject(new Error('RSS feed timeout')), 15000)
        );
        
        const feedPromise = parser.parseURL(s.url);
        const feed = await Promise.race([feedPromise, timeoutPromise]) as any;
        
        for (let i = 0; i < (feed.items || []).length; i++) {
          const it = feed.items[i];
          const n = await normalizeRSS(it, s, i);
          if (n) items.push(n);
        }
      } catch (e: any) {
        console.error('[news] source failed', s.source, e?.message || e);
        // Continue with other sources even if one fails
      }
    })
  );

  // de-dup by URL
  const map = new Map<string, FeedItem>();
  for (const i of items) if (!map.has(i.url)) map.set(i.url, i);

  let out = Array.from(map.values())
    .filter((i) => isRecent(i.publishedAt, sinceMs))
    .sort((a, b) => +new Date(b.publishedAt) - +new Date(a.publishedAt));

  if (certifiedOnly) out = out.filter((i) => i.certified);

  if (q) {
    const T = (s: string) => s.toLowerCase();
    out = out.filter((i) => T(`${i.title} ${i.summary} ${i.source}`).includes(q));
  }

  // If no items found, return empty array instead of error
  if (out.length === 0) {
    console.warn('[news] No items found for category:', category, 'sinceDays:', sinceDays);
  }

  return NextResponse.json({ 
    items: out.slice(0, limit),
    total: out.length,
    sources_checked: SOURCES_RSS.length
  });
}
