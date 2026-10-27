'use client';

import React, { useState } from 'react';
import { ShieldAlert, Play, RefreshCw, CheckCircle, AlertTriangle, ShieldCheck, Cpu, Terminal, Lock } from 'lucide-react';

interface LogMessage {
  id: number;
  type: 'info' | 'success' | 'warning' | 'error';
  text: string;
  timestamp: string;
}

export default function SecurityScanSimulator() {
  const [isScanning, setIsScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeTab, setActiveTab] = useState<'all' | 'high' | 'med'>('all');
  const [logs, setLogs] = useState<LogMessage[]>([
    { id: 1, type: 'info', text: '[SYSTEM] Initializing Security Assessment Suite v2.4...', timestamp: '10:00:01' },
    { id: 2, type: 'info', text: '[TARGET] Target application: https://thandev.io (Production Build)', timestamp: '10:00:02' },
    { id: 3, type: 'success', text: '[AUTH] OAuth2 & JWT HMAC Signature: VERIFIED SECURE', timestamp: '10:00:03' },
    { id: 4, type: 'success', text: '[SAST] Semgrep scan completed: 0 High / 0 Critical Findings', timestamp: '10:00:04' },
  ]);

  const runSimulation = () => {
    setIsScanning(true);
    setProgress(5);
    setLogs([
      { id: 1, type: 'info', text: '[SCAN RUNNER] Launching multi-tier security pipeline...', timestamp: new Date().toLocaleTimeString() },
    ]);

    const steps = [
      { p: 25, type: 'info', text: '[DAST / NMAP] Crawling application endpoints & validating HTTP headers (HSTS, CSP, X-Frame-Options)...' },
      { p: 45, type: 'success', text: '[SEMGREP / SAST] Analyzing Python FastAPI & Next.js client components for injection flaws...' },
      { p: 70, type: 'info', text: '[NUCLEI DAST] Executing automated vulnerability templates for SSRF, SQLi, and CORS misconfigurations...' },
      { p: 90, type: 'success', text: '[RBAC AUDIT] Auditing role-based permissions, signed sessions, and rate-limiting (10 req/60s)...' },
      { p: 100, type: 'success', text: '[PIPELINE COMPLETE] Scan successfully finished. All application controls validated!' },
    ];

    steps.forEach((step, idx) => {
      setTimeout(() => {
        setProgress(step.p);
        setLogs((prev) => [
          ...prev,
          {
            id: Date.now() + idx,
            type: step.type as any,
            text: step.text,
            timestamp: new Date().toLocaleTimeString(),
          },
        ]);
        if (idx === steps.length - 1) {
          setIsScanning(false);
        }
      }, (idx + 1) * 900);
    });
  };

  return (
    <div className="w-full rounded-xl border border-emerald-500/30 bg-slate-950/90 p-5 shadow-2xl backdrop-blur-md">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
            <ShieldCheck className="w-6 h-6 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              AUTOMATED SECURITY SCAN PIPELINE
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/40">
                THANDEV SEC-ENGINE
              </span>
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              Live simulation of multi-tier vulnerability assessment & SAST/DAST workflow
            </p>
          </div>
        </div>

        <button
          onClick={runSimulation}
          disabled={isScanning}
          className={`px-4 py-2 rounded-lg font-mono text-xs font-bold transition-all flex items-center gap-2 shadow-lg ${
            isScanning
              ? 'bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700'
              : 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-400 hover:to-cyan-400 text-slate-950 shadow-emerald-500/20'
          }`}
        >
          {isScanning ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" /> SCANNING IN PROGRESS...
            </>
          ) : (
            <>
              <Play className="w-4 h-4 fill-current" /> EXECUTE SECURITY SCAN
            </>
          )}
        </button>
      </div>

      {/* Progress Bar */}
      <div className="my-4">
        <div className="flex justify-between text-xs font-mono mb-1.5">
          <span className="text-slate-400">PIPELINE EXECUTION STATUS:</span>
          <span className="text-emerald-400 font-bold">{progress}%</span>
        </div>
        <div className="w-full h-2.5 bg-slate-900 rounded-full overflow-hidden border border-slate-800 p-0.5">
          <div
            className="h-full bg-gradient-to-r from-emerald-500 via-cyan-400 to-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>

      {/* Security Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 my-4 font-mono">
        <div className="p-3 rounded-lg bg-slate-900/80 border border-cyan-500/20">
          <p className="text-[11px] text-slate-400">TOOLS INTEGRATED</p>
          <p className="text-xl font-bold text-cyan-400 mt-0.5">10+ Tools</p>
          <p className="text-[10px] text-slate-500">Semgrep, ZAP, Nuclei, Trivy</p>
        </div>
        <div className="p-3 rounded-lg bg-slate-900/80 border border-emerald-500/20">
          <p className="text-[11px] text-slate-400">CAMPUS APPS TESTED</p>
          <p className="text-xl font-bold text-emerald-400 mt-0.5">4 Enterprise</p>
          <p className="text-[10px] text-slate-500">Sodexo Campus Environment</p>
        </div>
        <div className="p-3 rounded-lg bg-slate-900/80 border border-purple-500/20">
          <p className="text-[11px] text-slate-400">AUTH VALIDATION</p>
          <p className="text-xl font-bold text-purple-400 mt-0.5">OAuth2 / RBAC</p>
          <p className="text-[10px] text-slate-500">GitHub, DNS TXT, JWT</p>
        </div>
        <div className="p-3 rounded-lg bg-slate-900/80 border border-amber-500/20">
          <p className="text-[11px] text-slate-400">ASYNC WORKERS</p>
          <p className="text-xl font-bold text-amber-400 mt-0.5">Up to 3 hrs</p>
          <p className="text-[10px] text-slate-500">Redis Streams + Celery</p>
        </div>
      </div>

      {/* Terminal Audit Log */}
      <div className="rounded-lg bg-slate-900/90 border border-slate-800 p-3 font-mono text-xs">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 text-slate-400">
          <span className="flex items-center gap-1.5 font-semibold">
            <Terminal className="w-3.5 h-3.5 text-emerald-400" /> AUDIT EVENT STREAM
          </span>
          <span className="text-[11px] text-emerald-400">LOG STATUS: OK</span>
        </div>

        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
          {logs.map((log) => (
            <div key={log.id} className="flex items-start gap-2">
              <span className="text-slate-500 shrink-0 text-[10px]">{log.timestamp}</span>
              <span
                className={`${
                  log.type === 'success'
                    ? 'text-emerald-400'
                    : log.type === 'warning'
                    ? 'text-yellow-400'
                    : log.type === 'error'
                    ? 'text-red-400'
                    : 'text-cyan-300'
                }`}
              >
                {log.text}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
