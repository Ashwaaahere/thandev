// components/utils/getBaseUrl.ts
import { headers } from 'next/headers';

/**
 * Returns an absolute origin (https://host) that works on Vercel and locally.
 * - Honors NEXT_PUBLIC_API_BASE if you set it (e.g. https://yourdomain.com)
 * - Falls back to request headers (x-forwarded-proto/host)
 * - Finally falls back to http://localhost:3000
 */
export function getBaseUrl(): string {
  // 1) explicit env (best)
  const envBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (envBase) return envBase.replace(/\/+$/, '');

  // 2) derive from incoming request (works on Vercel/Reverse proxy)
  try {
    const h = headers();
    const host = h.get('x-forwarded-host') || h.get('host');
    const proto = h.get('x-forwarded-proto') || 'http';
    if (host) return `${proto}://${host}`;
  } catch {
    // headers() may throw if called in non-request context; ignore
  }

  // 3) last resort (local dev)
  return 'http://localhost:3000';
}
