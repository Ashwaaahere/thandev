/**
 * Phase Timeline Component
 * Displays scan progress organized by phases with real-time updates
 */
import React, { useMemo } from 'react';
import {type ScanToolState } from '@/lib/hooks/useScanEvents';

interface PhaseTimelineProps {
  toolStates: Map<string, ScanToolState>;
  scanLevel?: string;
  isConnected: boolean;
}

const PHASES = [
  { id: 'prepare', label: 'Prepare', icon: '⚙️' },
  { id: 'enumerate', label: 'Enumerate', icon: '🔍' },
  { id: 'scan', label: 'Scan', icon: '🎯' },
  { id: 'correlate_score', label: 'Correlate & Score', icon: '📊' },
  { id: 'finalize', label: 'Finalize', icon: '✅' },
] as const;

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  httpx: 'HTTPX',
  nuclei: 'Nuclei',
  zap: 'ZAP',
  dalfox: 'Dalfox',
  sqlmap: 'SQLMap',
  nmap: 'Nmap',
  sslscan: 'SSLScan',
  katana: 'Katana',
  gau: 'GAU',
  arjun: 'Arjun',
};

const STAGE_ICONS: Record<string, string> = {
  queued: '⏳',
  starting: '▶️',
  running: '⚡',
  parsing: '📋',
  uploading: '☁️',
  completed: '✅',
  failed: '❌',
  skipped: '⏭️',
};

const STAGE_COLORS: Record<string, string> = {
  queued: 'text-slate-400',
  starting: 'text-blue-400',
  running: 'text-yellow-400',
  parsing: 'text-purple-400',
  uploading: 'text-cyan-400',
  completed: 'text-emerald-400',
  timed_out: 'text-emerald-400',
  failed: 'text-red-400',
  skipped: 'text-slate-500',
};

export function PhaseTimeline({ toolStates, scanLevel, isConnected }: PhaseTimelineProps) {
  // Group tool states by phase
  const phaseTools = useMemo(() => {
    const grouped = new Map<string, ScanToolState[]>();
    
    toolStates.forEach((state) => {
      if (!grouped.has(state.phase)) {
        grouped.set(state.phase, []);
      }
      grouped.get(state.phase)!.push(state);
    });
    
    return grouped;
  }, [toolStates]);

  // Determine current phase based on latest event or tool state
  const currentPhase = useMemo(() => {
    if (toolStates.size === 0) return 'prepare';
    
    // Find the latest phase from tool states
    let latestPhase = 'prepare';
    const phaseOrder = ['prepare', 'enumerate', 'scan', 'correlate_score', 'finalize'];
    
    toolStates.forEach((state) => {
      const currentIndex = phaseOrder.indexOf(latestPhase);
      const stateIndex = phaseOrder.indexOf(state.phase);
      if (stateIndex > currentIndex) {
        latestPhase = state.phase;
      }
    });
    
    return latestPhase;
  }, [toolStates]);

  return (
    <div className="space-y-6">
      {/* Connection Status Indicator */}
      {!isConnected && (
        <div className="flex items-center gap-2 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-400 text-sm">
          <span className="animate-pulse">⚠️</span>
          <span>Reconnecting to live updates...</span>
        </div>
      )}

      {/* Phase Timeline */}
      {PHASES.map((phase, index) => {
        const tools = phaseTools.get(phase.id) || [];
        const isActive = phase.id === currentPhase;
        const isCompleted = PHASES.findIndex(p => p.id === currentPhase) > index;
        const hasTools = tools.length > 0;

        return (
          <div key={phase.id} className="relative">
            {/* Phase Header */}
            <div className={`flex items-center gap-3 mb-4 ${
              isActive ? 'text-blue-400' : isCompleted ? 'text-emerald-400' : 'text-slate-500'
            }`}>
              <div className={`text-2xl ${isActive ? 'animate-pulse' : ''}`}>
                {phase.icon}
              </div>
              <div>
                <h3 className="text-lg font-semibold">{phase.label}</h3>
                {hasTools && (
                  <p className="text-xs text-slate-400">
                    {tools.length} tool{tools.length !== 1 ? 's' : ''}
                  </p>
                )}
              </div>
              {isActive && isConnected && (
                <span className="ml-auto flex items-center gap-1 text-xs bg-blue-500/20 px-2 py-1 rounded">
                  <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
                  In Progress
                </span>
              )}
              {isCompleted && (
                <span className="ml-auto text-xs text-emerald-400">
                  ✓ Complete
                </span>
              )}
            </div>

            {/* Tool Cards */}
            {hasTools ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 ml-8">
                {tools.map((toolState) => (
                  <ToolCard key={`${toolState.phase}:${toolState.tool}`} toolState={toolState} />
                ))}
              </div>
            ) : (
              <div className="ml-8 text-slate-600 text-sm">
                {index === 0 ? 'Initializing...' : 'No tools configured for this phase'}
              </div>
            )}

            {/* Connector Line */}
            {index < PHASES.length - 1 && (
              <div className={`ml-6 w-0.5 h-6 my-2 ${
                isCompleted ? 'bg-emerald-400/30' : 'bg-slate-700'
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ToolCard({ toolState }: { toolState: ScanToolState }) {
  const displayName = TOOL_DISPLAY_NAMES[toolState.tool] || toolState.tool.toUpperCase();
  const stageIcon = STAGE_ICONS[toolState.stage] || '•';
  const stageColor = STAGE_COLORS[toolState.stage] || 'text-slate-400';
  const isRunning = toolState.stage === 'running';
  const isCompleted = toolState.stage === 'completed' || toolState.stage === 'timed_out';
  const isFailed = toolState.stage === 'failed';

  return (
    <div className={`relative p-3 rounded-lg border transition-all ${
      isRunning 
        ? 'bg-blue-500/5 border-blue-500/30' 
        : isCompleted 
        ? 'bg-emerald-500/5 border-emerald-500/30'
        : isFailed
        ? 'bg-red-500/5 border-red-500/30'
        : 'bg-slate-800/30 border-slate-700'
    }`}>
      {/* Tool Name */}
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-sm">{displayName}</h4>
        <span className={`text-lg ${stageColor} ${isRunning ? 'animate-pulse' : ''}`}>
          {stageIcon}
        </span>
      </div>

      {/* Progress Bar */}
      {typeof toolState.progress === 'number' && toolState.progress >= 0 && toolState.progress <= 100 && (
        <div className="mb-2">
          <div className="w-full bg-slate-700 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all ${
                isCompleted ? 'bg-emerald-400' : isRunning ? 'bg-blue-400' : 'bg-slate-500'
              }`}
              style={{ width: `${toolState.progress}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-1">{Math.round(toolState.progress)}%</p>
        </div>
      )}

      {/* Message */}
      {toolState.last_message && (
        <p className="text-xs text-slate-400 mb-2 line-clamp-2">
          {toolState.last_message}
        </p>
      )}

      {/* Meta Chips */}
      {toolState.meta && Object.keys(toolState.meta).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(toolState.meta).slice(0, 3).map(([key, value]) => (
            <span
              key={key}
              className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-slate-700/50 text-slate-300"
            >
              {key}: {typeof value === 'object' ? JSON.stringify(value).slice(0, 20) : String(value).slice(0, 20)}
            </span>
          ))}
        </div>
      )}

      {/* Stage Label */}
      <div className={`mt-2 text-xs font-medium ${stageColor}`}>
        {toolState.stage.charAt(0).toUpperCase() + toolState.stage.slice(1)}
      </div>
    </div>
  );
}

