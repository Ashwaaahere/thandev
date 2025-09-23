// components/utils/format.ts
export const timeAgo = (iso: string) => {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const d = Math.max(0, now - then);
  const m = Math.floor(d / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  return `${days}d ago`;
};

export const hostFromUrl = (url: string) => {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; }
};
