'use client';

export default function NewsLoading() {
  return (
    <div className="min-h-screen flex items-center justify-center relative" style={{ background: 'var(--bg)' }}>
      {/* Subtle center-focused gradient */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="w-96 h-96 rounded-full bg-gradient-to-br from-blue-400/10 via-purple-400/15 to-cyan-400/10 blur-3xl animate-pulse" />
      </div>

      {/* Subtle particles around center */}
      <div className="absolute inset-0 overflow-hidden flex items-center justify-center">
        {[...Array(8)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 rounded-full animate-pulse"
            style={{
              left: `calc(50% + ${(Math.random() - 0.5) * 400}px)`,
              top: `calc(50% + ${(Math.random() - 0.5) * 400}px)`,
              animationDelay: `${Math.random() * 3}s`,
              animationDuration: `${2 + Math.random() * 2}s`,
              background: 'var(--brand)',
              opacity: 0.6,
            }}
          />
        ))}
      </div>

      {/* Main loading content */}
      <div className="relative z-10 text-center">
        {/* Animated logo */}
        <div className="mb-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl loading-float loading-glow" 
               style={{ 
                 background: 'linear-gradient(92deg, #60a5fa 0%, #a78bfa 35%, #22d3ee 70%, #60a5fa 100%)',
                 boxShadow: '0 10px 30px rgba(99,102,241,.25)'
               }} />
          <div className="text-2xl font-bold title-future animate-pulse">
            Thandev
          </div>
        </div>

        {/* Loading text with typewriter effect */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold mb-4" style={{ color: 'var(--fg)' }}>
            Loading
            <span className="inline-block w-1 h-8 ml-2 animate-pulse" style={{ background: 'var(--brand)' }} />
          </h1>
          <p className="text-lg" style={{ color: 'var(--muted)' }}>
            Fetching latest security news...
          </p>
        </div>

        {/* Animated progress bar */}
        <div className="w-80 mx-auto loading-scan">
          <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface)' }}>
            <div className="h-full rounded-full animate-pulse" 
                 style={{ 
                   width: '60%',
                   background: 'linear-gradient(92deg, #60a5fa 0%, #a78bfa 35%, #22d3ee 70%, #60a5fa 100%)'
                 }} />
          </div>
          <div className="mt-2 text-sm" style={{ color: 'var(--muted)' }}>
            Scanning RSS feeds...
          </div>
        </div>

        {/* Loading dots */}
        <div className="flex justify-center space-x-2 mt-8">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="w-2 h-2 rounded-full animate-bounce"
              style={{ 
                background: 'var(--brand)',
                animationDelay: `${i * 0.2}s` 
              }}
            />
          ))}
        </div>
      </div>

      {/* Subtle vignette effect */}
      <div className="absolute inset-0 pointer-events-none" 
           style={{
             background: 'radial-gradient(80% 80% at 50% 50%, transparent 0%, rgba(0,0,0,.05) 100%)'
           }} />
    </div>
  );
}
