'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  Terminal as TerminalIcon,
  Award,
  BookOpen,
  Mail,
  Phone,
  MapPin,
  Linkedin,
  Github,
  Globe,
  Download,
  CheckCircle,
  Cpu,
  Lock,
  Zap,
  Award as CertIcon,
  Users,
  ChevronRight,
  Sparkles,
  Layers,
} from 'lucide-react';
import CyberTerminal from '@/components/portfolio/CyberTerminal';
import SecurityScanSimulator from '@/components/portfolio/SecurityScanSimulator';
import SkillsRadar from '@/components/portfolio/SkillsRadar';
import ExperienceTimeline from '@/components/portfolio/ExperienceTimeline';
import ProjectsShowcase from '@/components/portfolio/ProjectsShowcase';

export default function PortfolioClient() {
  const [activeTab, setActiveTab] = useState<'all' | 'terminal' | 'skills' | 'exp' | 'projects' | 'sim'>('all');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans relative overflow-x-hidden selection:bg-cyan-500 selection:text-slate-950">
      {/* Background Cyber Grid Effects */}
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(14,165,233,0.15),rgba(255,255,255,0))]"></div>
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: `linear-[#38bdf8] 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.3) 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      ></div>

      {/* Main Container */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-10 relative z-10">

        {/* Top HUD Banner */}
        <div className="rounded-xl border border-cyan-500/30 bg-slate-900/60 p-4 backdrop-blur-md flex flex-wrap items-center justify-between gap-4 font-mono text-xs">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-emerald-400 animate-ping"></div>
            <span className="text-cyan-400 font-bold">CLEARANCE: LEVEL 5 (TOP SECRET)</span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-300">SYSTEM ID: SEC-ASH-2026</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>STATUS: <strong className="text-emerald-400">OPERATIONAL</strong></span>
            <span>ROLE: <strong className="text-cyan-300">SECURITY ENGINEER TARGET</strong></span>
          </div>
        </div>

        {/* Hero / Header Section */}
        <div className="relative rounded-2xl border border-cyan-500/30 bg-slate-900/80 p-6 md:p-10 backdrop-blur-xl shadow-2xl overflow-hidden">
          {/* Subtle glowing orb */}
          <div className="absolute -top-24 -right-24 w-96 h-96 rounded-full bg-cyan-500/10 blur-3xl pointer-events-none"></div>

          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8 relative z-10">
            <div className="space-y-4 max-w-3xl">
              <div className="flex flex-wrap items-center gap-2">
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-500/40 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" /> COMPTIA SECURITY+ CERTIFIED
                </span>
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-500/40">
                  M.S. COMPUTER SCIENCE (DEC 2026)
                </span>
              </div>

              <h1 className="text-3xl sm:text-4xl md:text-5xl font-extrabold tracking-tight text-slate-100 font-sans">
                Ashwathaman Satish Kumar
              </h1>

              <p className="text-lg md:text-xl text-cyan-400 font-mono font-semibold">
                Cybersecurity Professional & Application Security Specialist
              </p>

              <p className="text-sm md:text-base text-slate-300 leading-relaxed font-sans">
                Security+ certified cybersecurity professional completing an M.S. in Computer Science (Dec 2026) at Binghamton University with experience in application security assessments, access-control validation, and network operations. Developed <strong className="text-cyan-300">Thandev</strong>, integrating <span className="text-emerald-400 font-bold">10+ security tools</span> into automated assessment workflows, and tested 4 campus enterprise applications before operational use. Combines Python development, remediation coordination, and client-facing technical leadership.
              </p>

              {/* Contact Endpoints */}
              <div className="flex flex-wrap items-center gap-4 pt-2 font-mono text-xs text-slate-300">
                <a
                  href="mailto:aswathama0604@gmail.com"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500/50 hover:text-cyan-300 transition-colors"
                >
                  <Mail className="w-3.5 h-3.5 text-cyan-400" /> aswathama0604@gmail.com
                </a>
                <a
                  href="tel:+16073097597"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-cyan-500/50 hover:text-cyan-300 transition-colors"
                >
                  <Phone className="w-3.5 h-3.5 text-emerald-400" /> +1 (607) 309-7597
                </a>
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-slate-400">
                  <MapPin className="w-3.5 h-3.5 text-purple-400" /> Binghamton, NY, USA
                </span>
              </div>
            </div>

            {/* Quick Action Badges & Resume CTA */}
            <div className="flex flex-col sm:flex-row lg:flex-col gap-3 w-full lg:w-auto shrink-0 font-mono text-xs">
              <a
                href="https://linkedin.com"
                target="_blank"
                rel="noreferrer"
                className="w-full px-4 py-2.5 rounded-xl bg-cyan-950/80 border border-cyan-500/40 text-cyan-300 hover:bg-cyan-900/80 transition-all font-bold flex items-center justify-center gap-2 shadow-lg shadow-cyan-950/50"
              >
                <Linkedin className="w-4 h-4" /> LINKEDIN PROFILE
              </a>
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="w-full px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-700 text-slate-200 hover:border-slate-500 transition-all font-bold flex items-center justify-center gap-2"
              >
                <Github className="w-4 h-4" /> GITHUB REPOSITORIES
              </a>
              <a
                href="https://thandev.io"
                target="_blank"
                rel="noreferrer"
                className="w-full px-4 py-2.5 rounded-xl bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 hover:bg-emerald-900/80 transition-all font-bold flex items-center justify-center gap-2"
              >
                <Globe className="w-4 h-4" /> THANDEV PLATFORM
              </a>
            </div>
          </div>
        </div>

        {/* Navigation Tabs for Interactive Sections */}
        <div className="flex flex-wrap items-center justify-center gap-2 font-mono text-xs border-b border-slate-800 pb-4">
          <button
            onClick={() => setActiveTab('all')}
            className={`px-4 py-2 rounded-lg font-bold transition-all ${
              activeTab === 'all'
                ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
            }`}
          >
            ALL SECTIONS
          </button>
          <button
            onClick={() => setActiveTab('terminal')}
            className={`px-4 py-2 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'terminal'
                ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
            }`}
          >
            <TerminalIcon className="w-3.5 h-3.5" /> CYBER TERMINAL HUD
          </button>
          <button
            onClick={() => setActiveTab('sim')}
            className={`px-4 py-2 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'sim'
                ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
            }`}
          >
            <Shield className="w-3.5 h-3.5" /> SECURITY SCAN PIPELINE
          </button>
          <button
            onClick={() => setActiveTab('skills')}
            className={`px-4 py-2 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'skills'
                ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" /> TECHNICAL SKILLS
          </button>
          <button
            onClick={() => setActiveTab('exp')}
            className={`px-4 py-2 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'exp'
                ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" /> EXPERIENCE
          </button>
          <button
            onClick={() => setActiveTab('projects')}
            className={`px-4 py-2 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
              activeTab === 'projects'
                ? 'bg-cyan-500 text-slate-950 shadow-lg shadow-cyan-500/20'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5" /> PROJECTS
          </button>
        </div>

        {/* Section 1: Interactive Terminal HUD */}
        {(activeTab === 'all' || activeTab === 'terminal') && (
          <section className="space-y-3">
            <div className="flex items-center gap-2 font-mono text-xs text-cyan-400">
              <TerminalIcon className="w-4 h-4" /> INTERACTIVE COMMAND CENTER
            </div>
            <CyberTerminal />
          </section>
        )}

        {/* Section 2: Security Scan Pipeline Simulator */}
        {(activeTab === 'all' || activeTab === 'sim') && (
          <section className="space-y-3">
            <SecurityScanSimulator />
          </section>
        )}

        {/* Section 3: Education & Certifications */}
        {(activeTab === 'all') && (
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 font-mono">
              <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                EDUCATION & CERTIFICATIONS
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/40">
                  VERIFIED
                </span>
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono">
              {/* Certification Badge Card */}
              <div className="rounded-xl border border-emerald-500/40 bg-slate-900/90 p-5 shadow-xl space-y-3 relative overflow-hidden">
                <div className="absolute top-0 right-0 translate-x-3 -translate-y-3 w-20 h-20 bg-emerald-500/10 rounded-full blur-xl"></div>
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                    <CertIcon className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-100 text-base">CompTIA Security+</h4>
                    <p className="text-xs text-emerald-400 font-semibold">Active Certification</p>
                  </div>
                </div>
                <div className="space-y-1 text-xs text-slate-300 pt-2 border-t border-slate-800">
                  <p><strong>Expires:</strong> September 2027</p>
                  <p><strong>Focus:</strong> Threats, Attacks, Vulnerabilities, Architecture, Governance & Risk Management.</p>
                </div>
              </div>

              {/* Master's Degree */}
              <div className="rounded-xl border border-cyan-500/30 bg-slate-900/90 p-5 shadow-xl space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
                    <BookOpen className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-100 text-base">M.S. Computer Science</h4>
                    <p className="text-xs text-cyan-400 font-semibold">Binghamton University (SUNY)</p>
                  </div>
                </div>
                <div className="space-y-1 text-xs text-slate-300 pt-2 border-t border-slate-800">
                  <p><strong>Timeline:</strong> Completion Dec 2026 | Binghamton, NY</p>
                  <p><strong>Track & GPA:</strong> Cybersecurity Track | GPA: 3.23</p>
                </div>
              </div>

              {/* Bachelor's Degree */}
              <div className="rounded-xl border border-indigo-500/30 bg-slate-900/90 p-5 shadow-xl space-y-3">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
                    <BookOpen className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-100 text-base">B.Tech CS & Engineering</h4>
                    <p className="text-xs text-indigo-400 font-semibold">SRM Institute of Science and Tech</p>
                  </div>
                </div>
                <div className="space-y-1 text-xs text-slate-300 pt-2 border-t border-slate-800">
                  <p><strong>Timeline:</strong> 2021 – 2025 | Chennai, India</p>
                  <p><strong>Specialization:</strong> Cybersecurity Specialization</p>
                </div>
              </div>
            </div>

            {/* Relevant Coursework */}
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/50 font-mono text-xs text-slate-300 space-y-1">
              <span className="text-cyan-400 font-bold uppercase">Relevant Graduate & Undergraduate Coursework:</span>
              <p className="text-slate-400 leading-relaxed">
                Computer Networks, Systems Programming, Design and Analysis of Algorithms, Mobile Security, Information Assurance & Security, Forensics and Incident Response, Malware Analysis, Penetration Testing and Vulnerability Assessment.
              </p>
            </div>
          </section>
        )}

        {/* Section 4: Technical Skills Matrix */}
        {(activeTab === 'all' || activeTab === 'skills') && (
          <section>
            <SkillsRadar />
          </section>
        )}

        {/* Section 5: Experience Timeline */}
        {(activeTab === 'all' || activeTab === 'exp') && (
          <section>
            <ExperienceTimeline />
          </section>
        )}

        {/* Section 6: Security & Software Projects */}
        {(activeTab === 'all' || activeTab === 'projects') && (
          <section>
            <ProjectsShowcase />
          </section>
        )}

        {/* Section 7: Leadership & Volunteering */}
        {(activeTab === 'all') && (
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 font-mono">
              <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                LEADERSHIP & VOLUNTEERING
                <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/40">
                  ORGANIZATIONAL IMPACT
                </span>
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 font-mono">
              <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 space-y-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/40">
                  Sep 2025 – Sep 2026
                </span>
                <h4 className="font-bold text-slate-100 text-sm mt-1">
                  President – Computer Science Graduate Student Org
                </h4>
                <p className="text-xs text-slate-400">Binghamton University</p>
                <p className="text-xs text-slate-300 leading-relaxed font-sans pt-2">
                  Organized technical and non-technical events with other graduate student organizations, coordinating schedules, communications, and logistics for joint academic, professional, and social programming.
                </p>
              </div>

              <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 space-y-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800/40">
                  Jan 2023 – Feb 2024
                </span>
                <h4 className="font-bold text-slate-100 text-sm mt-1">
                  Vice President – Cyber Carnival
                </h4>
                <p className="text-xs text-slate-400">SRM Ramapuram</p>
                <p className="text-xs text-slate-300 leading-relaxed font-sans pt-2">
                  Coordinated 24 technical and non-technical events over 2 days, alongside a hackathon, managing volunteer assignments, participant communications, schedules, and event logistics.
                </p>
              </div>

              <div className="p-5 rounded-xl border border-slate-800 bg-slate-900/80 space-y-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/40">
                  Aug 2023 – Jul 2024
                </span>
                <h4 className="font-bold text-slate-100 text-sm mt-1">
                  Web Development Tech Lead – GDSC
                </h4>
                <p className="text-xs text-slate-400">Google Developer Student Clubs, SRMIST</p>
                <p className="text-xs text-slate-300 leading-relaxed font-sans pt-2">
                  Led web-development initiatives and organized online webinars and campus technical events; volunteered at DevFest and attended editions across multiple locations.
                </p>
              </div>
            </div>
          </section>
        )}

        {/* Footer Contact Banner */}
        <div className="rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-950/40 via-slate-900/80 to-slate-950 p-8 text-center space-y-4 shadow-2xl font-mono">
          <ShieldCheck className="w-10 h-10 text-cyan-400 mx-auto animate-pulse" />
          <h3 className="text-2xl font-bold text-slate-100">READY TO RECRUIT A CYBERSECURITY ENGINEER?</h3>
          <p className="text-xs md:text-sm text-slate-300 max-w-2xl mx-auto font-sans">
            Open for Security Engineer, Application Security, SecOps, and Penetration Testing opportunities.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 pt-2">
            <a
              href="mailto:aswathama0604@gmail.com"
              className="px-6 py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold transition-all shadow-lg shadow-cyan-500/20 text-xs"
            >
              SEND DIRECT EMAIL
            </a>
            <a
              href="tel:+16073097597"
              className="px-6 py-3 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 font-bold transition-all text-xs"
            >
              CALL +1 (607) 309-7597
            </a>
          </div>
        </div>

      </div>
    </div>
  );
}
