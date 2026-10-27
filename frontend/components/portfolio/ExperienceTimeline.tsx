'use client';

import React from 'react';
import { Briefcase, Calendar, MapPin, ShieldAlert, CheckCircle2, ChevronRight, Terminal } from 'lucide-react';

interface ExperienceItem {
  role: string;
  company: string;
  location: string;
  period: string;
  type: string;
  bullets: string[];
}

export default function ExperienceTimeline() {
  const experiences: ExperienceItem[] = [
    {
      role: 'IT Intern',
      company: 'Compass Group USA / Chartwells',
      location: 'Binghamton University, NY',
      period: 'Aug 2026 – Present',
      type: 'OPERATIONAL SECOPS & NETWORKS',
      bullets: [
        'Diagnose connectivity failures affecting POS terminals, inventory scanners, laptops, and phones by checking network connections and device configurations, isolating faults that interrupt dining operations.',
        'Coordinate infrastructure and vendor escalations when issues exceed local support access, documenting symptoms and troubleshooting steps and verifying restored functionality with affected users.',
        'Examine account access, firmware, and device configurations to identify security concerns; record findings and coordinate corrective actions with IT to support reliable operation of connected dining systems.',
        'Review endpoint alerts and patch status alongside asset records, linking unresolved device issues to remediation notes so the IT team can track ownership, maintenance needs, and follow-up.',
      ],
    },
    {
      role: 'IT Security Intern',
      company: 'Sodexo Dining Services',
      location: 'Binghamton University, NY',
      period: 'Aug 2025 – May 2026',
      type: 'PENETRATION TESTING & APPLICATION SECURITY',
      bullets: [
        'Conducted authorized penetration testing of 4 applications hosted in Sodexo’s environment—IT ticketing, waste-food management, job-application availability, and day-off requests—to assess campus software before operational use.',
        'Tested authentication, authorization, role separation, session management, and input handling against common OWASP risks, documenting affected functions and reproduction steps for engineering review.',
        'Reviewed scan findings and application-test evidence with the IT manager and remote security engineers, prioritized remediation, and retested patches or configuration changes to verify fixes before release.',
        'Configured role-based permissions across Grubhub, Transact, and Foodr, validated restrictions on administrative actions, and checked separation across payment, staff, and guest networks to identify unauthorized-access risks.',
      ],
    },
    {
      role: 'Founder & Security Lead',
      company: 'Condottiere',
      location: 'Chennai, India',
      period: 'Aug 2022 – Jun 2024',
      type: 'SAST/DAST ASSESSMENT & TECHNICAL LEADERSHIP',
      bullets: [
        'Conducted SAST and DAST for medical-sector client applications, examining security weaknesses with attention to sensitive information and translating findings into remediation priorities for developers.',
        'Coordinated application fixes alongside delivery milestones, communicating technical risks and recommended changes to clients and developers to incorporate security review into development and maintenance.',
        'Led client consultations and coordinated 5 disciplines—web development, app development, design, social media, and SEO—aligning requirements and schedules to deliver projects on time and improve client conversions.',
      ],
    },
  ];

  return (
    <div className="w-full space-y-6 font-sans">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            PROFESSIONAL EXPERIENCE LOGS
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/40">
              AUDITED AUDIT TRAIL
            </span>
          </h3>
          <p className="text-xs text-slate-400 font-mono">
            Hands-on work in application security, penetration testing, endpoint security, and SecOps workflows
          </p>
        </div>
      </div>

      <div className="relative border-l-2 border-cyan-500/30 ml-3 md:ml-6 space-y-8 pl-6">
        {experiences.map((exp, idx) => (
          <div key={idx} className="relative group">
            {/* Timeline node */}
            <div className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full bg-slate-950 border-2 border-cyan-400 group-hover:bg-cyan-400 transition-colors flex items-center justify-center">
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 group-hover:bg-slate-950"></div>
            </div>

            {/* Content card */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 hover:border-cyan-500/40 transition-all p-5 shadow-xl space-y-3">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                <div>
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800/50 uppercase">
                    {exp.type}
                  </span>
                  <h4 className="text-lg font-bold text-slate-100 mt-1 flex items-center gap-2">
                    {exp.role} <span className="text-cyan-400">@ {exp.company}</span>
                  </h4>
                </div>

                <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
                  <span className="flex items-center gap-1 text-slate-300">
                    <Calendar className="w-3.5 h-3.5 text-cyan-400" /> {exp.period}
                  </span>
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-emerald-400" /> {exp.location}
                  </span>
                </div>
              </div>

              {/* Bullet points */}
              <ul className="space-y-2 text-xs md:text-sm text-slate-300 leading-relaxed">
                {exp.bullets.map((bullet, bIdx) => (
                  <li key={bIdx} className="flex items-start gap-2.5">
                    <ChevronRight className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
