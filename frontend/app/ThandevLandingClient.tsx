"use client";

import { useEffect, useRef, useState } from "react";
import Hero from "@/components/landing/Hero";
import ProofStrip from "@/components/landing/ProofStrip";
import ModulesBento from "@/components/landing/ModulesBento";
import WhoItsFor from "@/components/landing/WhoItsFor";
import QuickStart60s from "@/components/landing/QuickStart60s";
import TrustSafety from "@/components/landing/TrustSafety";
import FinalCTA from "@/components/landing/FinalCTA";
import FAQ from "@/components/landing/FAQ";
import ScrollProgress from "@/components/landing/ScrollProgress";
import { GradientSeparator } from "@/components/landing/primitives";

/* ------------------------------------------------------------------ */
/* Live Stats (kept for platform stats section)                      */
/* ------------------------------------------------------------------ */

type LiveStats = {
  totalScans: number | null;
  totalProjects: number | null;
  totalVulnerabilities: number | null;
};

function useLiveStats(): LiveStats {
  const [stats, setStats] = useState<LiveStats>({
    totalScans: null,
    totalProjects: null,
    totalVulnerabilities: null,
  });

  useEffect(() => {
    // Try multiple backend URLs in order of preference
    const getBackendUrl = () => {
      if (process.env.NEXT_PUBLIC_API_BASE) {
        return process.env.NEXT_PUBLIC_API_BASE.replace(/\/$/, "");
      }
      // Try Azure Container Apps URL first (production)
      if (typeof window !== 'undefined' && window.location.hostname === 'thandev.io') {
        return "https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io";
      }
      // Fallback to Fly.dev
      return "https://thandev-backend.fly.dev";
    };

    const API = getBackendUrl();
    const statsUrl = `${API}/api/stats`;

    const fetchStats = async () => {
      try {
        // Add timeout and abort controller for better error handling
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
        
        const response = await fetch(statsUrl, {
          signal: controller.signal,
          headers: {
            'Accept': 'application/json',
          },
          mode: 'cors',
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          console.warn(`[Stats] API returned ${response.status}: ${response.statusText}`, {
            url: statsUrl,
            status: response.status,
          });
          return null;
        }
        
        const statsRes = await response.json();
        
        if (statsRes && typeof statsRes === 'object') {
          setStats({
            totalScans:
              typeof statsRes.total_scans === "number"
                ? statsRes.total_scans
                : statsRes.total_scans === 0
                  ? 0
                  : null,
            totalProjects:
              typeof statsRes.total_projects === "number"
                ? statsRes.total_projects
                : statsRes.total_projects === 0
                  ? 0
                  : null,
            totalVulnerabilities:
              typeof statsRes.total_vulnerabilities === "number"
                ? statsRes.total_vulnerabilities
                : statsRes.total_vulnerabilities === 0
                  ? 0
                  : null,
          });
          console.log('[Stats] Successfully fetched stats:', statsRes);
        } else {
          console.warn('[Stats] Invalid response format:', statsRes);
        }
      } catch (err: any) {
        clearTimeout(timeoutId);
        if (err.name !== 'AbortError') {
          console.error('[Stats] Fetch failed:', {
            error: err.message,
            url: statsUrl,
            name: err.name,
          });
        }
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  return stats;
}

/* ------------------------------------------------------------------ */
/* Count-up utility                                                    */
/* ------------------------------------------------------------------ */

function useCountUp(active: boolean, to: number, duration = 1000) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!ref.current) return;

    if (!active) {
      ref.current.textContent = to.toLocaleString();
      return;
    }

    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 4);
      const n = Math.round(to * eased);
      if (ref.current) {
        ref.current.textContent = n.toLocaleString();
      }
      if (p < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        if (ref.current) {
          ref.current.textContent = to.toLocaleString();
        }
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, to, duration]);
  return ref;
}

/* ------------------------------------------------------------------ */
/* Platform Stat Card                                                  */
/* ------------------------------------------------------------------ */

function PlatformStatCard({
  label,
  value,
  icon,
  gradient,
  textColor,
}: {
  label: string;
  value: number | null;
  icon: React.ReactNode;
  gradient: string;
  textColor: string;
}) {
  const hasValue = value !== null && value !== undefined;
  const displayValue = hasValue ? value : 0;
  const ref = useCountUp(hasValue, displayValue, 1000);

  return (
    <div className="group relative overflow-hidden rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur-sm transition-all hover:border-white/20 hover:bg-white/8">
      <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-0 transition-opacity duration-300 group-hover:opacity-20`} />
      <div className="relative flex items-center gap-3">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/5 ${textColor}`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="mb-1 text-xs uppercase tracking-wider text-slate-300 dark:text-slate-300">
            {label}
          </div>
          <div className={`text-xl font-bold tabular-nums ${textColor}`}>
            {value == null ? (
              <div className="h-6 w-16 animate-pulse rounded bg-slate-700/30" />
            ) : (
              <span ref={ref} className="inline-block min-w-[3ch]">
                {displayValue.toLocaleString()}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Diagnostics (kept for dev tools)                                   */
/* ------------------------------------------------------------------ */

function Diagnostics() {
  useEffect(() => {
    const required = [
      "product",
      "features",
      "who",
      "quickstart",
      "trust",
      "faq",
      "signup",
    ];
    const missing = required.filter((id) => !document.getElementById(id));
    const holder = document.getElementById("dev-tests");
    if (holder)
      holder.setAttribute("data-tests", JSON.stringify({ missing }));
    // eslint-disable-next-line no-console
    console.debug("[Thandev Diagnostics]", { missing });
  }, []);
  return <div id="dev-tests" data-tests="{}" className="hidden" />;
}

/* ------------------------------------------------------------------ */
/* Main Page                                                           */
/* ------------------------------------------------------------------ */

export default function ThandevLandingClient() {
  const live = useLiveStats();

  return (
    <main className="min-h-screen scroll-smooth bg-[var(--bg)]">
      <ScrollProgress />
      <Diagnostics />

      {/* Hero */}
      <Hero />

      {/* Proof Strip */}
      <ProofStrip />

      {/* Platform Stats */}
      <section className="border-y border-white/5 bg-white/2.5 py-8 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-6">
          <div className="grid gap-4 sm:grid-cols-3">
            <PlatformStatCard
              label="Total Scans"
              value={live.totalScans}
              icon={
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              }
              gradient="from-blue-500/20 to-cyan-500/20"
              textColor="text-blue-300 dark:text-blue-300"
            />
            <PlatformStatCard
              label="Active Projects"
              value={live.totalProjects}
              icon={
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                  />
                </svg>
              }
              gradient="from-purple-500/20 to-pink-500/20"
              textColor="text-purple-400"
            />
            <PlatformStatCard
              label="Vulnerabilities Found"
              value={live.totalVulnerabilities}
              icon={
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
              }
              gradient="from-red-500/20 to-orange-500/20"
              textColor="text-red-400"
            />
          </div>
        </div>
      </section>

      <GradientSeparator />

      {/* Security Control Room (Modules) */}
      <ModulesBento />

      <GradientSeparator />

      {/* Who It's For */}
      <WhoItsFor />

      <GradientSeparator />

      {/* 60 Seconds */}
      <QuickStart60s />

      <GradientSeparator />

      {/* Trust & Safety */}
      <TrustSafety />

      <GradientSeparator />

      {/* Final CTA */}
      <FinalCTA />

      <GradientSeparator />

      {/* FAQ */}
      <FAQ />
    </main>
  );
}

