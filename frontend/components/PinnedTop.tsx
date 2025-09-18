// components/PinnedTop.tsx
'use client';

import PinnedTimeline from './PinnedTimeline';

type Item = {
  id?: string | number;
  url: string;
  title: string;
  summary?: string;
  image?: string | null;
  source?: string;
  publishedAt?: string; // ISO
};

export default function PinnedTop({ items = [] }: { items: Item[] }) {
  if (!items.length) return null;

  // Take the top 5 (include what used to be the feature)
  const topFive = items.slice(0, 5);

  return (
    <section className="w-full">
      <PinnedTimeline items={topFive} />
    </section>
  );
}
