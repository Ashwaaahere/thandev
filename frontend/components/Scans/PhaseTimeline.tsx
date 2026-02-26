/**
 * PhaseTimeline Component
 * 
 * Real-time scan progress visualization with phases and tool states.
 * Replaces the old "7 checks" progress bar with a pentester-grade pipeline view.
 */

'use client';

import React from 'react';
import { ScanToolState } from '@/hooks/useScanEvents';

interface PhaseTimelineProps {
  toolStates: ScanToolState[];
  scanStatus: string;
  scanLevel?: string;
  isConnected: boolean;
}

interface Phase {
  id: string;
  label: string;
  description: string;
  order: number;
}

const ALL_PHASES: Phase[] = [
  { id: 'prepare', label: 'Prepare', description: 'Initializing scan', order: 1 },
  { id: 'enumerate', label: 'Enumerate', description: 'Asset discovery', order: 2 },
  { id: 'scan', label: 'Scan', description: 'Running security tools', order: 3 },
  { id: 'correlate_score', label: 'Correlate & Score', description: 'Analyzing findings', order: 4 },
  { id: 'finalize', label: 'Finalize', description: 'Generating report', order: 5 },
];

// Phases for Basic scans (no enumeration)
const BASIC_PHASES: Phase[] = [
  { id: 'prepare', label: 'Prepare', description: 'Initializing scan', order: 1 },
  { id: 'scan', label: 'Scan', description: 'Running security tools', order: 2 },
  { id: 'correlate_score', label: 'Correlate & Score', description: 'Analyzing findings', order: 3 },
  { id: 'finalize', label: 'Finalize', description: 'Generating report', order: 4 },
];

const TOOL_ICONS: Record<string, string> = {
  httpx: '🌐',
  katana: '🕷️',
  gau: '📡',
  arjun: '🔍',
  nuclei: '💣',
  dalfox: '💉',
  sqlmap: '🗄️',
  zap: '⚡',
  nmap: '🗺️',
  sslscan: '🔒',
  enumeration: '🔎',
};

const STAGE_LABELS: Record<string, string> = {
  queued: 'Queued',
  starting: 'Starting',
  running: 'Running',
  parsing: 'Parsing',
  uploading: 'Uploading',
  completed: 'Completed',
  timed_out: 'Completed',
  failed: 'Failed',
};

