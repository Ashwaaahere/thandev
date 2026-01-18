"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import HeroAurora from "@/components/Exploits/HeroAurora";
import { Container } from "./primitives";

export default function Hero() {
  return (
    <section id="product" className="relative min-h-[90vh] overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 z-0">
        <HeroAurora />
      </div>

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 z-0 opacity-30"
        style={{
          backgroundImage: `
            linear-gradient(rgba(125, 211, 252, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(125, 211, 252, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: "50px 50px",
        }}
      />

      {/* Content */}
      <Container className="relative z-10 flex min-h-[90vh] items-center py-12 md:py-20">
        <div className="grid w-full grid-cols-1 gap-12 md:grid-cols-2 md:items-center">
          {/* Left: Text content */}
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm backdrop-blur-sm"
            >
              <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
              <span className="text-slate-300">Early Beta Access</span>
            </motion.div>

            <h1 className="text-4xl font-semibold tracking-tight md:text-6xl lg:text-7xl">
              Real-time cybersecurity intelligence.
              <br />
              <span className="bg-gradient-to-r from-cyan-400 via-blue-400 to-indigo-400 bg-clip-text text-transparent">
                Scan early. Ship safe.
              </span>
            </h1>

            <p className="mt-6 text-lg text-slate-300 md:text-xl">
              Thandev is a security control room that combines real-time threat
              context and continuous scanning — so teams prioritize what's
              exploitable and fix what matters.
            </p>

            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                href="/auth"
                className="group relative overflow-hidden rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-cyan-500/25 transition-all hover:scale-105 hover:shadow-xl hover:shadow-cyan-500/30"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Request Beta Access
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </span>
              </Link>

              <Link
                href="/news"
                className="group rounded-xl border border-white/20 bg-white/5 px-6 py-3.5 text-base font-semibold text-white backdrop-blur-sm transition-all hover:border-white/30 hover:bg-white/10"
              >
                View Threat Feed
              </Link>
            </div>

            <p className="mt-4 text-sm text-slate-400">
              Early beta users invited. Access is controlled to prevent abuse.
            </p>
          </motion.div>

          {/* Right: Dashboard preview */}
          <motion.div
            initial={{ y: 20, opacity: 0, scale: 0.98 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            transition={{ delay: 0.3, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            className="relative"
          >
            <div className="relative rounded-2xl border border-white/10 bg-slate-800/40 p-4 shadow-2xl backdrop-blur-xl">
              {/* Device chrome */}
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div className="h-2.5 w-2.5 rounded-full bg-red-500/60" />
                  <div className="h-2.5 w-2.5 rounded-full bg-amber-500/60" />
                  <div className="h-2.5 w-2.5 rounded-full bg-emerald-500/60" />
                </div>
                <div className="text-[10px] font-mono tracking-wider text-slate-400/80">
                  SESSION: US-EAST-1 // SECURE_NODE_01
                </div>
              </div>

              {/* Metrics grid */}
              <div className="mb-3 grid grid-cols-3 gap-2">
                <div className="rounded-lg border border-slate-700/30 bg-slate-700/30 p-2.5 backdrop-blur-sm">
                  <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-400/70">
                    SCAN HEALTH
                  </div>
                  <div className="text-xl font-bold leading-tight text-green-400/90">
                    99.8%
                  </div>
                </div>
                <div className="rounded-lg border border-slate-700/30 bg-slate-700/30 p-2.5 backdrop-blur-sm">
                  <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-400/70">
                    ALERTS
                  </div>
                  <div className="text-xl font-bold leading-tight text-white">04</div>
                </div>
                <div className="rounded-lg border border-slate-700/30 bg-slate-700/30 p-2.5 backdrop-blur-sm">
                  <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-400/70">
                    NODES
                  </div>
                  <div className="text-xl font-bold leading-tight text-purple-400/90">
                    Active
                  </div>
                </div>
              </div>

              {/* Vulnerability list */}
              <div className="space-y-1.5">
                {[
                  {
                    name: "SQL Injection",
                    severity: "CRITICAL",
                    dotClass: "bg-red-500/15 border-red-500/20",
                    dotInnerClass: "bg-red-400",
                    badgeClass: "bg-red-500/90",
                  },
                  {
                    name: "Reflected XSS",
                    severity: "HIGH",
                    dotClass: "bg-orange-500/15 border-orange-500/20",
                    dotInnerClass: "bg-orange-400",
                    badgeClass: "bg-orange-500/90",
                  },
                  {
                    name: "Weak SSL/TLS Config",
                    severity: "MEDIUM",
                    dotClass: "bg-yellow-500/15 border-yellow-500/20",
                    dotInnerClass: "bg-yellow-400",
                    badgeClass: "bg-yellow-500/90",
                  },
                  {
                    name: "Exposed Directory",
                    severity: "MEDIUM",
                    dotClass: "bg-yellow-500/15 border-yellow-500/20",
                    dotInnerClass: "bg-yellow-400",
                    badgeClass: "bg-yellow-500/90",
                  },
                  {
                    name: "Missing Security Headers",
                    severity: "LOW",
                    dotClass: "bg-blue-500/15 border-blue-500/20",
                    dotInnerClass: "bg-blue-400",
                    badgeClass: "bg-blue-500/90",
                  },
                ].map((item, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg border border-slate-700/25 bg-slate-800/30 p-2.5 backdrop-blur-sm"
                  >
                    <div className="flex items-center gap-2.5">
                      <div
                        className={`flex h-5 w-5 items-center justify-center rounded-full border ${item.dotClass}`}
                      >
                        <div
                          className={`h-2 w-2 rounded-full ${item.dotInnerClass}`}
                        />
                      </div>
                      <span className="text-sm font-medium text-white/90">
                        {item.name}
                      </span>
                    </div>
                    <span
                      className={`rounded-md ${item.badgeClass} px-2 py-0.5 text-[10px] font-semibold text-white tracking-wide`}
                    >
                      {item.severity}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Glow effect */}
            <div className="pointer-events-none absolute -inset-4 -z-10 rounded-3xl bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-indigo-500/20 blur-2xl" />
          </motion.div>
        </div>
      </Container>
    </section>
  );
}
