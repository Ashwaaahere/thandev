'use client';

export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-slate-950 text-slate-300">
      <div className="mx-auto max-w-7xl px-6 py-8">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2 text-slate-400">
            <div className="h-6 w-6 rounded-lg bg-gradient-to-br from-cyan-400 to-indigo-500" />
            <span>© {new Date().getFullYear()} Thandev</span>
          </div>
          <div className="flex items-center gap-6 text-sm">
            <a className="hover:text-slate-100" href="/privacy">Privacy</a>
            <a className="hover:text-slate-100" href="/security">Security</a>
            <a className="hover:text-slate-100" href="/docs">Docs</a>
            <a className="hover:text-slate-100" href="https://github.com/" target="_blank" rel="noreferrer">GitHub</a>
          </div>
        </div>

        <p className="mt-4 text-xs text-slate-500">
          News content and trademarks belong to their respective owners. Thandev aggregates headlines and excerpts for informational purposes and links to the original source.
        </p>
      </div>
    </footer>
  );
}
