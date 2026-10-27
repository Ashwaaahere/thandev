'use client';

import React from 'react';
import { ExternalLink, ShieldCheck, Code2, Cpu, Zap, Lock, Terminal, Layers } from 'lucide-react';

interface Project {
  title: string;
  tagline: string;
  link?: string;
  tech: string[];
  bullets: string[];
  securitySpecs: { label: string; val: string }[];
  badgeColor: string;
}

export default function ProjectsShowcase() {
  const projects: Project[] = [
    {
      title: 'Thandev — Security Intelligence Platform',
      tagline: 'Unified security assessment tool & vulnerability orchestration engine',
      link: 'https://thandev.io',
      tech: ['Python', 'FastAPI', 'Next.js', 'TypeScript', 'Redis', 'OpenAI API', 'Qdrant'],
      bullets: [
        'Unified automated security checks through 10+ open-source and proprietary security tools across 3 scan tiers (web, network, dependencies, secrets, SAST). Standardized scan results into 7 unified output fields spanning severity, location, evidence, impact, and remediation.',
        'Implemented GitHub OAuth, administrator approvals, tier-based permissions, and DNS TXT domain ownership verification to restrict unauthorized scanning, configured with 2-URL Basic and 5-URL Pro scan limits and expanded Advanced coverage.',
        'Built Redis Streams and asynchronous background workers for deep security scans lasting up to 3 hours, decoupling scan execution from API request handlers.',
        'Integrated OpenAI API and Qdrant vector retrieval (RAG) to provide contextual, code-level remediation guidance and mitigation advice for developer review.',
      ],
      securitySpecs: [
        { label: 'Tools Integrated', val: '10+ Security Tools' },
        { label: 'Scan Pipeline', val: '3 Tiers (SAST/DAST/Secret)' },
        { label: 'Async Runtime', val: 'Up to 3 Hours' },
        { label: 'Domain Auth', val: 'DNS TXT Verification' },
      ],
      badgeColor: 'border-cyan-500/30 bg-cyan-950/20 text-cyan-400',
    },
    {
      title: 'MITM Attack Simulation, Honeypot & Web Defense',
      tagline: 'Interactive attack lab, traffic manipulation proxy, and threat hardening system',
      tech: ['Python', 'Flask', 'Scapy', 'tcpdump', 'CSRF Validation', 'Rate Limiting'],
      bullets: [
        'Developed a controlled interception-proxy lab to demonstrate credential exposure and HTTP request manipulation in real-time.',
        'Combined low-level packet capture (Scapy), honeypot trap fields, proxy indicators, and fake-credential response generators with centralized security event logging.',
        'Hardened the target web application with CSRF token validation, strict input sanitization, signed session cookies, security headers (CSP, HSTS), and 10-request-per-60-second rate-limiting.',
        'Verified invalid-token rejection, malicious request blocking, and automated excessive-request banning under stress tests.',
      ],
      securitySpecs: [
        { label: 'Rate Limiting', val: '10 req / 60 sec' },
        { label: 'Packet Engine', val: 'Scapy Packet Interceptor' },
        { label: 'Defense Layer', val: 'CSRF & Signed Sessions' },
        { label: 'Threat Trap', val: 'Honeypot Fake-Creds' },
      ],
      badgeColor: 'border-purple-500/30 bg-purple-950/20 text-purple-400',
    },
  ];

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            SECURITY & SOFTWARE PROJECTS
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/40">
              PRODUCTION READY
            </span>
          </h3>
          <p className="text-xs text-slate-400 font-mono">
            Flagship security platforms, attack simulations, and automated threat intelligence tooling
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {projects.map((proj, idx) => (
          <div
            key={idx}
            className="rounded-xl border border-slate-800 bg-slate-950/90 hover:border-cyan-500/40 transition-all p-6 shadow-2xl space-y-5"
          >
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${proj.badgeColor}`}>
                    FLAGSHIP SYSTEM
                  </span>
                  {proj.link && (
                    <a
                      href={proj.link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-mono text-cyan-400 hover:text-cyan-300 flex items-center gap-1 underline"
                    >
                      {proj.link} <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
                <h4 className="text-xl font-bold text-slate-100 mt-1">{proj.title}</h4>
                <p className="text-xs text-slate-400 font-mono">{proj.tagline}</p>
              </div>

              {/* Tech Stack Pills */}
              <div className="flex flex-wrap gap-1.5 max-w-md">
                {proj.tech.map((t, tIdx) => (
                  <span
                    key={tIdx}
                    className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-900 text-slate-300 border border-slate-800"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>

            {/* Bullets */}
            <ul className="space-y-2.5 text-xs md:text-sm text-slate-300 leading-relaxed font-sans">
              {proj.bullets.map((b, bIdx) => (
                <li key={bIdx} className="flex items-start gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                  <span>{b}</span>
                </li>
              ))}
            </ul>

            {/* Spec Matrix */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
              {proj.securitySpecs.map((spec, sIdx) => (
                <div key={sIdx} className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 font-mono">
                  <p className="text-[10px] text-slate-400 uppercase">{spec.label}</p>
                  <p className="text-xs font-bold text-cyan-300 mt-0.5">{spec.val}</p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
