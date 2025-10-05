'use client';

export default function Footer() {
  return (
    <footer className="border-t card-border"
        style={{ background: 'color-mix(in oklab, var(--bg) 92%, white 8%)' }}>
      <div className="mx-auto max-w-7xl px-6 py-10 text-sm text-[var(--muted)]">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2 ">
            <div className="h-6 w-6 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
            <span>© {new Date().getFullYear()} Thandev</span>
          </div>
          <div className="flex items-center gap-6 text-sm">
            <a className="hover:text-slate-100" href="/news">News</a>
            <a className="hover:text-slate-100" href="/exploits">Exploit Feeds</a>
            <a className="hover:text-slate-100" href="/dashboard/scan">Security Scan</a>
            <a className="hover:text-slate-100" href="/docs">Docs</a>
            <a className="hover:text-slate-100" href="/security">Security</a>
            <a className="hover:text-slate-100" href="/terms">Terms</a>
            <a className="hover:text-slate-100" href="/privacy">Privacy</a>
          </div>
        </div>

        <p className="mt-4 text-xs text-slate-500">
          News content and trademarks belong to their respective owners. Thandev aggregates headlines and excerpts for informational purposes and links to the original source.
        </p>
      </div>
    </footer>
  );
}
