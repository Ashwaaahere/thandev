"use client";

import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import { Container, GlassCard, AnimatedInView } from "./primitives";

export default function FinalCTA() {
  return (
    <section id="signup" className="py-16 md:py-24">
      <Container size="md">
        <AnimatedInView>
          <GlassCard className="relative overflow-hidden p-8 text-center md:p-12">
            {/* Background gradient */}
            <div className="pointer-events-none absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-indigo-500/20 blur-xl" />

            <div className="relative z-10">
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                whileInView={{ scale: 1, opacity: 1 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-sm backdrop-blur-sm"
              >
                <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
                <span className="text-slate-300">Join the first wave</span>
              </motion.div>

              <h2 className="mb-4 text-3xl font-semibold tracking-tight md:text-4xl">
                Ready to secure your infrastructure?
              </h2>

              <p className="mb-8 text-lg text-slate-300">
                Thandev is in early beta — join the first wave of builders.
              </p>

              <div className="flex flex-wrap justify-center gap-4">
                <Link
                  href="/auth"
                  className="group relative overflow-hidden rounded-xl bg-gradient-to-r from-cyan-500 to-blue-500 px-8 py-4 text-base font-semibold text-white shadow-lg shadow-cyan-500/25 transition-all hover:scale-105 hover:shadow-xl hover:shadow-cyan-500/30"
                >
                  <span className="relative z-10 flex items-center gap-2">
                    Request Beta Access
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </span>
                </Link>

                <Link
                  href="/news"
                  className="group rounded-xl border border-white/20 bg-white/5 px-8 py-4 text-base font-semibold text-slate-200 backdrop-blur-sm transition-all hover:border-white/30 hover:bg-white/10"
                >
                  View Threat Feed
                </Link>
              </div>
            </div>
          </GlassCard>
        </AnimatedInView>
      </Container>
    </section>
  );
}
