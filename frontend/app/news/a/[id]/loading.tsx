'use client';

export default function ArticleLoading() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-8">
      {/* Top navigation bar skeleton */}
      <div className="mb-8 flex items-center justify-between">
        <div className="h-4 w-24 bg-[var(--muted)]/20 rounded animate-pulse" />
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-[var(--brand)]/50 animate-pulse" />
          <div className="h-4 w-12 bg-[var(--muted)]/20 rounded animate-pulse" />
          <div className="h-8 w-24 bg-[var(--brand)]/20 rounded-lg animate-pulse" />
        </div>
      </div>

      {/* Hero section skeleton */}
      <div className="relative mb-8 overflow-hidden rounded-3xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/5 to-transparent" />
        
        {/* Image skeleton */}
        <div className="h-64 w-full bg-[var(--muted)]/10 animate-pulse md:h-96" />

        <div className="relative z-10 p-6 md:p-8">
          {/* Title skeleton */}
          <div className="space-y-3 mb-4">
            <div className="h-8 w-full bg-[var(--muted)]/20 rounded animate-pulse" />
            <div className="h-8 w-3/4 bg-[var(--muted)]/20 rounded animate-pulse" />
          </div>

          {/* Excerpt skeleton */}
          <div className="space-y-2 mb-6">
            <div className="h-4 w-full bg-[var(--muted)]/20 rounded animate-pulse" />
            <div className="h-4 w-5/6 bg-[var(--muted)]/20 rounded animate-pulse" />
            <div className="h-4 w-4/5 bg-[var(--muted)]/20 rounded animate-pulse" />
          </div>

          {/* Meta info skeleton */}
          <div className="flex items-center gap-4">
            <div className="h-4 w-32 bg-[var(--muted)]/20 rounded animate-pulse" />
            <div className="h-4 w-2 bg-[var(--muted)]/20 rounded animate-pulse" />
            <div className="h-4 w-24 bg-[var(--muted)]/20 rounded animate-pulse" />
          </div>
        </div>
      </div>

      {/* Article content skeleton */}
      <article className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 md:p-8 backdrop-blur-sm">
        <div className="absolute inset-0 bg-gradient-to-br from-[var(--brand)]/2 to-transparent" />
        
        <div className="relative z-10 space-y-4">
          {/* Content paragraphs */}
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <div className="h-4 w-full bg-[var(--muted)]/20 rounded animate-pulse" />
              <div className="h-4 w-full bg-[var(--muted)]/20 rounded animate-pulse" />
              <div className="h-4 w-3/4 bg-[var(--muted)]/20 rounded animate-pulse" />
            </div>
          ))}
        </div>
      </article>

      {/* Bottom navigation skeleton */}
      <div className="mt-8 flex items-center justify-between">
        <div className="h-8 w-24 bg-[var(--muted)]/20 rounded-lg animate-pulse" />
        <div className="h-8 w-32 bg-[var(--brand)]/20 rounded-lg animate-pulse" />
      </div>
    </main>
  );
}
