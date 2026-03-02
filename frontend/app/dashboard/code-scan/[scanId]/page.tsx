'use client';

import { useSession } from 'next-auth/react';
import { useEffect, useState } from 'react';
import { useRouter, useParams } from 'next/navigation';
import AppShell from '@/components/layout/AppShell';
import { Card } from '@/components/ui/Card';
import StatCard from '@/components/ui/StatCard';
import Badge from '@/components/ui/Badge';
import { TabList, Tab, TabPanel } from '@/components/ui/Tabs';
import JsonViewerPanel from '@/components/ui/JsonViewerPanel';
import SeverityBadge from '@/components/Scans/SeverityBadge';
import { thandevFetchJSON } from '@/lib/thandevApi';

type CodeScanDetail = {
  id: string;
  project_id: string;
  scan_type: string;
  provider: string;
  repo_full_name: string;
  ref?: string;
  sha?: string;
  run_id?: string;
  status: string;
  summary_json?: Record<string, unknown>;
  meta_json?: { artifacts?: Record<string, unknown>; pipeline_run_url?: string };
  created_at: string;
  completed_at?: string;
};

const TOOL_TABS = ['semgrep', 'gitleaks', 'osv', 'trivy', 'sbom', 'sarif'] as const;
type ToolKey = (typeof TOOL_TABS)[number];

// --- Security summary: severity counts from all tools ---
type SeverityCounts = {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  secrets: number;
};

function normalizeSeverity(s: string | null | undefined): keyof Omit<SeverityCounts, 'total' | 'secrets'> {
  if (!s) return 'info';
  const lower = String(s).toLowerCase();
  if (lower === 'critical' || lower === 'error') return 'critical';
  if (lower === 'high') return 'high';
  if (lower === 'medium' || lower === 'warning') return 'medium';
  if (lower === 'low' || lower === 'note') return 'low';
  if (lower === 'info') return 'info';
  return 'info';
}

function computeSecuritySummary(artifacts: Record<string, unknown> | null | undefined): SeverityCounts {
  const counts: SeverityCounts = { total: 0, critical: 0, high: 0, medium: 0, low: 0, info: 0, secrets: 0 };
  if (!artifacts || typeof artifacts !== 'object') return counts;

  // Semgrep: results[].extra.severity (or top-level array / matches / single finding object)
  const semgrep = artifacts.semgrep;
  if (semgrep !== undefined && semgrep !== null) {
    let semgrepResults: Record<string, unknown>[] = [];
    if (Array.isArray(semgrep)) semgrepResults = semgrep as Record<string, unknown>[];
    else if (typeof semgrep === 'object') {
      const obj = semgrep as Record<string, unknown>;
      const fromKey = (obj.results as Record<string, unknown>[] | undefined) ?? (obj.matches as Record<string, unknown>[] | undefined);
      if (Array.isArray(fromKey)) semgrepResults = fromKey;
      else if (obj.path != null && (obj.start != null || obj.line != null)) semgrepResults = [obj];
    }
    for (const r of semgrepResults) {
      const extra = r?.extra as Record<string, unknown> | undefined;
      const sev = (extra?.severity ?? (extra?.metadata as Record<string, unknown>)?.severity) as string | undefined;
      counts[normalizeSeverity(sev)]++;
      counts.total++;
    }
  }

  // Gitleaks: count findings + secrets
  const gitleaks = artifacts.gitleaks;
  if (gitleaks !== undefined && gitleaks !== null) {
    let n = 0;
    if (Array.isArray(gitleaks)) n = gitleaks.length;
    else if (typeof gitleaks === 'object' && Array.isArray((gitleaks as Record<string, unknown>).runs)) {
      const runs = (gitleaks as { runs: { results: unknown[] }[] }).runs;
      n = runs.reduce((acc, run) => acc + (run.results?.length ?? 0), 0);
    }
    counts.secrets += n;
    counts.total += n;
  }

  // SARIF: runs[].results[].level (error -> high, warning -> medium, note -> low)
  const sarif = artifacts.sarif as Record<string, unknown> | undefined;
  if (sarif && Array.isArray(sarif.runs)) {
    for (const run of sarif.runs as Record<string, unknown>[]) {
      const results = run.results as Record<string, unknown>[] | undefined;
      if (!Array.isArray(results)) continue;
      for (const res of results) {
        const level = (res.level as string) || 'warning';
        const lower = level.toLowerCase();
        if (lower === 'error') counts.high++;
        else if (lower === 'warning') counts.medium++;
        else counts.low++;
        counts.total++;
      }
    }
  }

  // Trivy: Results[].Vulnerabilities[].Severity (or top-level .Results)
  const trivy = artifacts.trivy;
  if (trivy !== undefined && trivy !== null && typeof trivy === 'object') {
    const results = (trivy as Record<string, unknown>).Results as Record<string, unknown>[] | undefined;
    const arr = Array.isArray(results) ? results : (Array.isArray((trivy as Record<string, unknown>).Vulnerabilities) ? [{ Vulnerabilities: (trivy as Record<string, unknown>).Vulnerabilities }] : []);
    for (const r of arr) {
      const vulns = (r?.Vulnerabilities ?? r?.vulnerabilities) as Record<string, unknown>[] | undefined;
      if (!Array.isArray(vulns)) continue;
      for (const v of vulns) {
        const sev = (v.Severity ?? v.severity) as string | undefined;
        counts[normalizeSeverity(sev)]++;
        counts.total++;
      }
    }
  }

  // OSV: vulnerabilities with severity (e.g. database_specific.severity or .severity)
  const osv = artifacts.osv;
  if (osv !== undefined && osv !== null && typeof osv === 'object') {
    const vulns = (osv as Record<string, unknown>).vulns ?? (osv as Record<string, unknown>).vulnerabilities;
    const list = Array.isArray(vulns) ? vulns : (Array.isArray((osv as Record<string, unknown>).results) ? (osv as { results: { vulns?: unknown[] }[] }).results.flatMap((r) => r.vulns ?? []) : []);
    for (const v of list) {
      const obj = v as Record<string, unknown>;
      const sev = (obj.severity ?? (obj.database_specific as Record<string, unknown>)?.severity) as string | undefined;
      counts[normalizeSeverity(sev)]++;
      counts.total++;
    }
  }

  return counts;
}

