"use client";

import { motion, useInView } from "framer-motion";
import { useRef, type ReactNode } from "react";

/* ------------------------------------------------------------------ */
/* Section Container                                                  */
/* ------------------------------------------------------------------ */

export function Section({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`relative ${className}`}>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Container                                                          */
/* ------------------------------------------------------------------ */

export function Container({
  children,
  className = "",
  size = "xl",
}: {
  children: ReactNode;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl" | "full";
}) {
  const maxWidths = {
    sm: "max-w-3xl",
    md: "max-w-5xl",
    lg: "max-w-6xl",
    xl: "max-w-7xl",
    full: "max-w-full",
  };

  return (
    <div className={`mx-auto px-6 ${maxWidths[size]} ${className}`}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Glass Card                                                         */
/* ------------------------------------------------------------------ */

export function GlassCard({
  children,
  className = "",
  hover = false,
}: {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}) {
  return (
    <motion.div
      className={`relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl ${className}`}
      whileHover={hover ? { y: -4, scale: 1.01 } : undefined}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Device Frame                                                       */
/* ------------------------------------------------------------------ */

export function DeviceFrame({
  children,
  className = "",
  image,
  alt,
}: {
  children?: ReactNode;
  className?: string;
  image?: string;
  alt?: string;
}) {
  return (
    <div
      className={`relative rounded-xl border border-white/10 bg-slate-900/50 p-2 shadow-2xl ${className}`}
    >
      {/* Device chrome */}
      <div className="mb-2 flex items-center gap-1.5 px-2">
        <div className="h-2 w-2 rounded-full bg-red-500/60" />
        <div className="h-2 w-2 rounded-full bg-amber-500/60" />
        <div className="h-2 w-2 rounded-full bg-emerald-500/60" />
      </div>

      {/* Content area */}
      <div className="relative overflow-hidden rounded-lg bg-slate-800/40">
        {image ? (
          <div className="relative aspect-video w-full">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={image}
              alt={alt || "Screenshot"}
              className="h-full w-full object-contain"
            />
            {/* Subtle glow overlay */}
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-900/20 to-transparent" />
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Animated In View                                                   */
/* ------------------------------------------------------------------ */

export function AnimatedInView({
  children,
  className = "",
  delay = 0,
  direction = "up",
  once = true,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
  direction?: "up" | "down" | "left" | "right" | "fade";
  once?: boolean;
}) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once, margin: "-100px" });

  const variants = {
    up: { y: 40, opacity: 0 },
    down: { y: -40, opacity: 0 },
    left: { x: -40, opacity: 0 },
    right: { x: 40, opacity: 0 },
    fade: { opacity: 0 },
  };

  const final = {
    y: 0,
    x: 0,
    opacity: 1,
  };

  return (
    <motion.div
      ref={ref}
      initial={variants[direction]}
      animate={isInView ? final : variants[direction]}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Gradient Separator                                                 */
/* ------------------------------------------------------------------ */

export function GradientSeparator({ className = "" }: { className?: string }) {
  return (
    <div
      className={`mx-auto h-px w-[90%] bg-gradient-to-r from-transparent via-white/10 to-transparent ${className}`}
    />
  );
}
