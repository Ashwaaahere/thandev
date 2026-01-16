"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Newspaper, Scan, Zap } from "lucide-react";
import { Container, GlassCard, DeviceFrame, AnimatedInView } from "./primitives";

export default function ModulesBento() {
  const [activeTab, setActiveTab] = useState<"feed" | "scanner">("feed");

  const modules = {
    feed: {
      title: "Threat Feed",
      icon: Newspaper,
      description:
        "CVE, KEV, vendor advisories and PoCs streaming in real time. Filter by product, severity and exploit activity.",
      bullets: [
        "Real-time security intelligence",
        "CVE and KEV tracking",
        "Vendor advisories & PoCs",
      ],
      image: "/securitynews.png",
      gradient: "from-cyan-500/20 to-blue-500/20",
    },
    scanner: {
      title: "Surface Scanner",
      icon: Scan,
      description:
        "Continuous security scanning for shipping teams. Catch vulnerabilities before release with professional-grade scanning tools.",
      bullets: [
        "Professional-grade scanning",
        "Continuous monitoring",
        "Actionable vulnerability reports",
      ],
      image: "/scan.png",
      gradient: "from-indigo-500/20 to-purple-500/20",
    },
  };

  const activeModule = modules[activeTab];
  const Icon = activeModule.icon;

  return (
    <section id="features" className="py-16 md:py-24">
      <Container>
        <AnimatedInView className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Security Control Room
          </h2>
          <p className="mt-3 text-lg text-slate-300">
            Two powerful modules working together to keep your infrastructure
            secure.
          </p>
        </AnimatedInView>

        {/* Tab switcher */}
        <div className="mb-8 flex flex-wrap justify-center gap-2">
          {(["feed", "scanner"] as const).map((tab) => {
            const module = modules[tab];
            const TabIcon = module.icon;
            return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`group relative flex items-center gap-2 rounded-xl border px-4 py-2.5 text-xs font-semibold transition-all sm:px-6 sm:py-3 sm:text-sm ${
                  activeTab === tab
                    ? "border-white/20 bg-white/10 text-white"
                    : "border-white/10 bg-white/5 text-slate-400 hover:border-white/15 hover:bg-white/8"
                }`}
              >
                <TabIcon className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                <span className="whitespace-nowrap">{module.title}</span>
                {activeTab === tab && (
                  <motion.div
                    layoutId="activeTab"
                    className="absolute inset-0 rounded-xl border border-cyan-400/30 bg-cyan-400/10"
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Content area with crossfade */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <GlassCard hover className="p-8 md:p-12">
              <div className="grid grid-cols-1 gap-8 md:grid-cols-2 md:items-center">
                {/* Left: Content */}
                <div>
                  <div className="mb-4 flex items-center gap-3">
                    <div
                      className={`flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${activeModule.gradient} border border-white/10`}
                    >
                      <Icon className="h-6 w-6 text-cyan-400" />
                    </div>
                    <h3 className="text-2xl font-semibold md:text-3xl">
                      {activeModule.title}
                    </h3>
                  </div>

                  <p className="mb-6 text-slate-300">
                    {activeModule.description}
                  </p>

                  <ul className="space-y-3">
                    {activeModule.bullets.map((bullet, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="flex items-start gap-3"
                      >
                        <Zap className="mt-0.5 h-4 w-4 shrink-0 text-cyan-400" />
                        <span className="text-slate-300">{bullet}</span>
                      </motion.li>
                    ))}
                  </ul>
                </div>

                {/* Right: Image */}
                <div className="relative">
                  <motion.div
                    whileHover={{ scale: 1.02 }}
                    transition={{ type: "spring", stiffness: 300 }}
                  >
                    <DeviceFrame
                      image={activeModule.image}
                      alt={activeModule.title}
                      className="group"
                    />
                  </motion.div>

                  {/* Spotlight glow */}
                  <div
                    className={`pointer-events-none absolute -inset-8 -z-10 rounded-3xl bg-gradient-to-br ${activeModule.gradient} blur-2xl opacity-50`}
                  />
                </div>
              </div>
            </GlassCard>
          </motion.div>
        </AnimatePresence>
      </Container>
    </section>
  );
}
