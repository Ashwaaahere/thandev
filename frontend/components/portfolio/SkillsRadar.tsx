'use client';

import React from 'react';
import { Shield, Code, Server, Cpu, CheckCircle2, Terminal } from 'lucide-react';

interface Skill {
  name: string;
  level: number;
  tag: string;
}

interface SkillCategory {
  title: string;
  icon: React.ReactNode;
  color: string;
  skills: Skill[];
}

export default function SkillsRadar() {
  const categories: SkillCategory[] = [
    {
      title: 'Security Engineering & AppSec',
      icon: <Shield className="w-5 h-5 text-cyan-400" />,
      color: 'border-cyan-500/30 bg-cyan-950/10',
      skills: [
        { name: 'Application Security (SAST/DAST)', level: 95, tag: 'Core Expertise' },
        { name: 'Vulnerability Assessment & Remediation', level: 92, tag: 'Expert' },
        { name: 'Secure Software Development Lifecycle', level: 90, tag: 'AppSec' },
        { name: 'Identity & Access Management (IAM / RBAC)', level: 88, tag: 'Auth' },
        { name: 'Authentication & Session Security', level: 92, tag: 'OAuth/JWT' },
      ],
    },
    {
      title: 'Security Tools & Threat Analysis',
      icon: <Terminal className="w-5 h-5 text-emerald-400" />,
      color: 'border-emerald-500/30 bg-emerald-950/10',
      skills: [
        { name: 'Burp Suite & OWASP ZAP', level: 92, tag: 'Pentesting' },
        { name: 'Nuclei & Semgrep Rules', level: 90, tag: 'SAST/DAST' },
        { name: 'Nmap, Metasploit & Hydra', level: 85, tag: 'Network Sec' },
        { name: 'GitLeaks, Trivy & Security Audits', level: 88, tag: 'DevSecOps' },
        { name: 'Wireshark, Scapy & tcpdump', level: 86, tag: 'Packet Analysis' },
      ],
    },
    {
      title: 'Programming & Web Architecture',
      icon: <Code className="w-5 h-5 text-indigo-400" />,
      color: 'border-indigo-500/30 bg-indigo-950/10',
      skills: [
        { name: 'Python & Automation Scripting', level: 95, tag: 'Primary' },
        { name: 'FastAPI, Flask & REST APIs', level: 90, tag: 'Backend' },
        { name: 'TypeScript, React & Next.js', level: 85, tag: 'Frontend' },
        { name: 'Bash Scripting & CLI Tooling', level: 88, tag: 'Automation' },
        { name: 'SQL & Database Hardening', level: 85, tag: 'PostgreSQL' },
      ],
    },
    {
      title: 'Systems, Cloud & AI Security Integration',
      icon: <Cpu className="w-5 h-5 text-purple-400" />,
      color: 'border-purple-500/30 bg-purple-950/10',
      skills: [
        { name: 'Linux & Windows Systems Hardening', level: 90, tag: 'SysAdmin' },
        { name: 'Docker Containerization & Isolation', level: 85, tag: 'DevOps' },
        { name: 'Redis Streams & Async Workers', level: 88, tag: 'Architecture' },
        { name: 'OpenAI API & Qdrant Vector DB (RAG)', level: 86, tag: 'AI Security' },
        { name: 'DNS, TCP/IP & Network Segmentation', level: 88, tag: 'Networking' },
      ],
    },
  ];

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            CYBER SECURITY TECHNICAL MATRIX
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/40">
              VERIFIED SKILLSETS
            </span>
          </h3>
          <p className="text-xs text-slate-400 font-mono">
            Directly mapped from hands-on security engineering projects, vulnerability assessments, and tool development
          </p>
        </div>
        <div className="hidden sm:flex items-center gap-2 font-mono text-xs text-slate-400">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
          <span>MATRIX ACTIVE</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {categories.map((cat, idx) => (
          <div key={idx} className={`p-5 rounded-xl border ${cat.color} backdrop-blur-md space-y-4`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">{cat.icon}</div>
                <h4 className="font-bold text-slate-200 text-sm md:text-base">{cat.title}</h4>
              </div>
            </div>

            <div className="space-y-3 font-mono">
              {cat.skills.map((skill, sIdx) => (
                <div key={sIdx} className="space-y-1">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-300 font-medium flex items-center gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      {skill.name}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
                      {skill.tag}
                    </span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden p-0.5 border border-slate-800">
                    <div
                      className="h-full bg-gradient-to-r from-cyan-500 to-emerald-400 rounded-full"
                      style={{ width: `${skill.level}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
