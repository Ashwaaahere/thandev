"use client";
import { useEffect, useRef } from "react";
import type { ReactNode, MouseEventHandler } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import dynamic from "next/dynamic";
const BreakingNews = dynamic(() => import("@/components/BreakingNews"), { ssr: false });
import HeroAurora from '@/components/HeroAurora';
import AnimatedCard from '@/components/AnimatedCard';



/**
 * Decorative animated background orbs (pure client-side, no Tailwind config needed)
 */
function Orbs() {
  const orbs = [
    { className: "bg-cyan-500/25", size: 280, x: -180, y: -60, delay: 0 },
    { className: "bg-indigo-500/20", size: 360, x: 120, y: -100, delay: 0.4 },
    { className: "bg-emerald-400/20", size: 220, x: 220, y: 120, delay: 0.8 },
  ];
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {orbs.map((o, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.2, delay: o.delay }}
          className={`absolute blur-3xl ${o.className} rounded-full`}
          style={{ width: o.size, height: o.size, left: `calc(50% + ${o.x}px)`, top: `calc(30% + ${o.y}px)` }}
        />
      ))}
    </div>
  );
}

/**
 * Soft spotlight under the hero headline
 */
function Spotlight() {
  return (
    <div aria-hidden className="absolute -top-32 left-1/2 -translate-x-1/2 h-[480px] w-[840px] rounded-full opacity-30 blur-3xl"
      style={{
        background: "radial-gradient(50% 50% at 50% 50%, rgba(99,102,241,0.35) 0%, rgba(15,23,42,0) 70%)",
      }}
    />
  );
}

/**
 * Simple, safe in-page anchor link with smooth scroll & history guards
 */
function AnchorLink({ href, className, children }: { href: string; className?: string; children: ReactNode }) {
  const onClick: MouseEventHandler<HTMLAnchorElement> = (e) => {
    if (!href || !href.startsWith("#")) return;
    if (typeof document === "undefined") return;
    const id = href.slice(1);
    let el: HTMLElement | null = null;
    try { el = document.getElementById(id); } catch { el = null; }
    if (el && typeof (el as any).scrollIntoView === "function") {
      e.preventDefault();
      try { el.scrollIntoView({ behavior: "smooth", block: "start" }); } catch {}
      if (typeof window !== "undefined" && typeof window.history?.replaceState === "function") {
        try { window.history.replaceState(null, "", href); } catch {}
      }
    }
  };
  return <a href={href} onClick={onClick} className={className}>{children}</a>;
}

/**
 * Developer-only diagnostics to ensure anchor IDs exist
 */
function Diagnostics() {
  useEffect(() => {
    const required = ["product","features","developers","pricing","faq","signup","demo"];
    const missing = required.filter((id) => !document.getElementById(id));
    const holder = document.getElementById("dev-tests");
    if (holder) holder.setAttribute("data-tests", JSON.stringify({ missing }));
    // eslint-disable-next-line no-console
    console.debug("[Thandev Diagnostics]", { missing });
  }, []);
  return <div id="dev-tests" data-tests="{}" className="hidden"/>;
}

/**
 * Animated horizontal ticker for the hero (fake content for now)
 */
function NewsTicker() {
  const items = [
    "CVE-2025-1234 RCE in ExampleCMS", "KEV: VendorX auth bypass actively exploited", "PoC released for CVE-2025-2222",
    "Zero-day in WidgetOS mitigated", "High EPSS spike for CVE-2025-0420",
  ];
  const row = (
    <div className="flex shrink-0 items-center gap-6 pr-6">
      {items.map((t, i) => (
        <span key={i} className="whitespace-nowrap text-xs text-slate-300/80">
          <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-cyan-400"/>{t}
        </span>
      ))}
    </div>
  );
  return (
    <div aria-label="Live ticker" className="relative mt-8 overflow-hidden rounded-xl border border-white/10 bg-white/5">
      <motion.div
        className="flex"
        animate={{ x: [0, -800] }}
        transition={{ duration: 18, ease: "linear", repeat: Infinity }}
      >
        {row}
        {row}
        {row}
      </motion.div>
    </div>
  );
}

/**
 * Subtle parallax wrapper for the hero right card
 */
