'use client';

import React, { useState, useRef, useEffect } from 'react';
import { Terminal, Shield, Zap, CheckCircle2, AlertTriangle, Code, ChevronRight } from 'lucide-react';

interface HistoryItem {
  command: string;
  output: React.ReactNode;
}

export default function CyberTerminal() {
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<HistoryItem[]>([
    {
      command: 'sysinfo --verbose',
      output: (
        <div className="text-cyan-300 space-y-1 my-1">
          <p>--------------------------------------------------</p>
          <p className="font-bold text-cyan-400">OPERATIVE PROFILE: ASHWATHAMAN SATISH KUMAR</p>
          <p>ROLE: Cybersecurity Engineer / Application Security Specialist</p>
          <p>STATUS: SECURITY+ CERTIFIED (EXP: SEP 2027)</p>
          <p>CLEARANCE: TOP SECRET / LEVEL 5</p>
          <p>LOCATION: Binghamton, NY, USA | +1 (607) 309-7597</p>
          <p>--------------------------------------------------</p>
          <p className="text-emerald-400 font-mono text-xs">Type <span className="underline font-bold text-cyan-200">help</span> to view available security commands.</p>
        </div>
      ),
    },
  ]);

  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history]);

  const handleCommand = (e: React.FormEvent) => {
    e.preventDefault();
    const cmd = input.trim().toLowerCase();
    if (!cmd) return;

    let output: React.ReactNode = null;

    switch (cmd) {
      case 'help':
        output = (
          <div className="text-slate-300 space-y-1 font-mono text-xs md:text-sm my-1 bg-cyan-950/20 p-2.5 rounded border border-cyan-800/40">
            <p className="text-cyan-400 font-semibold mb-1">AVAILABLE TERMINAL COMMANDS:</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">summary</span> - Display professional summary & education</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">skills</span> - List SecEng, AppSec, SAST/DAST & toolchain</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">exp</span> - View professional security internships & leadership</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">projects</span> - Inspect Thandev Platform & MITM Honeypot project</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">certs</span> - Display active Security+ verification</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">contact</span> - Retrieve contact & social endpoints</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">scan</span> - Execute automated vulnerability assessment demo</p>
            <p><span className="text-emerald-400 font-bold w-24 inline-block">clear</span> - Clear terminal buffer</p>
          </div>
        );
        break;

      case 'summary':
        output = (
          <div className="text-slate-300 space-y-2 text-xs md:text-sm font-mono my-2 border-l-2 border-cyan-500 pl-3">
            <p className="text-cyan-300 font-semibold">SUMMARY OVERVIEW:</p>
            <p>
              Security+ certified cybersecurity professional completing an M.S. in Computer Science (Dec 2026) at Binghamton University (GPA: 3.23).
              Proven expertise in application security assessments, access-control validation, and network operations.
              Architected <span className="text-emerald-400 font-semibold">Thandev</span>, integrating 10+ security scanning tools into automated assessment pipelines. Tested 4 campus enterprise applications prior to operational use.
            </p>
          </div>
        );
        break;

      case 'skills':
        output = (
          <div className="text-slate-300 space-y-2 font-mono text-xs md:text-sm my-2">
            <p className="text-cyan-400 font-bold">TECHNICAL SKILL SPECS:</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
              <div className="bg-slate-900/80 p-2 rounded border border-slate-700">
                <span className="text-emerald-400 font-semibold">Security Engineering:</span> AppSec, SAST/DAST, Vulnerability Management, IAM, RBAC, OAuth, Session Security.
              </div>
              <div className="bg-slate-900/80 p-2 rounded border border-slate-700">
                <span className="text-cyan-400 font-semibold">Tools & Scanners:</span> Burp Suite, OWASP ZAP, Nuclei, Nmap, Metasploit, Semgrep, GitLeaks, Trivy, Wireshark, Scapy, tcpdump.
              </div>
              <div className="bg-slate-900/80 p-2 rounded border border-slate-700">
                <span className="text-indigo-400 font-semibold">Languages & Dev:</span> Python, Bash, SQL, JavaScript/TypeScript, FastAPI, Flask, Next.js, REST APIs, Git.
              </div>
              <div className="bg-slate-900/80 p-2 rounded border border-slate-700">
                <span className="text-purple-400 font-semibold">AI & Infra:</span> OpenAI API, Qdrant (Vector DB), RAG, Linux, Windows, Docker, PostgreSQL, Redis.
              </div>
            </div>
          </div>
        );
        break;

      case 'exp':
        output = (
          <div className="text-slate-300 space-y-3 font-mono text-xs md:text-sm my-2">
            <div>
              <p className="text-cyan-400 font-bold">1. IT Intern — Compass Group USA / Chartwells (Aug 2026 – Present)</p>
              <p className="text-slate-400">Diagnose network connectivity, POS & scanner security, isolate faults, patch management and endpoint alert reviews.</p>
            </div>
            <div>
              <p className="text-cyan-400 font-bold">2. IT Security Intern — Sodexo Dining Services (Aug 2025 – May 2026)</p>
              <p className="text-slate-400">Conducted authorized penetration testing on 4 campus applications. Tested authentication, authorization, RBAC, session management, and OWASP Top 10 risks.</p>
            </div>
            <div>
              <p className="text-cyan-400 font-bold">3. Founder & Security Lead — Condottiere (Aug 2022 – Jun 2024)</p>
              <p className="text-slate-400">Conducted SAST and DAST for medical-sector client applications, prioritizing remediation and developer security reviews.</p>
            </div>
          </div>
        );
        break;

      case 'projects':
        output = (
          <div className="text-slate-300 space-y-3 font-mono text-xs md:text-sm my-2">
            <div className="border border-cyan-500/30 p-2.5 rounded bg-cyan-950/20">
              <span className="text-emerald-400 font-bold">[PROJECT 1] Thandev — Security Intelligence Platform</span>
              <p className="text-slate-300 mt-1">Unified security checks through 10+ tools across 3 scan tiers (web, network, secrets, dependencies, SAST). Implemented GitHub OAuth, RBAC, Redis Streams async background execution (up to 3 hrs scan runtime), and OpenAI + Qdrant contextual remediation guidance.</p>
            </div>
            <div className="border border-purple-500/30 p-2.5 rounded bg-purple-950/20">
              <span className="text-purple-300 font-bold">[PROJECT 2] MITM Attack Simulation, Honeypot & Web Defense</span>
              <p className="text-slate-300 mt-1">Controlled interception-proxy lab using Python, Flask & Scapy. Implemented rate-limiting (10 req/60s), CSRF validation, signed sessions, and fake credential responses for attacker trapping.</p>
            </div>
          </div>
        );
        break;

      case 'certs':
        output = (
          <div className="text-emerald-400 font-mono text-xs md:text-sm my-2 p-3 bg-emerald-950/20 border border-emerald-500/40 rounded flex items-center gap-3">
            <Shield className="w-8 h-8 text-emerald-400 flex-shrink-0" />
            <div>
              <p className="font-bold text-base text-emerald-300">CompTIA Security+ Certified</p>
              <p className="text-slate-300">Credential Status: Active | Valid through September 2027</p>
              <p className="text-xs text-slate-400">Verification ID: SY0-601/701 Verified Cyber Security Practitioner</p>
            </div>
          </div>
        );
        break;

      case 'contact':
        output = (
          <div className="text-slate-300 font-mono text-xs md:text-sm space-y-1 my-2 bg-slate-900/90 p-3 rounded border border-cyan-500/30">
            <p><span className="text-cyan-400 font-bold">Email:</span> aswathama0604@gmail.com</p>
            <p><span className="text-cyan-400 font-bold">Phone:</span> +1 (607) 309-7597</p>
            <p><span className="text-cyan-400 font-bold">Location:</span> Binghamton, NY, USA</p>
            <p><span className="text-cyan-400 font-bold">LinkedIn:</span> linkedin.com/in/ashwathaman-satish-kumar</p>
            <p><span className="text-cyan-400 font-bold">GitHub:</span> github.com/ashwathaman-sk</p>
            <p><span className="text-cyan-400 font-bold">Platform:</span> thandev.io</p>
          </div>
        );
        break;

      case 'scan':
        output = (
          <div className="text-xs font-mono space-y-1 my-2 bg-black/90 p-3 rounded border border-emerald-500/50">
            <p className="text-emerald-400 animate-pulse">[INITIATING MOCK SAST/DAST SECURITY SCAN...]</p>
            <p className="text-slate-400">[1/4] Checking headers & TLS configuration... <span className="text-emerald-400 font-bold">PASS (TLS 1.3, HSTS Enabled)</span></p>
            <p className="text-slate-400">[2/4] Executing Semgrep SAST on application source... <span className="text-emerald-400 font-bold">0 HIGH, 0 CRITICAL</span></p>
            <p className="text-slate-400">[3/4] Running Nuclei DAST templates against target endpoints... <span className="text-emerald-400 font-bold">SECURE</span></p>
            <p className="text-slate-400">[4/4] Verifying RBAC & JWT secret key integrity... <span className="text-emerald-400 font-bold">256-BIT HMAC VALID</span></p>
            <p className="text-cyan-300 font-bold mt-2">RESULT: SECURITY POSTURE VERIFIED - ZERO HIGH/CRITICAL VULNERABILITIES DETECTED.</p>
          </div>
        );
        break;

      case 'clear':
        setHistory([]);
        setInput('');
        return;

      default:
        output = (
          <p className="text-red-400 font-mono text-xs md:text-sm my-1">
            Command not recognized: &apos;{cmd}&apos;. Type <span className="text-cyan-300 font-bold underline">help</span> for available commands.
          </p>
        );
    }

    setHistory((prev) => [...prev, { command: input, output }]);
    setInput('');
  };

  return (
    <div className="w-full rounded-xl overflow-hidden border border-cyan-500/30 bg-slate-950/90 shadow-2xl backdrop-blur-md font-mono text-sm">
      {/* Terminal Titlebar */}
      <div className="bg-slate-900 px-4 py-2.5 border-b border-cyan-500/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-red-500/80 inline-block"></span>
            <span className="w-3 h-3 rounded-full bg-yellow-500/80 inline-block"></span>
            <span className="w-3 h-3 rounded-full bg-green-500/80 inline-block"></span>
          </div>
          <span className="text-xs text-cyan-400/80 font-semibold ml-2 flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5" /> sec-console@ashwathaman-satish-kumar:~
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          <span className="text-emerald-400 font-semibold">LIVE HUD ACTIVE</span>
        </div>
      </div>

      {/* Terminal Content Box */}
      <div className="p-4 max-h-96 overflow-y-auto space-y-3 font-mono scrollbar-thin scrollbar-thumb-cyan-700">
        {history.map((item, idx) => (
          <div key={idx} className="space-y-1">
            <div className="flex items-center gap-2 text-cyan-400">
              <ChevronRight className="w-4 h-4 text-emerald-400" />
              <span className="text-emerald-400 font-bold">ashwathaman@secops:~$</span>
              <span className="text-slate-100 font-medium">{item.command}</span>
            </div>
            <div>{item.output}</div>
          </div>
        ))}

        {/* Command Form */}
        <form onSubmit={handleCommand} className="flex items-center gap-2 pt-1">
          <ChevronRight className="w-4 h-4 text-emerald-400 animate-pulse" />
          <span className="text-emerald-400 font-bold text-xs md:text-sm">ashwathaman@secops:~$</span>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type 'help', 'skills', 'projects', 'exp' or 'scan'..."
            className="flex-1 bg-transparent border-none outline-none text-cyan-300 font-mono text-xs md:text-sm focus:ring-0 placeholder:text-slate-600"
            autoFocus
          />
        </form>
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
