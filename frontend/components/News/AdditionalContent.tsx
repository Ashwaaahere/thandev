// components/News/AdditionalContent.tsx
'use client';

export default function AdditionalContent() {
  return (
    <div className="space-y-6">
      {/* Security Stats */}
      <div className="rounded-2xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 backdrop-blur-sm">
        <h3 className="mb-4 text-lg font-semibold text-[var(--fg)] flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          Exploits Stats
        </h3>
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-[var(--muted)]">Threats Detected</span>
            <span className="text-lg font-bold text-[var(--brand)]">1,247</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-[var(--muted)]">CVEs Tracked</span>
            <span className="text-lg font-bold text-[var(--brand)]">892</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-[var(--muted)]">Active Campaigns</span>
            <span className="text-lg font-bold text-[var(--brand)]">156</span>
          </div>
        </div>
      </div>

      {/* Trending Topics */}
      <div className="rounded-2xl border border-[var(--brand)]/20 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 backdrop-blur-sm">
        <h3 className="mb-4 text-lg font-semibold text-[var(--fg)] flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-orange-500 animate-pulse" />
          Trending Topics
        </h3>
        <div className="space-y-2">
          {['Ransomware', 'Zero-Day', 'Supply Chain', 'AI Security', 'Cloud Threats'].map((topic, i) => (
            <div key={topic} className="flex items-center justify-between">
              <span className="text-sm text-[var(--muted)]">{topic}</span>
              <div className="flex items-center gap-1">
                <div className="h-1 w-16 bg-[var(--brand)]/20 rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-[var(--brand)] rounded-full transition-all duration-1000"
                    style={{ width: `${85 - i * 10}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--muted)]">{85 - i * 10}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