export default function PhaseTimeline({
  toolStates,
  scanStatus,
  scanLevel,
  isConnected,
}: PhaseTimelineProps) {
  // Select phases based on scan level
  const PHASES = React.useMemo(() => {
    return scanLevel === 'basic' ? BASIC_PHASES : ALL_PHASES;
  }, [scanLevel]);

  // Debug logging
  React.useEffect(() => {
    console.log('[PhaseTimeline] Tool states updated:', toolStates);
    console.log('[PhaseTimeline] Scan status:', scanStatus);
  }, [toolStates, scanStatus]);

  // Group tool states by phase
  const toolStatesByPhase = React.useMemo(() => {
    const grouped: Record<string, ScanToolState[]> = {};
    toolStates.forEach(state => {
      if (!grouped[state.phase]) {
        grouped[state.phase] = [];
      }
      grouped[state.phase].push(state);
    });
    return grouped;
  }, [toolStates]);

  // Determine current phase based on tool states and scan status
  const currentPhaseId = React.useMemo(() => {
    // If scan is completed, show finalize
    if (scanStatus === 'completed') return 'finalize';

    // If no tool states yet, we're in prepare phase
    if (toolStates.length === 0) return 'prepare';

    // Check each phase in priority order to find the active one
    // A phase is active if it has running/queued/starting tools OR if it's the latest phase with any activity
    // IMPORTANT: Check enumerate BEFORE scan to ensure enumeration phase is shown during enumeration
    const phaseOrder = ['finalize', 'correlate_score', 'scan', 'enumerate', 'prepare'];

    // First pass: Find phases with actively running tools (prioritize enumerate over scan)
    // Check enumerate first if it has any tools
    const enumerateTools = toolStatesByPhase['enumerate'] || [];
    const hasRunningEnumerate = enumerateTools.some(
      t => ['running', 'starting', 'queued', 'parsing', 'uploading'].includes(t.stage)
    );
    if (hasRunningEnumerate) {
      return 'enumerate';
    }

    // Then check other phases
    for (const phase of phaseOrder) {
      if (phase === 'enumerate') continue; // Already checked
      const phaseTools = toolStatesByPhase[phase] || [];
      const hasRunningTools = phaseTools.some(
        t => ['running', 'starting', 'queued', 'parsing', 'uploading'].includes(t.stage)
      );
      if (hasRunningTools) {
        return phase;
      }
    }

    // Second pass: Find the latest phase with any completed tools
    // But if enumerate has any tools (even completed), show it if scan hasn't started yet
    const scanTools = toolStatesByPhase['scan'] || [];
    const hasScanActivity = scanTools.length > 0;
    const enumerateHasActivity = enumerateTools.length > 0;

    if (enumerateHasActivity && !hasScanActivity) {
      // Enumeration has activity but scan hasn't started - show enumerate
      return 'enumerate';
    }

    for (const phase of phaseOrder) {
      if (toolStatesByPhase[phase]?.length > 0) {
        return phase;
      }
    }

    return 'prepare';
  }, [toolStates, toolStatesByPhase, scanStatus]);

  // Get phase status
  const getPhaseStatus = (phaseId: string): 'pending' | 'active' | 'completed' => {
    const currentPhase = PHASES.find(p => p.id === currentPhaseId);
    const thisPhase = PHASES.find(p => p.id === phaseId);

    if (!currentPhase || !thisPhase) return 'pending';

    if (thisPhase.order < currentPhase.order) return 'completed';
    if (thisPhase.order === currentPhase.order) return 'active';
    return 'pending';
  };

  // Get stage color
  const getStageColor = (stage: string) => {
    if (stage === 'completed' || stage === 'timed_out') return 'text-emerald-400';
    if (stage === 'failed') return 'text-red-400';
    if (stage === 'running' || stage === 'parsing' || stage === 'uploading') return 'text-blue-400';
    return 'text-slate-400';
  };

  // Get stage background
  const getStageBg = (stage: string) => {
    if (stage === 'completed' || stage === 'timed_out') return 'bg-emerald-500/20';
    if (stage === 'failed') return 'bg-red-500/20';
    if (stage === 'running' || stage === 'parsing' || stage === 'uploading') return 'bg-blue-500/20';
    return 'bg-slate-500/20';
  };

  return (
    <div className="rounded-2xl border shadow-lg p-6 overflow-hidden" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>Scan Pipeline</h2>
        <div className="flex items-center gap-2">
          {isConnected ? (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-xs font-medium text-emerald-400">Live</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-500/20">
              <div className="w-2 h-2 rounded-full bg-slate-400" />
              <span className="text-xs font-medium text-slate-400">Polling</span>
            </div>
          )}
        </div>
      </div>

      {/* Phase Timeline */}
      <div className="space-y-4">
        {PHASES.map((phase, idx) => {
          const phaseStatus = getPhaseStatus(phase.id);
          // Filter out the "enumeration" pseudo-tool from the UI card list
          const phaseToolStates = (toolStatesByPhase[phase.id] || []).filter(ts => ts.tool !== 'enumeration');
          const isActive = phaseStatus === 'active';
          const isCompleted = phaseStatus === 'completed';

          return (
            <div key={phase.id}>
              {/* Phase Header */}
              <div className="flex items-start gap-3">
                {/* Phase Indicator */}
                <div className="flex flex-col items-center">
                  <div
                    className={`w-8 h-8 rounded-full border-2 flex items-center justify-center font-semibold text-sm ${isCompleted
                        ? 'border-emerald-500 bg-emerald-500/20 text-emerald-400'
                        : isActive
                          ? 'border-blue-500 bg-blue-500/20 text-blue-400 animate-pulse'
                          : 'border-slate-600 bg-slate-800/40 text-slate-500'
                      }`}
                  >
                    {isCompleted ? '✓' : phase.order}
                  </div>
                  {idx < PHASES.length - 1 && (
                    <div
                      className={`w-0.5 h-12 mt-2 ${isCompleted ? 'bg-emerald-500/50' : 'bg-slate-700'
                        }`}
                    />
                  )}
                </div>

                {/* Phase Content */}
                <div className="flex-1 -mt-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3
                      className={`font-semibold ${isActive ? 'text-blue-400' : isCompleted ? 'text-emerald-400' : 'text-slate-400'
                        }`}
                    >
                      {phase.label}
                    </h3>
                    {isActive && (
                      <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full flex-shrink-0" />
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mb-3">{phase.description}</p>

                  {/* Tool Cards - only show for active or pending phases, not completed */}
                  {phaseToolStates.length > 0 && !isCompleted && (
                    <div className="space-y-2">
                      {phaseToolStates.map(toolState => {
                        const icon = TOOL_ICONS[toolState.tool] || '🔧';
                        const stageLabel = STAGE_LABELS[toolState.stage] || toolState.stage;
                        const stageColor = getStageColor(toolState.stage);
                        const stageBg = getStageBg(toolState.stage);

                        return (
                          <div
                            key={`${toolState.tool}-${toolState.phase}`}
                            className="rounded-lg border p-3 overflow-hidden"
                            style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                          >
                            <div className="flex items-start justify-between gap-2 min-w-0">
                              <div className="flex items-start gap-2 flex-1 min-w-0">
                                <span className="text-lg mt-0.5 flex-shrink-0">{icon}</span>
                                <div className="flex-1 min-w-0">
                                  <div className="font-medium text-sm mb-1 truncate" style={{ color: 'var(--fg)' }}>
                                    {toolState.tool.charAt(0).toUpperCase() + toolState.tool.slice(1)}
                                  </div>
                                  {toolState.last_message && (
                                    <p className="text-xs text-slate-400 mb-2 break-words overflow-wrap-anywhere" style={{ wordBreak: 'break-word' }}>
                                      {toolState.last_message}
                                    </p>
                                  )}
                                  {toolState.meta && (
                                    <div className="flex flex-wrap gap-2 text-xs">
                                      {Object.entries(toolState.meta).map(([key, value]) => {
                                        const valueStr = String(value);
                                        const isLongValue = valueStr.length > 50;
                                        return (
                                          <span
                                            key={key}
                                            className="px-2 py-0.5 rounded-full bg-slate-700/40 text-slate-300 break-words max-w-full"
                                            style={{ wordBreak: 'break-word' }}
                                            title={isLongValue ? valueStr : undefined}
                                          >
                                            {key}: {isLongValue ? `${valueStr.substring(0, 47)}...` : valueStr}
                                          </span>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-col items-end gap-1 flex-shrink-0">
                                <span
                                  className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${stageBg} ${stageColor}`}
                                >
                                  {stageLabel}
                                </span>
                                {toolState.progress !== null && toolState.progress !== undefined && (
                                  <span className="text-xs font-medium text-slate-400 whitespace-nowrap">
                                    {Math.round(toolState.progress)}%
                                  </span>
                                )}
                              </div>
                            </div>
                            {/* Progress bar */}
                            {toolState.progress !== null && toolState.progress !== undefined && (
                              <div className="mt-2 w-full h-1 rounded-full bg-slate-700 overflow-hidden">
                                <div
                                  className="h-full bg-blue-500 transition-all duration-300"
                                  style={{ width: `${Math.min(100, Math.max(0, toolState.progress))}%` }}
                                />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

