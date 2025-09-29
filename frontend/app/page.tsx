"use client";

import React, {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type MouseEventHandler,
} from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  motion,
  useScroll,
  useTransform,
  useSpring,
  type Variants,
} from "framer-motion";

const BreakingNews = dynamic(() => import("@/components/BreakingNews"), {
  ssr: false,
});
import HeroAurora from "@/components/Exploits/HeroAurora";
import AnimatedCard from "@/components/AnimatedCard";


/* ------------------------------------------------------------------ */
/* Easing + variants                                                   */
/* ------------------------------------------------------------------ */

const OUT = [0.16, 1, 0.3, 1] as const;
const makeItemVariants = (from: "left" | "right"): Variants => ({
  hidden: {
    opacity: 0,
    y: 18,
    x: from === "left" ? -40 : 40,
    scale: 0.98,
    filter: "blur(2px)",
  },
  show: {
    opacity: 1,
    y: 0,
    x: 0,
    scale: 1,
    filter: "blur(0px)",
    transition: { duration: 0.7, ease: OUT },
  },
});

/* ------------------------------------------------------------------ */
/* Safe anchor (no SSR breakage, no errors if ID missing)              */
/* ------------------------------------------------------------------ */

function AnchorLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: ReactNode;
}) {
  const onClick: MouseEventHandler<HTMLAnchorElement> = (e) => {
    if (!href?.startsWith("#") || typeof document === "undefined") return;
    const id = href.slice(1);
    let el: HTMLElement | null = null;
    try {
      el = document.getElementById(id);
    } catch {
      el = null;
    }
    if (el?.scrollIntoView) {
      e.preventDefault();
      try {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch {}
      if (typeof window !== "undefined" && window.history?.replaceState) {
        try {
          window.history.replaceState(null, "", href);
        } catch {}
      }
    }
  };
  return (
    <a href={href} onClick={onClick} className={className}>
      {children}
    </a>
  );
}

function CursorGlow() {
  const dotRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const dot = dotRef.current;
    const host = document.getElementById('product');
    if (!dot || !host) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const onMove = (e: PointerEvent) => {
      const r = host.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      dot.style.transform = `translate(${x}px, ${y}px)`;
      dot.style.opacity = '0.65';
    };
    const onLeave = () => { dot.style.opacity = '0'; };
    host.addEventListener('pointermove', onMove, { passive: true });
    host.addEventListener('pointerleave', onLeave, { passive: true });
    return () => {
      host.removeEventListener('pointermove', onMove as any);
      host.removeEventListener('pointerleave', onLeave as any);
    };
  }, []);

  return (
    <div aria-hidden>
      <div
        ref={dotRef}
        className="cursor-glow"
        style={{ transform: 'translate(-9999px,-9999px)', opacity: 0 }}
      />
    </div>
  );
}

function HeroSparkles() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext('2d'); if (!ctx) return;
    let w = c.width = c.offsetWidth; let h = c.height = c.offsetHeight;
    const onResize = () => { w = c.width = c.offsetWidth; h = c.height = c.offsetHeight; };
    window.addEventListener('resize', onResize, { passive: true });

    const N = 60;
    const stars = Array.from({ length: N }).map(() => ({
      x: Math.random() * w,
      y: Math.random() * h,
      r: Math.random() * 1.4 + 0.3,
      t: Math.random() * Math.PI * 2,
      s: 0.6 + Math.random() * 0.6,
    }));

    let raf = 0;
    const loop = () => {
      ctx.clearRect(0, 0, w, h);
      for (const s of stars) {
        s.t += 0.02 * s.s;
        const a = (Math.sin(s.t) * 0.5 + 0.5) * 0.8 + 0.2;
        ctx.globalAlpha = a;
        ctx.fillStyle = 'rgba(125,211,252,1)';
        ctx.beginPath(); ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); };
  }, []);

  return <canvas ref={ref} className="absolute right-0 top-0 h-[60%] w-[60%] opacity-45 mix-blend-screen" />;
}

function Diagnostics() {
  useEffect(() => {
    const required = ["product", "features", "developers", "how", "faq", "signup", "demo"];
    const missing = required.filter((id) => !document.getElementById(id));
    const holder = document.getElementById("dev-tests");
    if (holder) holder.setAttribute("data-tests", JSON.stringify({ missing }));
    // eslint-disable-next-line no-console
    console.debug("[Thandev Diagnostics]", { missing });
  }, []);
  return <div id="dev-tests" data-tests="{}" className="hidden" />;
}

/* ------------------------------------------------------------------ */
/* Live data fetchers                                                  */
/* ------------------------------------------------------------------ */

