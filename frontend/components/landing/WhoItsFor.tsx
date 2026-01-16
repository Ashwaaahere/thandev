"use client";

import { Rocket, Laptop, GraduationCap, Shield } from "lucide-react";
import { motion } from "framer-motion";
import { Container, GlassCard, AnimatedInView } from "./primitives";

export default function WhoItsFor() {
  const audiences = [
    {
      title: "Startups shipping fast",
      description:
        "Get enterprise-grade security without the enterprise price tag. Catch vulnerabilities before they become incidents.",
      icon: Rocket,
      gradient: "from-blue-500/20 to-cyan-500/20",
      size: "md" as const,
    },
    {
      title: "Indie developers",
      description:
        "Professional security scanning without the complexity. Focus on building while Thandev handles the security checks.",
      icon: Laptop,
      gradient: "from-purple-500/20 to-pink-500/20",
      size: "md" as const,
    },
    {
      title: "Security learners",
      description:
        "Learn security best practices with real-world scanning tools. See how vulnerabilities are detected and prioritized.",
      icon: GraduationCap,
      gradient: "from-emerald-500/20 to-teal-500/20",
      size: "lg" as const,
    },
    {
      title: "Small security teams",
      description:
        "Scale your security operations without scaling your team. Automated scanning and threat intelligence in one place.",
      icon: Shield,
      gradient: "from-orange-500/20 to-red-500/20",
      size: "md" as const,
    },
  ];

  // Bento grid layout: 2x2 with one large card
  const gridClasses = {
    md: "md:col-span-1",
    lg: "md:col-span-2",
  };

  return (
    <section id="who" className="py-16 md:py-24">
      <Container>
        <AnimatedInView className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Who it's for
          </h2>
          <p className="mt-3 text-lg text-slate-300">
            Built for teams that ship fast and need security that scales with
            them.
          </p>
        </AnimatedInView>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {audiences.map((audience, i) => {
            const Icon = audience.icon;
            return (
              <AnimatedInView
                key={i}
                delay={i * 0.1}
                direction="up"
                className={gridClasses[audience.size]}
              >
                <GlassCard hover className="group relative h-full p-6 md:p-8">
                  {/* Gradient glow on hover */}
                  <div
                    className={`absolute -inset-0.5 rounded-2xl bg-gradient-to-br ${audience.gradient} opacity-0 blur transition-opacity duration-300 group-hover:opacity-30`}
                  />

                  <div className="relative z-10">
                    <motion.div
                      whileHover={{ rotate: 2, scale: 1.05 }}
                      transition={{ type: "spring", stiffness: 300 }}
                      className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${audience.gradient} border border-white/10`}
                    >
                      <Icon className="h-6 w-6 text-cyan-400" />
                    </motion.div>

                    <h3 className="mb-2 text-xl font-semibold md:text-2xl">
                      {audience.title}
                    </h3>
                    <p className="text-sm text-slate-300 md:text-base">
                      {audience.description}
                    </p>
                  </div>
                </GlassCard>
              </AnimatedInView>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