// --- Structured row types and extractors ---
type SemgrepRow = { ruleId: string; severity: string; file: string; line: number; message: string };
function getSemgrepRows(data: unknown): SemgrepRow[] {
  let results: Record<string, unknown>[] = [];
  if (Array.isArray(data)) {
    results = data as Record<string, unknown>[];
  } else if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    const fromKey = (obj.results as Record<string, unknown>[] | undefined) ??
      (obj.matches as Record<string, unknown>[] | undefined);
    if (Array.isArray(fromKey)) {
      results = fromKey;
    } else if (obj.path != null && (obj.start != null || obj.line != null)) {
      // Single finding object (e.g. { path, start, end } at root)
      results = [obj];
    }
  }
  return results.map((r) => {
    const extra = (r.extra as Record<string, unknown>) ?? {};
    const start = (r.start as Record<string, unknown>) ?? {};
    return {
      ruleId: String(r.check_id ?? r.rule_id ?? r.ruleID ?? '—'),
      severity: String(extra.severity ?? (extra.metadata as Record<string, unknown>)?.severity ?? 'INFO').toUpperCase(),
      file: String(r.path ?? r.file ?? r.filename ?? '—'),
      line: Number(start.line ?? r.line ?? 0) || 0,
      message: String(extra.message ?? r.message ?? '—'),
    };
  });
}

