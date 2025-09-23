export default function DocsPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">Documentation</h1>
        <p className="mt-4 text-lg text-slate-600 dark:text-slate-400">
          Coming soon - comprehensive documentation for Thandev
        </p>
      </div>
      
      <div className="mt-16 grid gap-8 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-xl font-semibold">API Reference</h2>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Complete API documentation for integrating with Thandev
          </p>
        </div>
        
        <div className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-xl font-semibold">Getting Started</h2>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Quick start guide for developers
          </p>
        </div>
      </div>
    </main>
  );
}
