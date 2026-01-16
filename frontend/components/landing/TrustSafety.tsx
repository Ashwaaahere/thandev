"use client";

import { Shield, Lock, CheckCircle2 } from "lucide-react";
import { Container, GlassCard, AnimatedInView } from "./primitives";

export default function TrustSafety() {
  const trustItems = [
    {
      icon: Shield,
      title: "Controlled beta access",
      description:
        "Early beta users invited. Access is controlled to prevent abuse.",
      gradient: "from-blue-500/20 to-cyan-500/20",
    },
    {
      icon: Lock,
      title: "Authorized scanning only",
      description:
        "Only scan targets you own or are authorized to test. Domain verification via DNS TXT is part of the beta rollout.",
      gradient: "from-indigo-500/20 to-purple-500/20",
    },
    {
      icon: CheckCircle2,
      title: "Domain verification",
      description:
        "Verify ownership with DNS TXT records. Rolling out in beta to ensure scans are scoped to verified ownership.",
      gradient: "from-emerald-500/20 to-teal-500/20",
    },
  ];

  return (
    <section id="trust" className="py-16 md:py-24">
      <Container size="lg">
        <AnimatedInView className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Trust & Safety
          </h2>
          <p className="mt-3 text-lg text-slate-300">
            Security and responsibility are built into every feature.
          </p>
        </AnimatedInView>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {trustItems.map((item, i) => {
            const Icon = item.icon;
            return (
              <AnimatedInView
                key={i}
                delay={i * 0.1}
                direction="up"
              >
                <GlassCard hover className="h-full p-6 text-center">
                  <div
                    className={`mb-4 inline-flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br ${item.gradient} border border-white/10`}
                  >
                    <Icon className="h-7 w-7 text-cyan-400" />
                  </div>

                  <h3 className="mb-2 text-lg font-semibold">{item.title}</h3>
                  <p className="text-sm text-slate-300">{item.description}</p>
                </GlassCard>
              </AnimatedInView>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
