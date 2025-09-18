// app/components/utils/urls.ts

/**
 * Normalize any raw URL into a proper http(s) URL
 * - Adds https:// if missing
 * - Handles protocol-relative links (//example.com)
 * - Ensures it’s safe for use in href
 */
export function normalizeExternalUrl(raw: string): string {
  if (!raw) return '#';
  let s = raw.trim();

  // protocol-relative → https://
  if (s.startsWith('//')) s = 'https:' + s;

  // add https:// if no scheme
  if (!/^https?:\/\//i.test(s)) s = 'https://' + s;

  // Validate/normalize; fallback to encodeURI
  try {
    const u = new URL(s);
    return u.toString();
  } catch {
    return encodeURI(s);
  }
}