type LiveStats = {
  signalsToday: number | null;
  exploitsToday: number | null;
  vendorsToday: number | null;
  checksPerRun: number | null;        // reserved (soon)
  issuesPrevented: number | null;     // reserved (soon)
};

function unique<T>(arr: T[]) {
  return Array.from(new Set(arr));
}

function useLiveStats(): LiveStats {
  const [stats, setStats] = useState<LiveStats>({
    signalsToday: null,
    exploitsToday: null,
    vendorsToday: null,
    checksPerRun: null,
    issuesPrevented: null,
  });

  useEffect(() => {
    const API =
      process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "https://thandev-backend.fly.dev";

    (async () => {
      try {
        // 1) Try a dedicated stats endpoint
        let signals: number | null = null;
        let exploits: number | null = null;
        let vendors: number | null = null;
        let checks: number | null = null;
        let prevented: number | null = null;

        try {
          const s = await fetch(`${API}/stats`).then((r) => (r.ok ? r.json() : null));
          if (s) {
            signals = s?.signals_today ?? null;
            exploits = s?.exploits_today ?? null;
            vendors = s?.vendors_today ?? null;
            checks = s?.checks_per_run ?? null;
            prevented = s?.issues_prevented_7d ?? null;
          }
        } catch {}

        // 2) Fallbacks for MVP:
        //    - signalsToday from /news count (limit large enough)
        //    - exploitsToday + vendorsToday from /exploits/daily OR derive from /news items with tags
        if (signals == null || exploits == null || vendors == null) {
          // news
          let news: any[] = [];
          try {
            const n = await fetch(`${API}/news?limit=400`).then((r) =>
              r.ok ? r.json() : []
            );
            if (Array.isArray(n)) news = n;
          } catch {}

          if (signals == null) {
            signals = news.length || null;
          }

          // try dedicated exploits endpoint(s)
          let exp: any[] | null = null;
          try {
            const e = await fetch(`${API}/exploits/daily`).then((r) =>
              r.ok ? r.json() : null
            );
            if (Array.isArray(e)) exp = e;
          } catch {}
          if (exp == null) {
            try {
              const e2 = await fetch(`${API}/exploits?period=today`).then((r) =>
                r.ok ? r.json() : null
              );
              if (Array.isArray(e2)) exp = e2;
            } catch {}
          }

          // derive from exploits; fallback to news tags
          if (exp) {
            exploits = exp.length;
            const vendorsList = unique(
              exp
                .map((x) => x.vendor || x.org || x.affected_vendor)
                .filter(Boolean)
            );
            vendors = vendorsList.length || null;
          } else {
            // heuristic: news items tagged with exploit/poc
            const todayEx = news.filter((n) => {
              const tags = (n?.tags || n?.labels || []) as string[];
              const title = `${n?.title || ""}`.toLowerCase();
              return (
                tags.some((t) => /exploit|poc|kev/i.test(t)) ||
                /exploit|proof[-\s]?of[-\s]?concept|poc/.test(title)
              );
            });
            exploits = todayEx.length || null;

            const vendorsList = unique(
              todayEx
                .map((n) => (n?.vendor || n?.org || n?.source || "").toString())
                .filter(Boolean)
            );
            vendors = vendorsList.length || null;
          }
        }

        setStats({
          signalsToday: typeof signals === "number" ? signals : null,
          exploitsToday: typeof exploits === "number" ? exploits : null,
          vendorsToday: typeof vendors === "number" ? vendors : null,
          checksPerRun: typeof checks === "number" ? checks : null, // may stay null (soon)
          issuesPrevented: typeof prevented === "number" ? prevented : null, // may stay null (soon)
        });
      } catch {
        // keep nulls
      }
    })();
  }, []);

  return stats;
}

/* ------------------------------------------------------------------ */
/* Count-up utility                                                    */
/* ------------------------------------------------------------------ */

function useCountUp(active: boolean, to: number, duration = 1000) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!active || !ref.current) return;
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 4);
      const n = Math.round(to * eased);
      if (ref.current) ref.current.textContent = n.toLocaleString();
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, to, duration]);
  return ref;
}

/* ------------------------------------------------------------------ */
/* HERO FX — kinetic grid + constellation canvas + spark lines         */
/* ------------------------------------------------------------------ */

function HeroKinetic() {
  // light sweep lines
  const rows = new Array(9).fill(0).map((_, i) => i);
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      {rows.map((r) => (
        <motion.div
          key={r}
          initial={{ x: "-60%" }}
          animate={{ x: ["-60%", "60%"] }}
          transition={{
            duration: 10 + r * 0.5,
            ease: "linear",
            repeat: Infinity,
            repeatType: "reverse",
          }}
          className="pointer-events-none absolute left-0 right-0 h-px"
          style={{
            top: `${8 + r * 10}%`,
            background:
              "linear-gradient(90deg, rgba(255,255,255,0), rgba(125,211,252,.42), rgba(255,255,255,0))",
          }}
        />
      ))}
    </div>
  );
}

