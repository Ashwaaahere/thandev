// frontend/lib/importance.ts
export type NewsItem = {
  id?: string;
  url: string;
  title: string;
  image?: string | null;
  source?: string;
  publishedAt?: string; // ISO timestamp
  certified?: boolean;
};

const SOURCE_BOOST: Record<string, number> = {
  "CISA KEV": 30,
  "MSRC": 20,
  "The Hacker News": 10,
  "BleepingComputer": 10,
  "KrebsOnSecurity": 10,
};

export function scoreItem(it: NewsItem): number {
  let score = 0;

  // Recency (max 40 pts, within ~48h)
  if (it.publishedAt) {
    const hours = (Date.now() - new Date(it.publishedAt).getTime()) / 36e5;
    const recency = Math.max(0, 48 - Math.min(hours, 48));
    score += (recency / 48) * 40;
  }

  // Certified boost
  if (it.certified) score += 25;

  // Source boost
  if (it.source && SOURCE_BOOST[it.source]) score += SOURCE_BOOST[it.source];

  // Keyword hints
  const t = (it.title || "").toLowerCase();
  if (/\b(cve|zero[- ]day|rce|kev|actively exploited|patch)\b/.test(t)) score += 10;

  return Math.round(score);
}

export function importanceLabel(score: number): "High" | "Medium" | "Low" {
  if (score >= 55) return "High";
  if (score >= 30) return "Medium";
  return "Low";
}