type GitleaksRow = { secretType: string; file: string; line: number; description: string };
function getGitleaksRows(data: unknown): GitleaksRow[] {
  if (Array.isArray(data)) {
    return data.map((item: Record<string, unknown>) => ({
      secretType: String(item.RuleID ?? item.ruleID ?? item.SecretType ?? '—'),
      file: String(item.File ?? item.file ?? item.Match ?? '—'),
      line: Number(item.Line ?? item.line ?? 0) || 0,
      description: String(item.Description ?? item.description ?? item.Message ?? '—'),
    }));
  }
  const sarif = data as Record<string, unknown>;
  const runs = (sarif.runs as Record<string, unknown>[]) ?? [];
  const rows: GitleaksRow[] = [];
  for (const run of runs) {
    const results = (run.results as Record<string, unknown>[]) ?? [];
    const tool = run.tool as Record<string, unknown> | undefined;
    const driver = tool?.driver as Record<string, unknown> | undefined;
    const rules = (driver?.rules as Record<string, unknown>[]) ?? [];
    const ruleMap = new Map(rules.map((r) => [r.id, r]));
    for (const res of results) {
      const ruleId = res.ruleId as string;
      const rule = ruleMap.get(ruleId) as Record<string, unknown> | undefined;
      const locs = (res.locations ?? []) as { physicalLocation?: { artifactLocation?: { uri?: string }; region?: { startLine?: number } } }[];
      const loc = locs[0];
      const file = loc?.physicalLocation?.artifactLocation?.uri ?? '—';
      const line = loc?.physicalLocation?.region?.startLine ?? 0;
      rows.push({
        secretType: ruleId ?? '—',
        file: String(file),
        line: Number(line) || 0,
        description: String(
          (res.message as Record<string, unknown>)?.text ??
            (rule?.shortDescription as Record<string, unknown>)?.text ??
            (rule?.fullDescription as Record<string, unknown>)?.text ??
            '—'
        ),
      });
    }
  }
  return rows;
}

type TrivyRow = { cve: string; package: string; installedVersion: string; severity: string; fixedVersion: string };
function getTrivyRows(data: unknown): TrivyRow[] {
  const rows: TrivyRow[] = [];
  let results: Record<string, unknown>[] = [];
  if (Array.isArray(data)) {
    results = data as Record<string, unknown>[];
  } else if (data && typeof data === 'object') {
    results = ((data as Record<string, unknown>).Results as Record<string, unknown>[]) ?? [];
  }
  for (const r of results) {
    const vulns = (r.Vulnerabilities ?? r.vulnerabilities) as Record<string, unknown>[] | undefined;
    if (!Array.isArray(vulns)) continue;
    const target = String(r.Target ?? r.target ?? '—');
    for (const v of vulns) {
      rows.push({
        cve: String(v.VulnerabilityID ?? v.vulnerabilityID ?? v.CVE ?? '—'),
        package: String(v.PkgName ?? v.pkgName ?? target),
        installedVersion: String(v.InstalledVersion ?? v.installedVersion ?? '—'),
        severity: String(v.Severity ?? v.severity ?? 'UNKNOWN').toUpperCase(),
        fixedVersion: String(v.FixedVersion ?? v.fixedVersion ?? '—'),
      });
    }
  }
  return rows;
}

type OsvRow = { pkg: string; id: string; severity: string; fixedVersion: string };
function getOsvRows(data: unknown): OsvRow[] {
  const obj = data as Record<string, unknown>;
  let list: Record<string, unknown>[] = [];
  const pkg = String(obj.name ?? obj.package ?? '—');
  if (Array.isArray(obj.vulns)) list = obj.vulns as Record<string, unknown>[];
  else if (Array.isArray(obj.vulnerabilities)) list = obj.vulnerabilities as Record<string, unknown>[];
  else if (Array.isArray(obj.results)) {
    const results = obj.results as Record<string, unknown>[];
    list = results.flatMap((r) => (Array.isArray(r.vulns) ? (r.vulns as Record<string, unknown>[]) : []));
  }
  return list.map((v) => ({
    pkg,
    id: String(v.id ?? (v.aliases as unknown[])?.[0] ?? '—'),
    severity: String((v.severity ?? (v.database_specific as Record<string, unknown>)?.severity) ?? '—').toUpperCase(),
    fixedVersion: String((v.database_specific as Record<string, unknown>)?.fixed_version ?? (v.affected as Record<string, unknown>[])?.[0]?.ranges?.[0]?.events?.[0]?.fixed ?? '—'),
  }));
}