function Constellation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;

    let w = (c.width = c.offsetWidth);
    let h = (c.height = c.offsetHeight);

    const onResize = () => {
      w = c.width = c.offsetWidth;
      h = c.height = c.offsetHeight;
    };
    window.addEventListener("resize", onResize, { passive: true });

    const particles = Array.from({ length: 70 }).map(() => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
    }));
    let mx = w / 2,
      my = h / 3;

    const onMove = (e: MouseEvent) => {
      const rect = c.getBoundingClientRect();
      mx = e.clientX - rect.left;
      my = e.clientY - rect.top;
    };
    c.addEventListener("mousemove", onMove);

    let raf = 0;
    const loop = () => {
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = "rgba(125,211,252,0.9)"; // cyan-300 dot
      const linkDist = 110;

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        // repulsion from mouse
        const dx = p.x - mx;
        const dy = p.y - my;
        const d = Math.hypot(dx, dy);
        if (d < 120) {
          p.vx += (dx / d) * 0.02;
          p.vy += (dy / d) * 0.02;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.1, 0, Math.PI * 2);
        ctx.fill();
      }

      // links
      ctx.strokeStyle = "rgba(125,211,252,0.15)";
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const a = particles[i];
          const b = particles[j];
          const dist = Math.hypot(a.x - b.x, a.y - b.y);
          if (dist < linkDist) {
            ctx.globalAlpha = 1 - dist / linkDist;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
            ctx.globalAlpha = 1;
          }
        }
      }

      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      c.removeEventListener("mousemove", onMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 z-0 opacity-80"
      style={{ mixBlendMode: "screen" }}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Metric helpers                                                      */
/* ------------------------------------------------------------------ */

function Metric({
  value,
  label,
  active,
}: {
  value: number | null;
  label: string;
  active: boolean;
}) {
  const ref = useCountUp(active && value != null, value ?? 0, 900);
  if (value == null) {
    return (
      <div className="mt-4 flex items-baseline gap-3">
        <span className="text-3xl font-semibold tabular-nums">—</span>
        <span className="text-sm muted">{label}</span>
      </div>
    );
  }
  return (
    <div className="mt-4 flex items-baseline gap-3">
      <span ref={ref} className="text-3xl font-semibold tabular-nums">
        0
      </span>
      <span className="text-sm muted">{label}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Scroll-scrubbed cards (Control room)                                */
/* ------------------------------------------------------------------ */

function ScrollScrubCard({
  index,
  title,
  body,
  value,
  label,
  from,
  accentClass,
  soon,
}: {
  index: number;
  title: string;
  body: string;
  value: number | null;
  label: string;
  from: "left" | "right";
  accentClass: string;
  soon?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 80%", "end 20%"],
  });

  const x = useTransform(scrollYProgress, [0, 1], [from === "left" ? -60 : 60, 0]);
  const y = useTransform(scrollYProgress, [0, 1], [26, 0]);
  const o = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const s = useTransform(scrollYProgress, [0, 1], [0.98, 1]);
  const glow = useTransform(scrollYProgress, [0, 1], [0, 0.35]);

  const activeT = useTransform(scrollYProgress, (v) => v > 0.55);
  const [isActive, setIsActive] = useState(false);
  useEffect(() => {
    const unsub = activeT.on("change", (v) => setIsActive(!!v));
    return () => unsub();
  }, [activeT]);

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach(
          (e) =>
            e.isIntersecting && (e.target.classList.add("play"), io.unobserve(e.target))
        ),
      { threshold: 0.45 }
    );
    const el = ref.current;
    if (el) io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <motion.div
      ref={ref}
      style={{ x, y, opacity: o, scale: s }}
      className="relative overflow-hidden rounded-2xl border card-border p-6 md:p-8 bg-white/5 reveal-sheen"
    >
      <motion.div
        style={{ opacity: glow }}
        className={`pointer-events-none absolute -inset-16 blur-3xl ${accentClass}`}
      />
      <div className="flex flex-col gap-6 md:flex-row md:items-center">
        <div className="order-2 md:order-1 md:w-[42%]">
          <div className="relative overflow-hidden rounded-xl border card-border bg-[var(--surface)]/60 p-4 shadow-soft">
            <div className="flex items-center gap-1.5 opacity-70">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <div className="h-16 rounded-lg bg-white/50 dark:bg-white/10" />
              <div className="h-16 rounded-lg bg-white/50 dark:bg-white/10" />
              <div className="h-16 rounded-lg bg-white/50 dark:bg-white/10" />
              <div className="col-span-3 h-20 rounded-lg bg-white/60 dark:bg-white/10" />
            </div>
          </div>
        </div>

        <div className="order-1 md:order-2 md:flex-1">
          <div className="text-sm muted">{`0${index + 1}`}</div>
          <h3 className="mt-1 text-2xl font-semibold flex items-center gap-3">
            <span className="dot" /> {title}
            {soon && <span className="pill-soon">Soon</span>}
          </h3>
          <p className="mt-2 text-sm muted">{body}</p>

          {!soon && <Metric value={value} label={label} active={isActive} />}
          {soon && (
            <div className="mt-4 text-xs muted">
              Metrics will appear on release.
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Tilted scrub tiles (Workflow)                                       */
/* ------------------------------------------------------------------ */

function TiltScrub({
  title,
  body,
  accentClass,
  from,
}: {
  title: string;
  body: string;
  accentClass: string;
  from: "left" | "right";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 85%", "end 35%"],
  });

  const x = useTransform(scrollYProgress, [0, 1], [from === "left" ? -40 : 40, 0]);
  const r = useTransform(scrollYProgress, [0, 1], [from === "left" ? -2 : 2, 0]);
  const o = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const s = useTransform(scrollYProgress, [0, 1], [0.98, 1]);

  return (
    <motion.div
      ref={ref}
      style={{ x, rotate: r, opacity: o, scale: s }}
      className="relative overflow-hidden rounded-2xl border card-border p-6 md:p-8 bg-white/5"
    >
      <motion.div className={`absolute -inset-20 blur-3xl ${accentClass}`} style={{ opacity: 0.25 }} />
      <h3 className="text-2xl font-semibold flex items-center gap-2">
        <span className="dot" /> {title}
      </h3>
      <p className="mt-2 text-sm muted">{body}</p>

      <div className="mt-5 h-px w-full bg-gradient-to-r from-transparent via-[var(--hairline)] to-transparent" />
      <div className="mt-4 grid grid-cols-3 gap-2">
        <div className="h-10 rounded-lg bg-white/50 dark:bg-white/10" />
        <div className="h-10 rounded-lg bg-white/50 dark:bg-white/10" />
        <div className="h-10 rounded-lg bg-white/50 dark:bg-white/10" />
      </div>
    </motion.div>
  );
}

/* ------------------------------------------------------------------ */
/* Vertical progress (used by How)                                     */
/* ------------------------------------------------------------------ */

function VerticalProgress({ progress, side }: { progress: any; side: "left" | "right" }) {
  const leftPos = side === "right" ? "calc(66.666% - 1px)" : "calc(33.333% - 1px)";
  const pathLength = useTransform(progress, [0, 1], [0, 1]);
  return (
    <svg
      className="hidden md:block absolute top-0 h-full w-[2px]"
      style={{ left: leftPos as any }}
      viewBox="0 0 2 100"
      preserveAspectRatio="none"
      aria-hidden
    >
      <defs>
        <linearGradient id="hiwGrad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--brand)" stopOpacity="0.0" />
          <stop offset="35%" stopColor="var(--brand)" stopOpacity="0.55" />
          <stop offset="100%" stopColor="var(--brand)" stopOpacity="0.1" />
        </linearGradient>
      </defs>
      <motion.path
        d="M1 0 L1 100"
        stroke="url(#hiwGrad)"
        strokeWidth="2"
        strokeLinecap="round"
        style={{ pathLength }}
      />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* How it works — flipped: cards LEFT, rail RIGHT; steps marked Soon   */
/* ------------------------------------------------------------------ */

function StepScrub({
  idx,
  from,
  title,
  body,
  accentClass,
  soon,
}: {
  idx: number;
  from: "left" | "right";
  title: string;
  body: string;
  accentClass: string;
  soon?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 85%", "end 35%"],
  });

  const x = useTransform(scrollYProgress, [0, 1], [from === "left" ? -60 : 60, 0]);
  const y = useTransform(scrollYProgress, [0, 1], [28, 0]);
  const o = useTransform(scrollYProgress, [0, 1], [0, 1]);
  const s = useTransform(scrollYProgress, [0, 1], [0.97, 1]);
  const glow = useTransform(scrollYProgress, [0, 1], [0, 0.35]);

  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach(
          (e) =>
            e.isIntersecting && (e.target.classList.add("play"), io.unobserve(e.target))
        ),
      { threshold: 0.5 }
    );
    if (ref.current) io.observe(ref.current);
    return () => io.disconnect();
  }, []);

  return (
    <motion.div
      ref={ref}
      style={{ x, y, opacity: o, scale: s }}
      className="relative overflow-hidden rounded-2xl border card-border bg-white/5 p-6 md:p-7 reveal-sheen"
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 180, damping: 18, mass: 0.5 }}
    >
      <motion.div className={`absolute -inset-16 blur-3xl ${accentClass}`} style={{ opacity: glow }} />
      <div className="flex items-start gap-5">
        <div className="mt-1 shrink-0 rounded-full border card-border px-3 py-1 text-xs font-semibold">{`0${
          idx + 1
        }`}</div>

        <div className="flex-1">
          <h3 className="text-xl font-semibold flex items-center gap-3">
            <span className="dot" /> {title}
            {soon && <span className="pill-soon">Soon</span>}
          </h3>
          <p className="mt-2 text-sm muted">{body}</p>

          <motion.div
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: false, amount: 0.6 }}
            transition={{ duration: 0.6, ease: OUT }}
            className="mt-5 h-[2px] origin-left rounded bg-gradient-to-r from-[var(--brand)]/0 via-[var(--brand)]/60 to-[var(--brand)]/0"
          />
        </div>
      </div>
    </motion.div>
  );
}

