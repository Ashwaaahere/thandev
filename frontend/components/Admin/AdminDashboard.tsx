'use client';

import { useEffect, useState } from 'react';
import { Session } from 'next-auth';
import { thandevFetchJSON } from '@/lib/thandevApi';

type UserSummary = {
  id: string;
  email: string;
  username: string;
  is_admin: boolean;
  is_approved: boolean;
  tenant_id?: string | null;
};

type TenantSummary = {
  id: string;
  name: string;
  plan: string;
};

type EntitlementRequest = {
  tenant_id: string;
  plan_name: string;
  limits_json: Record<string, any>;
  user_scoped: boolean;
};

type EntitlementResponse = {
  id: string;
  tenant_id: string;
  user_id?: string | null;
  plan_name: string;
  limits_json?: Record<string, any> | null;
};

type AllowedDomain = {
  id: string;
  domain: string;
  scope: string;
  tenant_id?: string | null;
  enabled: boolean;
  notes?: string | null;
  created_by_admin_id?: string | null;
  created_at: string;
  updated_at: string;
};

type AllowedDomainRequest = {
  domain: string;
  scope: string;
  tenant_id?: string;
  enabled: boolean;
  notes?: string;
};

interface Props {
  session: Session;
}

export default function AdminDashboard({ session }: Props) {
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [tenants, setTenants] = useState<TenantSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [entitlementForm, setEntitlementForm] = useState<EntitlementRequest>({
    tenant_id: '',
    plan_name: 'pro',
    limits_json: {
      allowed_scan_levels: ['basic', 'pro'],
      max_scans_per_day: 10,
      max_concurrent_scans: 2,
    },
    user_scoped: true,
  });
  const [entitlementUserId, setEntitlementUserId] = useState<string>('');
  const [savingEntitlement, setSavingEntitlement] = useState(false);
  const [allowedDomains, setAllowedDomains] = useState<AllowedDomain[]>([]);
  const [allowedForm, setAllowedForm] = useState<AllowedDomainRequest>({
    domain: '',
    scope: 'global',
    tenant_id: '',
    enabled: true,
    notes: '',
  });
  const [savingAllowed, setSavingAllowed] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [usersData, tenantsData] = await Promise.all([
        thandevFetchJSON<UserSummary[]>('/api/admin/users', session),
        thandevFetchJSON<TenantSummary[]>('/api/admin/tenants', session),
      ]);
      setUsers(usersData);
      setTenants(tenantsData);
      if (!entitlementForm.tenant_id && tenantsData.length > 0) {
        setEntitlementForm((prev) => ({ ...prev, tenant_id: tenantsData[0].id }));
      }

      // Allowed domains fetch is best-effort; don't block page if it fails
      try {
        const allowData = await thandevFetchJSON<AllowedDomain[]>('/api/admin/allowed-domains', session);
        setAllowedDomains(allowData);
      } catch (err) {
        console.warn('Allowed domains fetch failed', err);
        setAllowedDomains([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const approveUser = async (userId: string) => {
    try {
      await thandevFetchJSON(`/api/admin/users/${userId}/approve`, session, {
        method: 'POST',
      });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_approved: true } : u))
      );
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to approve user');
    }
  };

  const saveEntitlement = async () => {
    if (!entitlementUserId) {
      alert('Select a user to assign an entitlement');
      return;
    }
    setSavingEntitlement(true);
    try {
      const payload = {
        ...entitlementForm,
        limits_json: entitlementForm.limits_json,
        user_scoped: true,
      };
      const res = await thandevFetchJSON<EntitlementResponse>(
        `/api/admin/users/${entitlementUserId}/entitlement`,
        session,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );
      alert(`Entitlement saved: ${res.plan_name}`);
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Failed to save entitlement');
    } finally {
      setSavingEntitlement(false);
    }
  };

  const saveAllowedDomain = async () => {
    if (!allowedForm.domain.trim()) {
      alert('Enter a domain');
      return;
    }
    setSavingAllowed(true);
    try {
      const payload = {
        domain: allowedForm.domain.trim().toLowerCase(),
        scope: allowedForm.scope,
        tenant_id: allowedForm.scope === 'tenant' ? allowedForm.tenant_id || undefined : undefined,
        enabled: allowedForm.enabled,
        notes: allowedForm.notes,
      };
      const created = await thandevFetchJSON<AllowedDomain>(
        '/api/admin/allowed-domains',
        session,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );
      setAllowedDomains((prev) => [created, ...prev]);
      setAllowedForm({
        domain: '',
        scope: 'global',
        tenant_id: '',
        enabled: true,
        notes: '',
      });
    } catch (e: any) {
      alert(e?.message || 'Failed to save allowed domain');
    } finally {
      setSavingAllowed(false);
    }
  };

  const deleteAllowedDomain = async (id: string) => {
    if (!confirm('Delete this allowed domain?')) return;
    try {
      await thandevFetchJSON(`/api/admin/allowed-domains/${id}`, session, {
        method: 'DELETE',
      });
      setAllowedDomains((prev) => prev.filter((d) => d.id !== id));
    } catch (e: any) {
      alert(e?.message || 'Failed to delete allowed domain');
    }
  };

  if (loading) {
    return (
      <div className="p-6">
        <p className="text-sm text-slate-300">Loading admin data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <p className="text-sm text-red-300">{error}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="max-w-6xl mx-auto py-8 px-4 space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">Admin</p>
            <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
          </div>
          <button
            onClick={loadData}
            className="px-3 py-2 text-sm rounded-lg bg-slate-800 border border-slate-700 hover:border-slate-500"
          >
            Refresh
          </button>
        </div>

        {/* Users table */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Users</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-400">
                <tr>
                  <th className="py-2 pr-3">Email</th>
                  <th className="py-2 pr-3">Username</th>
                  <th className="py-2 pr-3">Admin</th>
                  <th className="py-2 pr-3">Approved</th>
                  <th className="py-2 pr-3">Tenant</th>
                  <th className="py-2 pr-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="py-2 pr-3 font-mono text-slate-200">{u.email}</td>
                    <td className="py-2 pr-3 text-slate-200">{u.username}</td>
                    <td className="py-2 pr-3">{u.is_admin ? 'Yes' : 'No'}</td>
                    <td className="py-2 pr-3">{u.is_approved ? 'Yes' : 'No'}</td>
                    <td className="py-2 pr-3 text-xs text-slate-400">{u.tenant_id || '–'}</td>
                    <td className="py-2 pr-3 space-x-2">
                      {!u.is_approved && (
                        <button
                          onClick={() => approveUser(u.id)}
                          className="px-2 py-1 text-xs rounded bg-emerald-700 hover:bg-emerald-600"
                        >
                          Approve
                        </button>
                      )}
                      <button
                        onClick={() => setEntitlementUserId(u.id)}
                        className={`px-2 py-1 text-xs rounded border ${
                          entitlementUserId === u.id
                            ? 'border-indigo-400 text-indigo-200'
                            : 'border-slate-700 text-slate-200'
                        }`}
                      >
                        Select for entitlement
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Entitlement form */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
          <h2 className="text-lg font-semibold">Assign Plan / Limits</h2>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="text-sm text-slate-300">
              Tenant
              <select
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm"
                value={entitlementForm.tenant_id}
                onChange={(e) =>
                  setEntitlementForm((prev) => ({ ...prev, tenant_id: e.target.value }))
                }
              >
                <option value="">Select tenant</option>
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.plan})
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm text-slate-300">
              Plan name
              <input
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm"
                value={entitlementForm.plan_name}
                onChange={(e) =>
                  setEntitlementForm((prev) => ({ ...prev, plan_name: e.target.value }))
                }
              />
            </label>
          </div>
          <label className="text-sm text-slate-300 block">
            Limits JSON
            <textarea
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm font-mono"
              rows={5}
              value={JSON.stringify(entitlementForm.limits_json, null, 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  setEntitlementForm((prev) => ({ ...prev, limits_json: parsed }));
                  setError(null);
                } catch (err) {
                  setError('Invalid JSON in limits');
                }
              }}
            />
          </label>
          <div className="flex items-center gap-2">
            <button
              onClick={saveEntitlement}
              disabled={savingEntitlement || !entitlementUserId || !entitlementForm.tenant_id}
              className="px-4 py-2 text-sm rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50"
            >
              {savingEntitlement ? 'Saving...' : 'Save entitlement'}
            </button>
            <p className="text-xs text-slate-400">
              Selected user: {entitlementUserId || 'none'}
            </p>
          </div>
        </div>

        {/* Allowed domains management */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 space-y-3">
          <h2 className="text-lg font-semibold">Allowed Domains</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm text-slate-300">
              Domain
              <input
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm"
                value={allowedForm.domain}
                onChange={(e) => setAllowedForm((prev) => ({ ...prev, domain: e.target.value }))}
                placeholder="example.com"
              />
            </label>
            <label className="text-sm text-slate-300">
              Scope
              <select
                className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm"
                value={allowedForm.scope}
                onChange={(e) => setAllowedForm((prev) => ({ ...prev, scope: e.target.value }))}
              >
                <option value="global">Global</option>
                <option value="tenant">Tenant</option>
              </select>
            </label>
            {allowedForm.scope === 'tenant' && (
              <label className="text-sm text-slate-300">
                Tenant
                <select
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm"
                  value={allowedForm.tenant_id}
                  onChange={(e) => setAllowedForm((prev) => ({ ...prev, tenant_id: e.target.value }))}
                >
                  <option value="">Select tenant</option>
                  {tenants.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <label className="text-sm text-slate-300 block">
            Notes
            <input
              className="mt-1 w-full rounded border border-slate-700 bg-slate-950 p-2 text-sm"
              value={allowedForm.notes}
              onChange={(e) => setAllowedForm((prev) => ({ ...prev, notes: e.target.value }))}
              placeholder="Training targets, demo, etc."
            />
          </label>
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-300 flex items-center gap-2">
              <input
                type="checkbox"
                checked={allowedForm.enabled}
                onChange={(e) => setAllowedForm((prev) => ({ ...prev, enabled: e.target.checked }))}
              />
              Enabled
            </label>
            <button
              onClick={saveAllowedDomain}
              disabled={savingAllowed}
              className="px-4 py-2 text-sm rounded bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50"
            >
              {savingAllowed ? 'Saving...' : 'Save allowed domain'}
            </button>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-400">
                <tr>
                  <th className="py-2 pr-3">Domain</th>
                  <th className="py-2 pr-3">Scope</th>
                  <th className="py-2 pr-3">Tenant</th>
                  <th className="py-2 pr-3">Enabled</th>
                  <th className="py-2 pr-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {allowedDomains.map((d) => (
                  <tr key={d.id}>
                    <td className="py-2 pr-3 font-mono text-slate-200">{d.domain}</td>
                    <td className="py-2 pr-3 text-slate-200">{d.scope}</td>
                    <td className="py-2 pr-3 text-xs text-slate-400">{d.tenant_id || '–'}</td>
                    <td className="py-2 pr-3">{d.enabled ? 'Yes' : 'No'}</td>
                    <td className="py-2 pr-3">
                      <button
                        onClick={() => deleteAllowedDomain(d.id)}
                        className="px-2 py-1 text-xs rounded border border-red-500 text-red-300 hover:bg-red-500/10"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
                {allowedDomains.length === 0 && (
                  <tr>
                    <td className="py-2 pr-3 text-slate-400 text-sm" colSpan={5}>
                      No allowed domains yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