function ParallaxCard({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  return (
    <motion.div
      ref={ref}
      initial={{ y: 16, opacity: 0 }}
      whileInView={{ y: 0, opacity: 1 }}
      viewport={{ once: true, amount: 0.4 }}
      transition={{ duration: 0.7, ease: "easeOut" }}
      whileHover={{ y: -4 }}
      className="relative"
    >
      {children}
    </motion.div>
  );
}

export default function ThandevLanding() {
  return (
    <main className="min-h-screen scroll-smooth">
    
      <Diagnostics />

      {/* HERO */}
        <section id="product" className="relative overflow-hidden">
          {/* background glow & blobs */}
          <div className="absolute inset-0 z-0">
            <HeroAurora />
          </div>

          <div className="relative z-10 mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 px-6 py-20 md:grid-cols-2 md:py-28">
            <div>
              <h1 className="text-4xl md:text-6xl font-semibold tracking-tight">See cyberspace in real time.<br/>Scan early. Ship safe.</h1>
              <p className="mt-4 max-w-xl text-[var(--muted)]">
                Thandev is a developer-first security space: live feed, instant scans, and dev-time checks.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <a href="#signup" className="btn-brand">Start free</a>
                <a href="#demo" className="btn-ghost">View demo</a>
              </div>
            </div>

            <div className="hero-surface p-5 shadow-deep">
              <AnimatedCard className="hero-surface p-5 shadow-deep">
  <div className="flex items-center justify-between">
    <h3 className="text-lg font-semibold">Quick Start</h3>
    {/* subtle toolbar pills */}
    <div className="hidden sm:flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
      <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
      <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
    </div>
  </div>

  <div className="mt-3 h-px w-full bg-gradient-to-r from-transparent via-[var(--hairline)] to-transparent" />

  {/* Frosted code block with toolbar */}
  <figure className="mt-4 overflow-hidden rounded-2xl border card-border shadow-soft">
    <div className="flex items-center justify-between px-3 py-2 backdrop-blur-md bg-white/45 dark:bg-slate-900/30">
      <div className="text-xs font-mono text-[var(--muted)]">Thandev • guide</div>
      
    </div>

   <pre className="font-code text-[13px] leading-[1.6] px-4 py-4 sm:px-6 sm:py-5
             backdrop-blur-md
             dark:text-slate-100 dark:bg-slate-900/35">
      {`# Browse live news feed
    ${process.env.NEXT_PUBLIC_API_BASE ?? "https://api.thandev.dev"}/news

    # Run a site scan in browser
    Dashboard → New Scan → Enter URL

    # Scan development build in browser
    Dashboard → Upload Build → Start Scan`}
    </pre>

  </figure>

  <div className="mt-4 flex items-center gap-3 text-xs text-[var(--muted)]">
    <span className="rounded-full px-2.5 py-1 bg-emerald-400/10 text-emerald-700 dark:text-emerald-300 border border-emerald-400/20">MVP online</span>
    <span className="rounded-full px-2.5 py-1 bg-indigo-400/10 text-indigo-700 dark:text-indigo-300 border border-indigo-400/20">LLM soon</span>
  </div>
              </AnimatedCard>

            </div>
          </div>

          <div className="section-sep mx-auto mt-6 w-[90%]" />
        </section>



      {/* BREAKING NEWS (compact) */}
      <section id="breaking" className="mx-auto max-w-7xl px-6 py-10">
        <BreakingNews />
      </section>


      {/* FEATURES */}
      {/* FEATURES — minimal rows in a soft band */}
      <section id="features" className="band">
        <div className="mx-auto max-w-7xl px-6 py-20 md:py-28">
          <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">
            Your security control room
          </h2>

          {/* 3 feature rows, no boxed cards */}
          <div className="mt-8 md:mt-10 grid gap-6 md:grid-cols-3">
            {[
              {
                title: "Live Cyber News Feed",
                body:
                  "Real-time CVE, KEV, vendor advisories, and PoCs. Filter by product, severity, exploit activity, and tags.",
              },
              {
                title: "Instant Site & App Scans",
                body:
                  "Kick off Nuclei/ZAP scans from the dashboard. Findings link to CVEs and live exploit intel so you fix what matters.",
              },
              {
                title: "Scan During Development (Shift-Left)",
                body:
                  "Scan local builds and preview deployments in the browser to catch exploitable issues before release.",
              },
            ].map((f, i) => (
              <div key={f.title} className="tile">
                <div className="text-sm muted mb-1">{`0${i + 1}`}</div>
                <h3 className="text-lg md:text-xl font-semibold flex items-center">
                  <span className="dot" /> {f.title}
                </h3>
                <p className="mt-2 text-sm muted">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      


      {/* DEVELOPERS — contrasting band with 2 wide tiles */}
      <section id="developers" className="band-alt">
        <div className="mx-auto max-w-7xl px-6 py-20 md:py-28">
          <div className="grid gap-10 md:grid-cols-2">
            {[
              {
                title: "Actionable insights",
                body:
                  "Every finding is enriched with CVE, KEV, exploit and EPSS context so you know exactly what to fix first.",
              },
              {
                title: "Seamless workflow",
                body:
                  "Works with your tools — GitHub, Slack and CI/CD. Assign, track and resolve without breaking your flow.",
              },
            ].map((card) => (
              <div key={card.title} className="tile">
                <h3 className="text-xl font-semibold flex items-center">
                  <span className="dot" /> {card.title}
                </h3>
                <p className="mt-2 text-sm muted">{card.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>


      {/* PRICING */}
      <section id="pricing" className="mx-auto max-w-7xl px-6 py-16 md:py-24">
        <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">Simple pricing</h2>
        <div className="mt-8 grid gap-6 md:grid-cols-3">
          {[
            { name: "Free", price: "$0", features: ["Live feed", "Manual scans", "Community"], cta: "Start free" },
            { name: "Personal", price: "$9/mo", features: ["Scheduled scans", "Saved filters", "Email alerts"], cta: "Upgrade" },
            { name: "Team", price: "$49/mo", features: ["API access", "Slack alerts", "SAML/SSO"], cta: "Contact sales" }
          ].map((p, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.2 }} transition={{ duration: 0.6, delay: i * 0.05 }} whileHover={{ y: -4 }} className="rounded-2xl border border-white/10 p-6 bg-white/5">
              <div className="text-sm ">{p.name}</div>
              <div className="mt-2 text-3xl font-semibold">{p.price}</div>
              <ul className="mt-4 space-y-2 text-sm ">
                {p.features.map((f, j) => (
                  <li key={j}>{f}</li>
                ))}
              </ul>
              <AnchorLink href="#signup" className="mt-6 inline-block rounded-xl bg-white px-4 py-2 font-semibold text-slate-900 hover:bg-slate-200">{p.cta}</AnchorLink>
            </motion.div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-5xl px-6 py-16 md:py-24">
        <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">FAQ</h2>
        <div className="mt-6 space-y-4">
          {[
            { q: 'Is Thandev open-source?', a: 'The feed and scanner connectors aim to be OSS-friendly; enterprise features are paid.' },
            { q: 'How is this different from a news aggregator?', a: 'We enrich with EPSS/KEV/PoC signals and link directly to your scans.' },
            { q: 'When is the AI assistant coming?', a: 'Soon. We’re adding pgvector & RAG for remediation chat and semantic search.' },
          ].map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ duration: 0.6, delay: i * 0.05 }}
              className="card p-5 transition-colors shadow-sm"
            >
              <div className="font-medium">{f.q}</div>
              <div className="mt-1 text-sm muted">{f.a}</div>
            </motion.div>
          ))}
        </div>
      </section>



      {/* SIGNUP */}
      <section id="signup" className="mx-auto max-w-3xl px-6 pb-20">
        <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.3 }} transition={{ duration: 0.6 }} className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center">
          <h3 className="text-xl font-semibold">Ready to see your attack surface?</h3>
          <p className="mt-2 text-sm text-slate-300">Create an account to stream the live feed, run your first scan, and set up dev‑time checks.</p>
          <div className="mt-4 flex justify-center gap-3">
            <Link href="/signup" className="rounded-xl bg-white px-4 py-2 font-semibold text-slate-900 hover:bg-slate-200">Create account</Link>
            <Link href="/docs" className="rounded-xl border border-white/10 px-4 py-2 font-semibold hover:bg-white/5">Read docs</Link>
          </div>
        </motion.div>
      </section>

      
    </main>
  );
}