function HowListFlipped() {
  const rootRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: rootRef,
    offset: ["start 75%", "end 25%"],
  });

  const steps = [
    {
      title: "Create your workspace",
      body:
        "Start with a clean project space. Invite teammates, set roles, choose data residency. No CLI required.",
      from: "left" as const,
      accent: "bg-cyan-400/20",
      soon: true, // unrelated to feed — mark as coming soon in MVP UI
    },
    {
      title: "Connect sources",
      body:
        "Hook up GitHub/CI and domains to watch. We index metadata only by default, and you control what’s ingested.",
      from: "right" as const,
      accent: "bg-indigo-400/20",
      soon: true,
    },
    {
      title: "Automate triage",
      body:
        "Define rules: tag by product, severity, exploit activity (KEV/PoC), and assign owners so the queue stays clean.",
      from: "left" as const,
      accent: "bg-emerald-400/20",
      soon: true,
    },
  ];

  return (
    <div ref={rootRef} className="relative">
      <VerticalProgress progress={scrollYProgress} side="right" />
      <div className="space-y-12 md:pr-10">
        {steps.map((s, i) => (
          <StepScrub
            key={s.title}
            idx={i}
            from={s.from}
            title={s.title}
            body={s.body}
            accentClass={s.accent}
            soon={s.soon}
          />
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function ThandevLanding() {
  // sheen trigger
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("play");
            obs.unobserve(e.target);
          }
        }),
      { threshold: 0.45 }
    );
    document.querySelectorAll(".reveal-sheen").forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  const live = useLiveStats();

  return (
    <main className="min-h-screen scroll-smooth">
      <Diagnostics />

      {/* HERO */}
      <section id="product" className="relative overflow-hidden">
        <div className="absolute inset-0 z-0">
          <HeroAurora />
          <CursorGlow />
          <HeroSparkles />
        </div>

        <div className="relative z-10 mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 px-6 py-20 md:grid-cols-2 md:py-28">
          <motion.div
            initial={{ y: 8, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: .6, ease: [0.16,1,0.3,1] }}
            whileHover={{ y: -2 }}
          >
            <h1 className="text-4xl md:text-6xl font-semibold tracking-tight title-future">
              See cyberspace in real time.<br />
              <span className="title-future-underline">Scan early. Ship safe.</span>
            </h1>
            <TypeLine />
            <div className="mt-6 flex flex-wrap gap-3">
              <a href="#signup" className="btn-brand btn-neon">Start free</a>
              <a href="#features" className="btn-ghost btn-ghost-neon">Explore</a>
            </div>
          </motion.div>

          <motion.div
            className="hero-surface p-5 shadow-deep"
            initial={{ y: 16, opacity: 0, scale: .98 }}
            whileInView={{ y: 0, opacity: 1, scale: 1 }}
            viewport={{ once: true, amount: .4 }}
            transition={{ duration: .6, ease: [0.16,1,0.3,1] }}
            whileHover={{ y: -4 }}
          >
            {/* floating micro-orbs */}
            <div aria-hidden className="pointer-events-none absolute -left-6 -top-6 h-16 w-16 rounded-full bg-cyan-400/25 blur-2xl" />
            <div aria-hidden className="pointer-events-none absolute -right-8 top-10 h-24 w-24 rounded-full bg-indigo-400/20 blur-3xl" />
            <AnimatedCard className="hero-surface p-5 shadow-deep">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Quick Start</h3>
                <div className="hidden sm:flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-rose-400/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                </div>
              </div>

              <div className="mt-3 h-px w-full bg-gradient-to-r from-transparent via-[var(--hairline)] to-transparent" />

              <figure className="mt-4 overflow-hidden rounded-2xl border card-border shadow-soft">
                <div className="flex items-center justify-between px-3 py-2 backdrop-blur-md bg-white/45 dark:bg-slate-900/30">
                  <div className="text-xs font-mono text-[var(--muted)]">Thandev • guide</div>
                </div>
                <pre className="font-code text-[13px] leading-[1.6] px-4 py-4 sm:px-6 sm:py-5 backdrop-blur-md dark:text-slate-100 dark:bg-slate-900/35">{`# Browse live news feed
${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/news

# MVP: daily exploit feed is live
${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/exploits/daily  (or /exploits?period=today)`}</pre>
              </figure>

              <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-[var(--muted)]">
                <span className="badge-live">
                  <span className="live-dot" /> Live
                </span>
                <span className="rounded-full px-2.5 py-1 bg-indigo-400/10 text-indigo-700 dark:text-indigo-300 border border-indigo-400/20">LLM soon</span>
              </div>
            </AnimatedCard>
          </motion.div>
        </div>

        <div className="section-sep mx-auto mt-6 w-[90%]" />
      </section>

      {/* BREAKING NEWS */}
      <section id="breaking" className="mx-auto max-w-7xl px-6 py-10">
        <BreakingNews />
      </section>

      {/* MVP Stat strip — shows real counts */}
      <section className="mx-auto max-w-7xl px-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile label="Signals today" value={live.signalsToday} />
          <StatTile label="New exploits today" value={live.exploitsToday} />
          <StatTile label="Vendors touched" value={live.vendorsToday} />
        </div>
      </section>

      {/* CONTROL ROOM */}
      <section id="features" className="band py-16 md:py-24">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 px-6 md:grid-cols-12">
          {/* Left rail */}
          <div className="md:col-span-4">
            <div className="md:sticky md:top-24">
              <h2 className="text-3xl font-semibold tracking-tight">Your security control room</h2>
              <p className="mt-3 text-[var(--muted)]">
                Scroll to explore the core modules. Live numbers are real. Features marked “Soon” are in flight.
              </p>
              <motion.div
                className="mt-6 h-[3px] w-full origin-left rounded-full bg-[var(--brand)]/55"
                initial={{ scaleX: 0 }}
                whileInView={{ scaleX: 1 }}
                viewport={{ margin: "-120px 0px -40% 0px", once: false, amount: 0.1 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
              />
            </div>
          </div>

          {/* Right column (cards) */}
          <div className="md:col-span-8 space-y-16">
            {[
              {
                k: "feed",
                title: "Live Cyber News Feed",
                body:
                  "CVE, KEV, vendor advisories and PoCs streaming in real time. Filter by product, severity and exploit activity.",
                value: live.signalsToday,
                label: "Signals today",
                from: "left" as const,
                accent: "bg-cyan-400/20",
                soon: false,
              },
              {
                k: "scans",
                title: "Instant Site & App Scans",
                body:
                  "Kick off Nuclei/ZAP from the dashboard with no CLI. Correlate findings with exploit intel.",
                value: null,
                label: "Checks/run",
                from: "right" as const,
                accent: "bg-indigo-400/20",
                soon: true, // mark as upcoming
              },
              {
                k: "shift",
                title: "Scan During Development (Shift-Left)",
                body:
                  "Scan local builds and preview deployments in the browser to catch issues before release.",
                value: null,
                label: "Issues prevented (7d)",
                from: "left" as const,
                accent: "bg-emerald-400/20",
                soon: true, // mark as upcoming
              },
            ].map((item, i) => (
              <ScrollScrubCard
                key={item.k}
                index={i}
                title={item.title}
                body={item.body}
                value={item.value}
                label={item.label}
                from={item.from}
                accentClass={item.accent}
                soon={item.soon}
              />
            ))}
          </div>
        </div>
      </section>

      <div className="section-sep mx-auto w-[92%]" />

      {/* AUTOMATION & LIFECYCLE */}
      <section id="automation" className="band py-16 md:py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-semibold tracking-tight mb-4">
              Security Automation for Everyone
            </h2>
            <p className="text-lg text-[var(--muted)] max-w-3xl mx-auto">
              While big companies have dedicated security teams, startups, freelancers, and students can't afford enterprise solutions. 
              Thandev brings industry-level security automation to everyone.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-12">
            {/* Current Phase */}
            <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
              <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
              <div className="relative z-10">
                <div className="mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center mb-3">
                    <span className="text-xl">🛡️</span>
                  </div>
                  <h3 className="text-xl font-semibold mb-2">Manual Security Testing</h3>
                  <p className="text-[var(--muted)] text-sm">
                    Start with our surface scan tool. Perfect for testing individual websites and applications.
                  </p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                    <span>Available Now</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <div className="w-2 h-2 rounded-full bg-gray-400" />
                    <span>Free tier: 1 scan per device</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Next Phase */}
            <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
              <div className="relative z-10">
                <div className="mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center mb-3">
                    <span className="text-xl">⚡</span>
                  </div>
                  <h3 className="text-xl font-semibold mb-2">Automated CI/CD Integration</h3>
                  <p className="text-[var(--muted)] text-sm">
                    Integrate security scans into your development workflow. Catch vulnerabilities before they reach production.
                  </p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                    <span>Coming Soon</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <div className="w-2 h-2 rounded-full bg-gray-400" />
                    <span>GitHub Actions integration</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Future Phase */}
            <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-transparent" />
              <div className="relative z-10">
                <div className="mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 flex items-center justify-center mb-3">
                    <span className="text-xl">🚀</span>
                  </div>
                  <h3 className="text-xl font-semibold mb-2">Full Lifecycle Automation</h3>
                  <p className="text-[var(--muted)] text-sm">
                    Automatic security scanning on every commit with intelligent code analysis. Seamless CI/CD integration.
                  </p>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-purple-600 dark:text-purple-400">
                    <div className="w-2 h-2 rounded-full bg-purple-500" />
                    <span>Future Vision</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <div className="w-2 h-2 rounded-full bg-gray-400" />
                    <span>Industry-level standards</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* GitHub Integration Preview */}
          <div className="relative overflow-hidden rounded-3xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-8">
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5" />
            <div className="relative z-10">
              <div className="text-center mb-8">
                <h3 className="text-2xl font-semibold mb-3">The Future: GitHub-Native Security</h3>
                <p className="text-[var(--muted)] max-w-2xl mx-auto">
                  Imagine pushing code to GitHub and automatically getting security feedback. 
                  No complex setup, no expensive tools - just secure development by default.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div className="space-y-4">
                  <h4 className="font-semibold text-lg">How It Works</h4>
                  <div className="space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-indigo-500 text-white text-xs flex items-center justify-center font-semibold">1</div>
                      <div>
                        <p className="font-medium">Push to GitHub</p>
                        <p className="text-sm text-[var(--muted)]">Commit your code as usual</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-indigo-500 text-white text-xs flex items-center justify-center font-semibold">2</div>
                      <div>
                        <p className="font-medium">Automatic Scan Trigger</p>
                        <p className="text-sm text-[var(--muted)]">Thandev detects the push and starts scanning</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-indigo-500 text-white text-xs flex items-center justify-center font-semibold">3</div>
                      <div>
                        <p className="font-medium">Code Analysis</p>
                        <p className="text-sm text-[var(--muted)]">Analyzes your code for security flaws and vulnerabilities</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-3">
                      <div className="w-6 h-6 rounded-full bg-indigo-500 text-white text-xs flex items-center justify-center font-semibold">4</div>
                      <div>
                        <p className="font-medium">Instant Feedback</p>
                        <p className="text-sm text-[var(--muted)]">Get detailed reports and fix suggestions</p>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <h4 className="font-semibold text-lg">Benefits</h4>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <span className="text-sm">No expensive security teams needed</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <span className="text-sm">Catch issues before they reach production</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <span className="text-sm">Industry-level security standards</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <span className="text-sm">Perfect for startups and students</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500" />
                      <span className="text-sm">Zero configuration required</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-8 text-center">
                <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 rounded-full text-indigo-600 dark:text-indigo-400 text-sm">
                  <div className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse" />
                  <span>Building the future of accessible security</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="section-sep mx-auto w-[92%]" />

      {/* WORKFLOW */}
      <section id="developers" className="band-alt py-16 md:py-24">
        <div className="mx-auto max-w-7xl px-6">
          <div className="mb-8">
            <h2 className="text-3xl font-semibold tracking-tight">Workflow you already use</h2>
            <p className="mt-2 text-[var(--muted)]">Integrates with GitHub, Slack and CI/CD. Prioritize what matters and keep shipping.</p>
          </div>

          <div className="grid gap-10 md:grid-cols-2">
            {[
              {
                title: "Actionable insights",
                body: "Every finding is mapped to CVE/KEV/EPSS context so you know exactly what to fix first.",
                accent: "bg-emerald-400/25",
                from: "left" as const,
              },
              {
                title: "Seamless workflow",
                body: "Create issues, route alerts, and resolve without leaving your flow — GitHub, Slack and CI/CD.",
                accent: "bg-indigo-400/25",
                from: "right" as const,
              },
            ].map((c) => (
              <TiltScrub key={c.title} title={c.title} body={c.body} accentClass={c.accent} from={c.from} />
            ))}
          </div>
        </div>
      </section>

      <div className="section-sep mx-auto w-[92%]" />

      {/* HOW IT WORKS — flipped: cards LEFT, sticky rail RIGHT; non-feed = Soon */}
      <section id="how" className="relative py-16 md:py-24">
        <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 px-6 md:grid-cols-12">
          {/* LEFT: steps list */}
          <div className="relative md:col-span-8">
            <div className="relative">
              <HowListFlipped />
            </div>
          </div>

          {/* RIGHT: sticky rail */}
          <div className="md:col-span-4">
            <div className="md:sticky md:top-24">
              <h2 className="text-3xl font-semibold tracking-tight">How it works</h2>
              <p className="mt-2 text-[var(--muted)]">
                A clean setup path that scales with your team — items marked <span className="pill-soon">Soon</span> will roll out after MVP.
              </p>

              <div className="mt-5 space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan-400" />
                  <span className="muted">Workspace (Soon)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-indigo-400" />
                  <span className="muted">Connections (Soon)</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  <span className="muted">Automation (Soon)</span>
                </div>
              </div>

              <div className="mt-6 h-[3px] w-full origin-left rounded-full bg-[var(--brand)]/35" />
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-5xl px-6 py-16 md:py-24">
        <h2 className="text-2xl md:text-3xl font-semibold tracking-tight">FAQ</h2>
        <div className="mt-6 space-y-4">
          {[
            {
              q: "What’s live in the MVP?",
              a: "The live news feed and daily exploit feed with real counters. Scans and dev-time checks are coming soon.",
            },
            {
              q: "How are exploit counts calculated?",
              a: "We try a dedicated /exploits endpoint. If missing, we derive from today’s news tagged exploit/PoC.",
            },
            {
              q: "Do you fake numbers?",
              a: "No. If a metric isn’t live yet, we show a dash and mark the card as “Soon.”",
            },
          ].map((f, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.2 }}
              transition={{ duration: 0.6, delay: i * 0.05 }}
              className="card p-5 transition-colors shadow-sm"
            >
              <div className="font-medium">{f.q}</div>
              <div className="mt-1 text-sm muted">{f.a}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* SIGNUP — updated CTA text */}
      {/* <section id="signup" className="mx-auto max-w-3xl px-6 pb-20">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center">
          <h3 className="text-xl font-semibold">
            Ready to stream the feed and daily exploits?
          </h3>
          <p className="mt-2 text-sm text-slate-300">
            Start free to browse real-time security news and new exploits every day.
            Site scans and dev-time checks are rolling out next.
          </p>
          <div className="mt-4 flex justify-center gap-3">
            <a href="/signup" className="rounded-xl bg-white px-4 py-2 font-semibold text-slate-900 hover:bg-slate-200">
              Create account
            </a>
            <a href="#exploit-feed" className="rounded-xl border border-white/10 px-4 py-2 font-semibold hover:bg-white/5">
              View exploit feed
            </a>
          </div>
        </div>
      </section> */}
    </main>
  );
}