// SBOM: component count and ecosystem breakdown
type SbomSummary = { totalComponents: number; byEcosystem: Record<string, number>; raw: unknown };
function getSbomSummary(data: unknown): SbomSummary {
  const obj = data as Record<string, unknown>;
  const components = (obj.components ?? obj.Components ?? obj.packages) as Record<string, unknown>[] | undefined;
  const arr = Array.isArray(components) ? components : [];
  const byEcosystem: Record<string, number> = {};
  for (const c of arr) {
    const eco = String((c as Record<string, unknown>).type ?? (c as Record<string, unknown>).Type ?? (c as Record<string, unknown>).purl ?? 'other');
    byEcosystem[eco] = (byEcosystem[eco] ?? 0) + 1;
  }
  return { totalComponents: arr.length, byEcosystem, raw: data };
}

// SARIF table (generic): Rule ID, Level, File, Line, Message
type SarifRow = { ruleId: string; level: string; file: string; line: number; message: string };
function getSarifRows(data: unknown): SarifRow[] {
  const obj = data as Record<string, unknown>;
  const runs = (obj.runs as Record<string, unknown>[]) ?? [];
  const rows: SarifRow[] = [];
  for (const run of runs) {
    const results = (run.results as Record<string, unknown>[]) ?? [];
    for (const res of results) {
      const locs = (res.locations ?? []) as { physicalLocation?: { artifactLocation?: { uri?: string }; region?: { startLine?: number } } }[];
      const loc = locs[0];
      const file = loc?.physicalLocation?.artifactLocation?.uri ?? '—';
      const line = loc?.physicalLocation?.region?.startLine ?? 0;
      const msg = res.message as Record<string, unknown> | undefined;
      rows.push({
        ruleId: String(res.ruleId ?? '—'),
        level: String(res.level ?? 'warning').toUpperCase(),
        file: String(file),
        line: Number(line) || 0,
        message: String(msg?.text ?? res.message ?? '—'),
      });
    }
  }
  return rows;
}

// --- UI: Empty state (matches design system) ---
function EmptyState() {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 px-4 rounded-xl border"
      style={{ background: 'var(--card-2)', borderColor: 'var(--border)' }}
    >
      <span className="text-4xl mb-2" aria-hidden>🎉</span>
      <p className="text-center font-medium" style={{ color: 'var(--text)' }}>
        No vulnerabilities detected
      </p>
    </div>
  );
}

const tableHeaderStyle = { background: 'var(--card-2)', borderColor: 'var(--border)', color: 'var(--text)' };
const tableBorderStyle = { borderColor: 'var(--border)' };
const tableRowStyle = { color: 'var(--text)' };
const tableCellMutedStyle = { color: 'var(--muted)' };

