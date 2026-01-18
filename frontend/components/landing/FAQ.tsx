"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { Container, GlassCard, AnimatedInView } from "./primitives";

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const faqs = [
    {
      q: "Is this a pentest tool?",
      a: "No. Thandev is a DevSecOps scanner and threat intelligence dashboard. It helps teams find and prioritize vulnerabilities in their own applications, not test third-party systems.",
    },
    {
      q: "Can I scan any site?",
      a: "No. You can only scan targets you own or are authorized to test. Domain verification (DNS TXT) is rolling out in beta to ensure scans are scoped to verified ownership.",
    },
    {
      q: "When will domain verification launch?",
      a: "DNS TXT verification is rolling out in beta. You'll be able to verify domain ownership through the project settings as the feature becomes available.",
    },
    {
      q: "What tools power the scans?",
      a: "Thandev uses industry-standard security scanners orchestrated in a controlled runner environment. This includes tools for web application scanning, dependency analysis, and infrastructure checks.",
    },
    {
      q: "How do I get beta access?",
      a: "Request beta access through the sign-up flow. Early beta access is controlled to prevent abuse and ensure a quality experience for all users.",
    },
    {
      q: "What's included in the beta?",
      a: "Beta users get access to the live security news feed, threat intelligence dashboard, and professional vulnerability scanning tools. Domain verification is rolling out in beta, and CI/CD integration is coming soon.",
    },
  ];

  return (
    <section id="faq" className="py-16 md:py-24">
      <Container size="lg">
        <AnimatedInView className="mb-12 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Frequently Asked Questions
          </h2>
        </AnimatedInView>

        <div className="space-y-4">
          {faqs.map((faq, i) => (
            <AnimatedInView key={i} delay={i * 0.05} direction="up">
              <GlassCard
                className="overflow-hidden"
                hover={false}
              >
                <button
                  onClick={() => setOpenIndex(openIndex === i ? null : i)}
                  className="flex w-full items-center justify-between p-6 text-left"
                >
                  <span className="font-semibold text-white">
                    {faq.q}
                  </span>
                  <motion.div
                    animate={{ rotate: openIndex === i ? 180 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <ChevronDown className="h-5 w-5 text-slate-400" />
                  </motion.div>
                </button>

                <AnimatePresence>
                  {openIndex === i && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden"
                    >
                      <div className="border-t border-white/10 px-6 pb-6 pt-4 text-sm text-slate-300">
                        {faq.a}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </GlassCard>
            </AnimatedInView>
          ))}
        </div>
      </Container>
    </section>
  );
}