/* ------------------------------------------------------------------ */
/* Small presentational bits                                           */
/* ------------------------------------------------------------------ */

function StatTile({ label, value }: { label: string; value: number | null }) {
  const ref = useCountUp(value != null, value ?? 0, 700);
  return (
    <div className="rounded-xl border card-border bg-white/40 dark:bg-white/5 p-4 shadow-soft flex items-center justify-between">
      <div className="text-sm muted">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value == null ? "—" : <span ref={ref}>0</span>}</div>
    </div>
  );
}

/* Minimal typewriter subtitle */
function TypeLine() {
  const [text, setText] = useState('');
  const first = 'Thandev is a developer-first security space: live feed, instant scans, and dev-time checks.';
  const second = 'Live intel, faster triage, safer releases — built for developers.';
  const lines = [first, second];
  const [idx, setIdx] = useState(0);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    let timer: any;
    const current = lines[idx];
    const typeSpeed = 14;
    const deleteSpeed = 10;
    const pause = 900;
    const backspaceDelay = 1200; // extra delay before backspace starts

    const run = () => {
      if (!isDeleting) {
        if (text.length < current.length) {
          setText(current.slice(0, text.length + 1));
          timer = setTimeout(run, typeSpeed);
        } else {
          timer = setTimeout(() => setIsDeleting(true), backspaceDelay);
        }
      } else {
        if (text.length > 0) {
          setText(current.slice(0, text.length - 1));
          timer = setTimeout(run, deleteSpeed);
        } else {
          setIsDeleting(false);
          setIdx((idx + 1) % lines.length);
        }
      }
    };

    timer = setTimeout(run, isDeleting ? deleteSpeed : typeSpeed);
    return () => clearTimeout(timer);
  }, [text, isDeleting, idx]);

  return (
    <p className="mt-4 max-w-xl text-[var(--muted)]">
      {text}
    </p>
  );
}
