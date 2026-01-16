"use client";

import { Shield, Lock, FileCheck } from "lucide-react";
import { Container, AnimatedInView } from "./primitives";

export default function ProofStrip() {
  const items = [
    {
      icon: Shield,
      label: "Controlled Beta",
      description: "Access is managed",
    },
    {
      icon: Lock,
      label: "Authorized Scanning",
      description: "Only your domains",
    },
    {
      icon: FileCheck,
      label: "Actionable Reports",
      description: "Prioritized findings",
    },
  ];

  return (
    <section className="border-y border-white/5 bg-white/2.5 py-8 backdrop-blur-sm">
      <Container>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          {items.map((item, i) => {
            const Icon = item.icon;
            return (
              <AnimatedInView
                key={i}
                delay={i * 0.1}
                direction="fade"
                className="flex items-center gap-4"
              >
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm">
                  <Icon className="h-5 w-5 text-cyan-400" />
                </div>
                <div>
                  <div className="font-semibold text-slate-200">{item.label}</div>
                  <div className="text-sm text-slate-400">{item.description}</div>
                </div>
              </AnimatedInView>
            );
          })}
        </div>
      </Container>
    </section>
  );
}