export default function CodeScanDetailPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const params = useParams<{ scanId: string }>();
  const scanId = params?.scanId;

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [scan, setScan] = useState<CodeScanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ToolKey>('semgrep');

  useEffect(() => {
    if (!session || !scanId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const data = await thandevFetchJSON<CodeScanDetail>(`/api/code-scans/scans/${encodeURIComponent(scanId)}`, session);
        if (!cancelled) setScan(data);
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : 'Failed to load code scan';
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [session, scanId]);

  const artifacts = (scan?.meta_json && scan.meta_json.artifacts) as Record<string, unknown> | undefined;
  const summary = computeSecuritySummary(artifacts);

  const postureBadge =
    summary.critical > 0 ? 'critical' : summary.high > 0 ? 'high' : 'normal';
  const postureStyle = {
    critical: 'bg-red-900/50 text-red-200 border-red-500/60',
    high: 'bg-amber-900/50 text-amber-200 border-amber-500/60',
    normal: 'bg-emerald-900/40 text-emerald-200 border-emerald-500/50',
  };

  const currentToolData = (activeTab && artifacts?.[activeTab]) ?? null;

  function getTabCount(tool: ToolKey): number {
    const data = artifacts?.[tool];
    if (data == null) return 0;
    if (tool === 'semgrep') return getSemgrepRows(data).length;
    if (tool === 'gitleaks') return getGitleaksRows(data).length;
    if (tool === 'trivy') return getTrivyRows(data).length;
    if (tool === 'osv') return getOsvRows(data).length;
    if (tool === 'sbom') return getSbomSummary(data).totalComponents;
    if (tool === 'sarif') return getSarifRows(data).length;
    return 0;
  }

  const runUrl: string | undefined = scan?.meta_json?.pipeline_run_url;

  return (
    <AppShell
      user={session?.user}
      sidebarOpen={sidebarOpen}
      setSidebarOpen={setSidebarOpen}
    >
      <div className="space-y-6">
        {/* Page title block — same rhythm as Overview/Projects */}
        <div className="mb-6">
          <button
            type="button"
            onClick={() => router.back()}
            className="text-sm mb-2 transition-colors hover:opacity-90"
            style={{ color: 'var(--muted)' }}
          >
            ← Back to Code Scan
          </button>
          <h1 className="text-3xl font-bold mb-1.5 flex items-center gap-3 flex-wrap" style={{ color: 'var(--text)' }}>
            Code Scan Details
            {scan && (
              <>
                <Badge variant="neutral" size="md">{scan.provider}</Badge>
                <Badge
                  variant={postureBadge === 'critical' ? 'critical' : postureBadge === 'high' ? 'high' : 'good'}
                  size="md"
                >
                  {postureBadge === 'critical' ? 'Critical' : postureBadge === 'high' ? 'Needs attention' : 'Good'}
                </Badge>
              </>
            )}
          </h1>
          <p className="text-base" style={{ color: 'var(--muted)' }}>
            Security findings and raw artifacts from this scan
          </p>
        </div>

        {loading ? (
          <p style={{ color: 'var(--muted)' }}>Loading code scan…</p>
        ) : error ? (
          <p className="text-sm" style={{ color: 'var(--danger)' }}>{error}</p>
        ) : !scan ? (
          <p style={{ color: 'var(--muted)' }}>Code scan not found.</p>
        ) : (
          <>
            {/* Security summary — StatCards same size/spacing as Overview */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-5 mb-6">
              <StatCard label="Total Issues" value={summary.total} />
              <StatCard label="Critical" value={summary.critical} accent="critical" />
              <StatCard label="High" value={summary.high} accent="high" />
              <StatCard label="Medium" value={summary.medium} />
              <StatCard label="Low" value={summary.low} />
              <StatCard label="Secrets" value={summary.secrets} accent="high" />
            </div>

            {/* Scan metadata card */}
            <Card className="mb-6">
              <div className="p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm" style={{ color: 'var(--text)' }}>{scan.repo_full_name}</span>
                  {scan.ref && <span className="text-xs" style={{ color: 'var(--muted)' }}>{scan.ref}</span>}
                  {scan.sha && (
                    <span className="text-xs font-mono" style={{ color: 'var(--muted)' }} title={scan.sha}>
                      {scan.sha.slice(0, 7)}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-4 text-xs mt-2" style={{ color: 'var(--muted)' }}>
                  <span>Status: {scan.status}</span>
                  <span>Created: {new Date(scan.created_at).toLocaleString()}</span>
                  {scan.completed_at && <span>Completed: {new Date(scan.completed_at).toLocaleString()}</span>}
                  {runUrl && (
                    <a href={runUrl} target="_blank" rel="noreferrer" className="underline" style={{ color: 'var(--brand)' }}>
                      View CI run
                    </a>
                  )}
                </div>
                {scan.summary_json && Array.isArray(scan.summary_json.sources) && (
                  <div className="flex flex-wrap items-center gap-2 text-xs mt-2">
                    <span style={{ color: 'var(--muted)' }}>Sources:</span>
                    {(scan.summary_json.sources as string[]).map((src) => (
                      <Badge key={src} variant="neutral" size="sm">{src}</Badge>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            {/* Tool tabs — Card + Tabs primitive */}
            <Card>
              <TabList>
                {TOOL_TABS.map((tool) => {
                  const count = getTabCount(tool);
                  return (
                    <Tab
                      key={tool}
                      active={activeTab === tool}
                      onClick={() => setActiveTab(tool)}
                    >
                      {tool.toUpperCase()}
                      {count > 0 && <span className="ml-1.5 opacity-70">({count})</span>}
                    </Tab>
                  );
                })}
              </TabList>
              <TabPanel className="space-y-4">
                {!currentToolData ? (
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>No data uploaded for this tool.</p>
                ) : (
                      <>
                        {/* Structured view per tool */}
                        {activeTab === 'semgrep' && (() => {
                          const rows = getSemgrepRows(currentToolData);
                          if (rows.length === 0) return <EmptyState />;
                          return (
                            <div className="overflow-x-auto rounded-lg border" style={tableBorderStyle}>
                              <table className="w-full text-left text-sm">
                                <thead className="border-b" style={tableHeaderStyle}>
                                  <tr>
                                    <th className="px-3 py-2 font-medium">Rule ID</th>
                                    <th className="px-3 py-2 font-medium">Severity</th>
                                    <th className="px-3 py-2 font-medium">File</th>
                                    <th className="px-3 py-2 font-medium w-16">Line</th>
                                    <th className="px-3 py-2 font-medium">Message</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y" style={{ ...tableRowStyle, borderColor: 'var(--border)' }}>
                                  {rows.map((row, i) => (
                                    <tr key={i} className="hover:opacity-90 transition-opacity">
                                      <td className="px-3 py-2 font-mono text-xs">{row.ruleId}</td>
                                      <td className="px-3 py-2">
                                        <SeverityBadge severity={row.severity} size="sm" />
                                      </td>
                                      <td className="px-3 py-2 font-mono text-xs truncate max-w-[200px]" title={row.file}>{row.file}</td>
                                      <td className="px-3 py-2">{row.line || '—'}</td>
                                      <td className="px-3 py-2 max-w-md truncate" style={tableCellMutedStyle} title={row.message}>{row.message}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}
                        {activeTab === 'gitleaks' && (() => {
                          const rows = getGitleaksRows(currentToolData);
                          if (rows.length === 0) return <EmptyState />;
                          return (
                            <div className="overflow-x-auto rounded-lg border" style={tableBorderStyle}>
                              <table className="w-full text-left text-sm">
                                <thead className="border-b" style={tableHeaderStyle}>
                                  <tr>
                                    <th className="px-3 py-2 font-medium">Secret Type</th>
                                    <th className="px-3 py-2 font-medium">File</th>
                                    <th className="px-3 py-2 font-medium w-16">Line</th>
                                    <th className="px-3 py-2 font-medium">Description</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y" style={{ ...tableRowStyle, borderColor: 'var(--border)' }}>
                                  {rows.map((row, i) => (
                                    <tr key={i} className="hover:opacity-90 transition-opacity">
                                      <td className="px-3 py-2 font-mono text-xs">{row.secretType}</td>
                                      <td className="px-3 py-2 font-mono text-xs truncate max-w-[200px]" title={row.file}>{row.file}</td>
                                      <td className="px-3 py-2">{row.line || '—'}</td>
                                      <td className="px-3 py-2 max-w-md truncate" style={tableCellMutedStyle} title={row.description}>{row.description}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}
                        {activeTab === 'trivy' && (() => {
                          const rows = getTrivyRows(currentToolData);
                          if (rows.length === 0) return <EmptyState />;
                          return (
                            <div className="overflow-x-auto rounded-lg border" style={tableBorderStyle}>
                              <table className="w-full text-left text-sm">
                                <thead className="border-b" style={tableHeaderStyle}>
                                  <tr>
                                    <th className="px-3 py-2 font-medium">CVE</th>
                                    <th className="px-3 py-2 font-medium">Package</th>
                                    <th className="px-3 py-2 font-medium">Installed</th>
                                    <th className="px-3 py-2 font-medium">Severity</th>
                                    <th className="px-3 py-2 font-medium">Fixed Version</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y" style={{ ...tableRowStyle, borderColor: 'var(--border)' }}>
                                  {rows.map((row, i) => (
                                    <tr key={i} className="hover:opacity-90 transition-opacity">
                                      <td className="px-3 py-2 font-mono text-xs">{row.cve}</td>
                                      <td className="px-3 py-2 font-mono text-xs">{row.package}</td>
                                      <td className="px-3 py-2" style={tableCellMutedStyle}>{row.installedVersion}</td>
                                      <td className="px-3 py-2">
                                        <SeverityBadge severity={row.severity} size="sm" />
                                      </td>
                                      <td className="px-3 py-2" style={tableCellMutedStyle}>{row.fixedVersion}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}
                        {activeTab === 'osv' && (() => {
                          const rows = getOsvRows(currentToolData);
                          if (rows.length === 0) return <EmptyState />;
                          return (
                            <div className="overflow-x-auto rounded-lg border" style={tableBorderStyle}>
                              <table className="w-full text-left text-sm">
                                <thead className="border-b" style={tableHeaderStyle}>
                                  <tr>
                                    <th className="px-3 py-2 font-medium">Package</th>
                                    <th className="px-3 py-2 font-medium">ID</th>
                                    <th className="px-3 py-2 font-medium">Severity</th>
                                    <th className="px-3 py-2 font-medium">Fixed Version</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y" style={{ ...tableRowStyle, borderColor: 'var(--border)' }}>
                                  {rows.map((row, i) => (
                                    <tr key={i} className="hover:opacity-90 transition-opacity">
                                      <td className="px-3 py-2 font-mono text-xs">{row.pkg}</td>
                                      <td className="px-3 py-2 font-mono text-xs">{row.id}</td>
                                      <td className="px-3 py-2">
                                        <SeverityBadge severity={row.severity} size="sm" />
                                      </td>
                                      <td className="px-3 py-2" style={tableCellMutedStyle}>{row.fixedVersion}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}
                        {activeTab === 'sbom' && (() => {
                          const sbom = getSbomSummary(currentToolData);
                          const ecosystems = Object.entries(sbom.byEcosystem).sort((a, b) => b[1] - a[1]);
                          return (
                            <div className="space-y-4">
                              <div className="flex flex-wrap items-center gap-4">
                                <div className="rounded-xl border px-4 py-3" style={{ background: 'var(--card-2)', borderColor: 'var(--border)' }}>
                                  <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--muted)' }}>Total components</p>
                                  <p className="text-xl font-bold" style={{ color: 'var(--text)' }}>{sbom.totalComponents}</p>
                                </div>
                                {ecosystems.length > 0 && (
                                  <div className="flex flex-wrap gap-2">
                                    {ecosystems.map(([name, count]) => (
                                      <Badge key={name} variant="neutral" size="md">{name}: {count}</Badge>
                                    ))}
                                  </div>
                                )}
                                <a
                                  href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(currentToolData, null, 2))}`}
                                  download={`sbom-${scanId}.json`}
                                  className="inline-flex items-center px-3 py-2 rounded-lg border text-sm transition-colors hover:opacity-90"
                                  style={{ borderColor: 'var(--border)', background: 'var(--card-2)', color: 'var(--text)' }}
                                >
                                  Download SBOM
                                </a>
                              </div>
                              {sbom.totalComponents === 0 && <EmptyState />}
                            </div>
                          );
                        })()}
                        {activeTab === 'sarif' && (() => {
                          const rows = getSarifRows(currentToolData);
                          if (rows.length === 0) return <EmptyState />;
                          return (
                            <div className="overflow-x-auto rounded-lg border" style={tableBorderStyle}>
                              <table className="w-full text-left text-sm">
                                <thead className="border-b" style={tableHeaderStyle}>
                                  <tr>
                                    <th className="px-3 py-2 font-medium">Rule ID</th>
                                    <th className="px-3 py-2 font-medium">Level</th>
                                    <th className="px-3 py-2 font-medium">File</th>
                                    <th className="px-3 py-2 font-medium w-16">Line</th>
                                    <th className="px-3 py-2 font-medium">Message</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y" style={{ ...tableRowStyle, borderColor: 'var(--border)' }}>
                                  {rows.map((row, i) => (
                                    <tr key={i} className="hover:opacity-90 transition-opacity">
                                      <td className="px-3 py-2 font-mono text-xs">{row.ruleId}</td>
                                      <td className="px-3 py-2">
                                        <SeverityBadge severity={row.level} size="sm" />
                                      </td>
                                      <td className="px-3 py-2 font-mono text-xs truncate max-w-[200px]" title={row.file}>{row.file}</td>
                                      <td className="px-3 py-2">{row.line || '—'}</td>
                                      <td className="px-3 py-2 max-w-md truncate" style={tableCellMutedStyle} title={row.message}>{row.message}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          );
                        })()}

                        <JsonViewerPanel data={currentToolData} title="View Raw JSON" maxHeight="400px" />
                      </>
                )}
              </TabPanel>
            </Card>
          </>
        )}
      </div>
    </AppShell>
  );
}
