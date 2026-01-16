"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import {
  LogIn,
  FolderPlus,
  CheckCircle2,
  Search,
  ArrowRight,
} from "lucide-react";
import { Container, AnimatedInView } from "./primitives";

export default function QuickStart60s() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start 70%", "end 30%"],
  });

  const progress = useTransform(scrollYProgress, [0, 1], [0, 100]);
  const progressWidth = useTransform(progress, (v) => `${Math.max(0, Math.min(100, v))}%`);

  const colorClasses = {
    cyan: {
      badge: "bg-gradient-to-br from-cyan-500/20 to-cyan-600/20 border-cyan-500/30 text-cyan-400",
      icon: "bg-gradient-to-br from-cyan-500/20 to-cyan-600/20 border-cyan-500/30 text-cyan-400",
    },
    blue: {
      badge: "bg-gradient-to-br from-blue-500/20 to-blue-600/20 border-blue-500/30 text-blue-400",
      icon: "bg-gradient-to-br from-blue-500/20 to-blue-600/20 border-blue-500/30 text-blue-400",
    },
    indigo: {
      badge: "bg-gradient-to-br from-indigo-500/20 to-indigo-600/20 border-indigo-500/30 text-indigo-400",
      icon: "bg-gradient-to-br from-indigo-500/20 to-indigo-600/20 border-indigo-500/30 text-indigo-400",
    },
    purple: {
      badge: "bg-gradient-to-br from-purple-500/20 to-purple-600/20 border-purple-500/30 text-purple-400",
      icon: "bg-gradient-to-br from-purple-500/20 to-purple-600/20 border-purple-500/30 text-purple-400",
    },
  };

  const steps = [
    {
      number: "1",
      title: "Join beta / Sign in",
      description:
        "Request early beta access or sign in with GitHub to get started.",
      icon: LogIn,
      color: "cyan" as keyof typeof colorClasses,
    },
    {
      number: "2",
      title: "Create a project",
      description: "Add your web application or service to start monitoring.",
      icon: FolderPlus,
      color: "blue" as keyof typeof colorClasses,
    },
    {
      number: "3",
      title: "Verify domain",
      description:
        "Verify ownership with DNS TXT record — rolling out in beta.",
      icon: CheckCircle2,
      color: "indigo" as keyof typeof colorClasses,
    },
    {
      number: "4",
      title: "Run scan + review",
      description:
        "Launch a scan and review prioritized findings with actionable context.",
      icon: Search,
      color: "purple" as keyof typeof colorClasses,
    },
  ];

  return (
    <section id="quickstart" className="py-16 md:py-24">
      <Container>
        <AnimatedInView className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            What you get in 60 seconds
          </h2>
          <p className="mt-3 text-lg text-slate-300">
            Get started with Thandev in four simple steps.
          </p>
        </AnimatedInView>

        <div ref={containerRef} className="relative">
          {/* Desktop: Horizontal stepper */}
          <div className="hidden md:block">
            {/* Progress line */}
            <div className="absolute left-0 top-12 h-1 w-full rounded-full bg-slate-800/50">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500"
                style={{ width: progressWidth }}
              />
            </div>

            <div className="relative grid grid-cols-4 gap-6">
              {steps.map((step, i) => {
                const Icon = step.icon;
                const isActive = scrollYProgress.get() > i * 0.25;
                return (
                  <AnimatedInView
                    key={i}
                    delay={i * 0.1}
                    direction="up"
                    className="relative"
                  >
                    <div className="relative rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
                      {/* Step number badge */}
                      <div className="mb-4 flex items-center justify-between">
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-full border text-lg font-bold ${colorClasses[step.color].badge}`}
                        >
                          {step.number}
                        </div>
                        {i < steps.length - 1 && (
                          <ArrowRight className="h-5 w-5 text-slate-600" />
                        )}
                      </div>

                      {/* Icon */}
                      <div
                        className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl border ${colorClasses[step.color].icon}`}
                      >
                        <Icon className="h-6 w-6" />
                      </div>

                      <h3 className="mb-2 text-lg font-semibold">
                        {step.title}
                      </h3>
                      <p className="text-sm text-slate-300">{step.description}</p>
                    </div>
                  </AnimatedInView>
                );
              })}
            </div>
          </div>

          {/* Mobile: Stacked cards */}
          <div className="space-y-4 md:hidden">
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <AnimatedInView
                  key={i}
                  delay={i * 0.1}
                  direction="left"
                  className="relative"
                >
                  <div className="flex items-start gap-4 rounded-2xl border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
                    {/* Step number badge */}
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full border text-lg font-bold ${colorClasses[step.color].badge}`}
                    >
                      {step.number}
                    </div>

                    <div className="flex-1">
                      {/* Icon */}
                      <div
                        className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl border ${colorClasses[step.color].icon}`}
                      >
                        <Icon className="h-5 w-5" />
                      </div>

                      <h3 className="mb-2 text-lg font-semibold">
                        {step.title}
                      </h3>
                      <p className="text-sm text-slate-300">{step.description}</p>
                    </div>
                  </div>
                </AnimatedInView>
              );
            })}
          </div>
        </div>
      </Container>
    </section>
  );
}
