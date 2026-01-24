'use client';

import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { thandevFetchJSON } from '@/lib/thandevApi';

type CWEResponse = {
  id: number;
  title: string | null;
  summary: string | null;
  why_it_matters: string | null;
  common_impacts: string[] | null;
  basic_mitigations: string[] | null;
  links: {
    mitre: string;
    nvd_search: string;
  };
};

interface CWEDrawerProps {
  cweId: string;
  open: boolean;
  onClose: () => void;
}

export default function CWEDrawer({ cweId, open, onClose }: CWEDrawerProps) {
  const { data: session } = useSession();
  const [cweData, setCweData] = useState<CWEResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Extract numeric CWE ID (handle "CWE-1021" or "1021")
  const cweIdClean = cweId.replace(/^CWE-/i, '');

  useEffect(() => {
    if (open && cweIdClean) {
      setLoading(true);
      setError(null);
      
      // CWE reference endpoint is public, but we'll try with session if available
      // If session fails, fall back to unauthenticated request
      const fetchCWE = async () => {
        try {
          if (session) {
            // Try with authenticated request first
            const data = await thandevFetchJSON<CWEResponse>(`/api/reference/cwe/${cweIdClean}`, session);
            setCweData(data);
          } else {
            // Fallback to unauthenticated fetch
            const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
            const response = await fetch(`${API_BASE}/api/reference/cwe/${cweIdClean}`);
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            setCweData(data);
          }
        } catch (err) {
          console.error('Failed to load CWE data', err);
          // Try unauthenticated as fallback
          try {
            const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
            const response = await fetch(`${API_BASE}/api/reference/cwe/${cweIdClean}`);
            if (response.ok) {
              const data = await response.json();
              setCweData(data);
            } else {
              setError('Failed to load CWE information');
            }
          } catch (fallbackErr) {
            setError('Failed to load CWE information');
          }
        } finally {
          setLoading(false);
        }
      };
      
      fetchCWE();
    } else if (!open) {
      setCweData(null);
      setError(null);
    }
  }, [open, cweIdClean, session]);

  // Handle Esc key to close
  useEffect(() => {
    if (!open) return;
    
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 z-50 transition-opacity"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div
        className="fixed top-0 right-0 h-full w-full max-w-lg z-[60] transform transition-transform duration-300 ease-in-out translate-x-0"
        style={{ background: 'var(--bg)' }}
      >
        <div className="h-full flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b" style={{ borderColor: 'var(--border)' }}>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
                CWE-{cweIdClean}
              </h2>
              {cweData?.title && (
                <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
                  {cweData.title}
                </p>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded hover:bg-opacity-20 transition-colors"
              style={{ background: 'var(--surface-2)' }}
              aria-label="Close"
            >
              <svg className="w-5 h-5" style={{ color: 'var(--fg)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {loading ? (
              <div className="text-center py-8" style={{ color: 'var(--muted)' }}>
                Loading CWE information...
              </div>
            ) : error ? (
              <div className="text-center py-8" style={{ color: 'var(--muted)' }}>
                {error}
              </div>
            ) : cweData ? (
              <>
                {!cweData.title && !cweData.summary ? (
                  <div className="text-sm p-4 rounded" style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                    No local details available for this CWE yet. Use the links below to view external resources.
                  </div>
                ) : (
                  <>
                    {/* Summary */}
                    {cweData.summary && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>About this weakness</h3>
                        <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                          {cweData.summary}
                        </p>
                      </div>
                    )}

                    {/* Why it matters */}
                    {cweData.why_it_matters && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Why it matters</h3>
                        <p className="text-sm leading-relaxed" style={{ color: 'var(--muted)' }}>
                          {cweData.why_it_matters}
                        </p>
                      </div>
                    )}

                    {/* Common impacts */}
                    {cweData.common_impacts && cweData.common_impacts.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Common impacts</h3>
                        <ul className="text-sm list-disc list-inside space-y-1" style={{ color: 'var(--muted)' }}>
                          {cweData.common_impacts.map((impact, idx) => (
                            <li key={idx}>{impact}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Basic mitigations */}
                    {cweData.basic_mitigations && cweData.basic_mitigations.length > 0 && (
                      <div>
                        <h3 className="text-sm font-semibold mb-2" style={{ color: 'var(--fg)' }}>Basic mitigations</h3>
                        <ul className="text-sm list-disc list-inside space-y-1" style={{ color: 'var(--muted)' }}>
                          {cweData.basic_mitigations.map((mitigation, idx) => (
                            <li key={idx}>{mitigation}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                )}

                {/* External links */}
                <div>
                  <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--fg)' }}>External resources</h3>
                  <div className="flex flex-col gap-2">
                    <a
                      href={cweData.links.mitre}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 rounded text-sm font-medium text-center transition-colors"
                      style={{ 
                        background: 'var(--brand)', 
                        color: 'white',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.opacity = '0.9';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.opacity = '1';
                      }}
                    >
                      View on MITRE CWE
                    </a>
                    <a
                      href={cweData.links.nvd_search}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-4 py-2 rounded text-sm font-medium text-center border transition-colors"
                      style={{ 
                        borderColor: 'var(--border)', 
                        color: 'var(--fg)',
                        background: 'var(--surface-2)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'var(--surface-3)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'var(--surface-2)';
                      }}
                    >
                      Related CVEs (NVD Search)
                    </a>
                  </div>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </>
  );
}

