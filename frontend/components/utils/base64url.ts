// Make sure a raw URL becomes a safe http(s) URL
export function b64urlEncode(raw: string): string {
  if (!raw) return '#';
  let s = raw.trim();

  // protocol-relative => https
  if (s.startsWith('//')) s = 'https:' + s;

  // add https if missing a scheme
  if (!/^https?:\/\//i.test(s)) s = 'https://' + s;

  // Validate/normalize; fall back to encodeURI (handles spaces, unicode)
  try {
    const u = new URL(s);
    return u.toString();
  } catch {
    return encodeURI(s);
  }
}
