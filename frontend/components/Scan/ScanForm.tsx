'use client';

import { useState } from 'react';

interface ScanFormProps {
  onScan: (url: string, scanType: string) => void;
  loading: boolean;
}

export default function ScanForm({ onScan, loading }: ScanFormProps) {
  const [url, setUrl] = useState('');
  const [scanType, setScanType] = useState('comprehensive');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    
    // Basic URL validation
    let targetUrl = url.trim();
    if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://')) {
      targetUrl = 'https://' + targetUrl;
    }
    
    onScan(targetUrl, scanType);
  };

  const scanTypes = [
    { value: 'quick', label: 'Quick Scan', description: 'Basic security checks (1-2 min)' },
    { value: 'comprehensive', label: 'Comprehensive Scan', description: 'Full vulnerability assessment (3-5 min)' },
    { value: 'deep', label: 'Deep Scan', description: 'Thorough analysis including subdomains (5-10 min)' }
  ];

  return (
    <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-8 shadow-lg">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
      
      <div className="relative z-10">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-[var(--fg)] mb-2">Start Security Scan</h2>
          <p className="text-[var(--muted)]">Enter a website URL to perform a comprehensive security assessment</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* URL Input */}
          <div>
            <label htmlFor="url" className="block text-sm font-medium text-[var(--fg)] mb-2">
              Website URL
            </label>
            <div className="relative">
              <input
                type="url"
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full px-4 py-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-[var(--fg)] placeholder-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                disabled={loading}
                required
              />
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                <div className="h-5 w-5 text-[var(--muted)]">
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9v-9m0-9v9" />
                  </svg>
                </div>
              </div>
            </div>
          </div>

          {/* Scan Type Selection */}
          <div>
            <label className="block text-sm font-medium text-[var(--fg)] mb-3">
              Scan Type
            </label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {scanTypes.map((type) => (
                <label
                  key={type.value}
                  className={`relative flex flex-col p-4 rounded-lg border cursor-pointer transition-all duration-200 ${
                    scanType === type.value
                      ? 'border-blue-500 bg-blue-500/10'
                      : 'border-[var(--border)] hover:border-blue-300 hover:bg-blue-500/5'
                  }`}
                >
                  <input
                    type="radio"
                    name="scanType"
                    value={type.value}
                    checked={scanType === type.value}
                    onChange={(e) => setScanType(e.target.value)}
                    className="sr-only"
                    disabled={loading}
                  />
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`h-4 w-4 rounded-full border-2 ${
                      scanType === type.value ? 'border-blue-500 bg-blue-500' : 'border-[var(--muted)]'
                    }`}>
                      {scanType === type.value && (
                        <div className="h-2 w-2 bg-white rounded-full m-0.5"></div>
                      )}
                    </div>
                    <span className="font-medium text-[var(--fg)]">{type.label}</span>
                  </div>
                  <p className="text-sm text-[var(--muted)] ml-7">{type.description}</p>
                </label>
              ))}
            </div>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={loading || !url.trim()}
            className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-semibold rounded-lg hover:from-blue-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                <span>Scanning...</span>
              </>
            ) : (
              <>
                <div className="h-5 w-5">
                  <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span>Start Security Scan</span>
              </>
            )}
          </button>
        </form>

        {/* Security Notice */}
        <div className="mt-6 p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
          <div className="flex items-start gap-3">
            <div className="h-5 w-5 text-yellow-500 mt-0.5">
              <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <div>
              <h4 className="font-medium text-yellow-700 dark:text-yellow-300 mb-1">Security Notice</h4>
              <p className="text-sm text-yellow-600 dark:text-yellow-400">
                Only scan websites you own or have explicit permission to test. Unauthorized scanning may violate terms of service and local laws.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
