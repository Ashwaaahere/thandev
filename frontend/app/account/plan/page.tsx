'use client';

/**
 * Plan Management Page
 * 
 * Allows users to view their current plan and switch between plans.
 * For development/admin use - no authentication required.
 */

import { useState, useEffect } from 'react';

// API base URL configuration
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

// Plan types (same as scans page)
type TenantPlanUsage = {
  projects_count: number;
  projects_max: number;
  scans_this_month: number;
  scans_monthly_max: number;
  concurrent_scans: number;
  concurrent_scans_max: number;
};

type PlanLimits = {
  max_projects: number;
  max_scans_per_month: number;
  max_concurrent_scans: number;
  allowed_scan_levels: string[];
};

type TenantPlanInfo = {
  id: string;
  name: string;
  plan: string; // "free" | "individual" | "team"
  limits: PlanLimits;
  usage: TenantPlanUsage;
};

type PlanTier = 'free' | 'individual' | 'team';

const PLAN_DESCRIPTIONS: Record<PlanTier, { name: string; description: string; features: string[] }> = {
  free: {
    name: 'Free',
    description: 'Perfect for getting started with basic security scanning',
    features: [
      '1 project',
      '20 scans per month',
      '1 concurrent scan',
      'Basic scan level only',
    ],
  },
  individual: {
    name: 'Individual',
    description: 'For solo developers and small projects',
    features: [
      '5 projects',
      '200 scans per month',
      '2 concurrent scans',
      'Basic + Pro scan levels',
    ],
  },
  team: {
    name: 'Team',
    description: 'For teams and organizations',
    features: [
      '20 projects',
      '2000 scans per month',
      '5 concurrent scans',
      'Basic + Pro + Advanced scan levels',
    ],
  },
};

export default function PlanPage() {
  const [planInfo, setPlanInfo] = useState<TenantPlanInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [switching, setSwitching] = useState<string | null>(null);

  // Fetch plan info
  useEffect(() => {
    async function loadPlan() {
      try {
        const res = await fetch(`${API_BASE}/api/tenants/current`);
        if (!res.ok) {
          throw new Error(`Failed to fetch plan info: ${res.status}`);
        }
        const data = await res.json();
        setPlanInfo(data);
      } catch (err) {
        console.error("Error fetching tenant plan info", err);
        setError(err instanceof Error ? err.message : 'Failed to load plan info');
      } finally {
        setLoading(false);
      }
    }

    loadPlan();
  }, []);

  // Switch plan
  const switchPlan = async (targetPlan: PlanTier) => {
    if (!planInfo || switching) return;

    setSwitching(targetPlan);
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE}/api/tenants/${planInfo.id}/change_plan?new_plan=${targetPlan}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`Failed to switch plan: ${text || res.status}`);
      }

      // Re-fetch plan info
      const planRes = await fetch(`${API_BASE}/api/tenants/current`);
      if (planRes.ok) {
        const data = await planRes.json();
        setPlanInfo(data);
      }
    } catch (err) {
      console.error('Error switching plan', err);
      setError(err instanceof Error ? err.message : 'Failed to switch plan');
    } finally {
      setSwitching(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading plan information...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error && !planInfo) {
    return (
      <div className="min-h-screen bg-gray-50 p-6">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  const currentPlan = planInfo?.plan as PlanTier;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Plan Management</h1>
          <p className="text-gray-600">View and manage your subscription plan</p>
        </div>

        {/* Current Plan Usage */}
        {planInfo && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Current Plan Usage</h2>
            <div className="text-sm text-slate-600 flex flex-wrap gap-2 items-center">
              <span className="font-semibold">
                Plan: {planInfo.plan.charAt(0).toUpperCase() + planInfo.plan.slice(1)}
              </span>
              <span>·</span>
              <span>Projects {planInfo.usage.projects_count}/{planInfo.usage.projects_max}</span>
              <span>·</span>
              <span>Scans this month {planInfo.usage.scans_this_month}/{planInfo.usage.scans_monthly_max}</span>
              <span>·</span>
              <span>Concurrent {planInfo.usage.concurrent_scans}/{planInfo.usage.concurrent_scans_max}</span>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 text-red-700 px-4 py-3">
            {error}
          </div>
        )}

        {/* Plan Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {(Object.keys(PLAN_DESCRIPTIONS) as PlanTier[]).map((planTier) => {
            const planDesc = PLAN_DESCRIPTIONS[planTier];
            const isCurrent = currentPlan === planTier;
            const isSwitching = switching === planTier;

            return (
              <div
                key={planTier}
                className={`bg-white rounded-lg shadow-sm border-2 p-6 ${
                  isCurrent
                    ? 'border-blue-500 ring-2 ring-blue-200'
                    : 'border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xl font-bold text-gray-900">{planDesc.name}</h3>
                  {isCurrent && (
                    <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                      Current
                    </span>
                  )}
                </div>

                <p className="text-gray-600 mb-4 text-sm">{planDesc.description}</p>

                <ul className="space-y-2 mb-6">
                  {planDesc.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start">
                      <svg
                        className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                      <span className="text-sm text-gray-700">{feature}</span>
                    </li>
                  ))}
                </ul>

                {!isCurrent && (
                  <button
                    onClick={() => switchPlan(planTier)}
                    disabled={isSwitching || !!switching}
                    className={`w-full px-4 py-2 rounded-lg font-medium transition-colors ${
                      isSwitching || switching
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    }`}
                  >
                    {isSwitching ? (
                      <span className="flex items-center justify-center gap-2">
                        <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                        Switching...
                      </span>
                    ) : (
                      `Switch to ${planDesc.name}`
                    )}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}



