// app/news/page.tsx
import NewsClient from "@/components/News/NewsClient";

export default function NewsPage() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Futuristic background effects */}
      <div className="absolute inset-0 hero-aurora">
        <div className="hero-aurora-glow absolute inset-0 bg-gradient-to-br from-blue-400/8 via-purple-400/12 to-cyan-400/8 animate-pulse" />
        <div className="hero-aurora-blob absolute top-1/4 left-1/4 w-96 h-96 bg-blue-400/15 rounded-full blur-3xl animate-pulse" />
        <div className="hero-aurora-blob absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple-400/15 rounded-full blur-3xl animate-pulse" />
        <div className="hero-aurora-blob absolute top-1/2 left-1/2 w-64 h-64 bg-cyan-400/10 rounded-full blur-3xl animate-pulse" />
      </div>

      {/* Animated grid pattern overlay */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
           style={{
             backgroundImage: `
               linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
               linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)
             `,
             backgroundSize: '60px 60px',
             animation: 'grid-move 20s linear infinite'
           }} />

      {/* Floating particles */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 rounded-full animate-pulse"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 5}s`,
              animationDuration: `${3 + Math.random() * 4}s`,
              background: 'var(--brand)',
              opacity: 0.4,
            }}
          />
        ))}
      </div>

      {/* Main content with futuristic styling */}
      <main className="relative z-10">
        <section className="relative">
          {/* Enhanced hero glow backdrop */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "radial-gradient(50% 55% at 12% 0%, var(--orb-indigo) 0%, transparent 60%), radial-gradient(36% 50% at 96% 0%, var(--orb-emerald) 0%, transparent 60%)",
              opacity: 0.8,
              filter: "saturate(1.1) blur(15px)",
            }}
          />

          <div className="relative mx-auto max-w-7xl px-6 pt-12">
            {/* Futuristic title */}
            <div className="mb-12 text-center">
              <h1 className="text-4xl md:text-6xl font-bold title-future mb-4">
                Latest News
              </h1>
              <div className="w-24 h-1 mx-auto bg-gradient-to-r from-transparent via-var(--brand) to-transparent rounded-full" />
              <p className="mt-6 text-lg text-[var(--muted)] max-w-2xl mx-auto">
                Stay ahead with real-time security intelligence and breaking news
              </p>
            </div>

            {/* Use client component for data fetching */}
            <NewsClient />
          </div>

          <div className="h-20" />
        </section>
      </main>

      {/* Vignette effect */}
      <div className="absolute inset-0 pointer-events-none" 
           style={{
             background: 'radial-gradient(80% 80% at 50% 50%, transparent 0%, rgba(0,0,0,.1) 100%)'
           }} />
    </div>
  );
}
