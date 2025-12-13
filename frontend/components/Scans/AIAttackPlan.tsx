'use client';

/**
 * AI Attack Plan Component
 * 
 * Displays the AI-generated attack plan for a scan, including suggested tools
 * and attack paths.
 */

type AIAttackPlanProps = {
  aiStatus?: "idle" | "planned" | "failed" | null;
  aiPlan?: {
    next_tools?: { key: string; reason?: string; priority?: string }[];
    attack_paths?: {
      goal: string;
      steps?: string[];
    }[];
  } | null;
};

export default function AIAttackPlan({ aiStatus, aiPlan }: AIAttackPlanProps) {
  // Safely parse and validate aiPlan structure
  const safeParseAIPlan = (plan: unknown): AIAttackPlanProps['aiPlan'] => {
    if (!plan || typeof plan !== 'object') {
      return null;
    }

    const planObj = plan as Record<string, unknown>;
    const result: AIAttackPlanProps['aiPlan'] = {
      next_tools: [],
      attack_paths: [],
    };

    // Parse next_tools
    if (Array.isArray(planObj.next_tools)) {
      result.next_tools = planObj.next_tools
        .filter((tool): tool is { key: string; reason?: string; priority?: string } => {
          return typeof tool === 'object' && tool !== null && 'key' in tool && typeof tool.key === 'string';
        })
        .map((tool) => ({
          key: tool.key,
          reason: typeof tool.reason === 'string' ? tool.reason : undefined,
          priority: typeof tool.priority === 'string' ? tool.priority : undefined,
        }));
    }

    // Parse attack_paths
    if (Array.isArray(planObj.attack_paths)) {
      result.attack_paths = planObj.attack_paths
        .filter((path): path is { goal: string; steps?: string[] } => {
          return typeof path === 'object' && path !== null && 'goal' in path && typeof path.goal === 'string';
        })
        .map((path) => ({
          goal: path.goal,
          steps: Array.isArray(path.steps) 
            ? path.steps.filter((step): step is string => typeof step === 'string')
            : undefined,
        }));
    }

    return result;
  };

  const parsedPlan = aiPlan ? safeParseAIPlan(aiPlan) : null;
  const nextTools = parsedPlan?.next_tools || [];
  const attackPaths = parsedPlan?.attack_paths || [];

  // Handle idle or missing status
  if (aiStatus === "idle" || aiStatus === null || !parsedPlan) {
    return (
      <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>AI Attack Plan</h2>
        <div className="text-center py-6">
          <div className="w-10 h-10 mx-auto mb-2 rounded-full flex items-center justify-center" style={{ background: 'var(--surface-2)', opacity: 0.5 }}>
            <svg className="w-5 h-5" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
          </div>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            AI planner did not run for this scan yet.
          </p>
        </div>
      </div>
    );
  }

  // Handle failed status
  if (aiStatus === "failed") {
    return (
      <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>AI Attack Plan</h2>
        <div className="rounded-lg border p-4" style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}>
          <div className="flex items-start gap-2">
            <svg className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <div>
              <p className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>AI Planner Failed</p>
              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                The AI planner failed on this scan. Base tool results are still valid.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Handle planned status
  if (aiStatus === "planned") {
    const hasNextTools = nextTools.length > 0;
    const hasAttackPaths = attackPaths.length > 0;

    return (
      <div className="rounded-2xl border shadow-lg p-6" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--fg)' }}>AI Attack Plan</h2>
        
        <div className="space-y-6">
          {/* Suggested Tools Section */}
          <div>
            <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--fg)' }}>Suggested Tools</h3>
            {!hasNextTools ? (
              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                The AI planner did not recommend additional tools based on the current findings.
              </p>
            ) : (
              <div className="space-y-3">
                {nextTools.map((tool, idx) => {
                  const priority = tool.priority?.toLowerCase() || 'medium';
                  const priorityColors = {
                    high: 'bg-red-900/40 text-red-200 border-red-500/50',
                    medium: 'bg-yellow-900/40 text-yellow-200 border-yellow-500/50',
                    low: 'bg-blue-900/40 text-blue-200 border-blue-500/50',
                  };
                  const priorityColor = priorityColors[priority as keyof typeof priorityColors] || priorityColors.medium;

                  return (
                    <div
                      key={`tool-${tool.key}-${idx}`}
                      className="rounded-lg border p-3"
                      style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium border bg-slate-800/40 text-slate-200 border-slate-600/50">
                          {tool.key}
                        </span>
                        {tool.priority && (
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium border ${priorityColor}`}>
                            {tool.priority.charAt(0).toUpperCase() + tool.priority.slice(1)}
                          </span>
                        )}
                      </div>
                      {tool.reason && (
                        <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>
                          {tool.reason}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Attack Paths Section */}
          {hasAttackPaths && (
            <div>
              <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--fg)' }}>Attack Paths</h3>
              <div className="space-y-3">
                {attackPaths.map((path, idx) => (
                  <div
                    key={`path-${idx}`}
                    className="rounded-lg border p-3"
                    style={{ background: 'var(--surface-2)', borderColor: 'var(--border)' }}
                  >
                    <p className="text-xs font-semibold mb-2" style={{ color: 'var(--fg)' }}>
                      {path.goal}
                    </p>
                    {path.steps && path.steps.length > 0 && (
                      <ol className="list-decimal list-inside space-y-1 text-xs" style={{ color: 'var(--muted)' }}>
                        {path.steps.map((step, stepIdx) => (
                          <li key={`step-${idx}-${stepIdx}`}>{step}</li>
                        ))}
                      </ol>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Fallback (should not reach here)
  return null;
}






