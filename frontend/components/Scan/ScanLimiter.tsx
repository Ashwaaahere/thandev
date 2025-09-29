'use client';

import { useState, useEffect } from 'react';

interface ScanLimiterProps {
  children: React.ReactNode;
  onLimitReached: () => void;
}

interface DeviceFingerprint {
  userAgent: string;
  language: string;
  platform: string;
  screenResolution: string;
  timezone: string;
  cookieEnabled: boolean;
  doNotTrack: string | null;
  hardwareConcurrency: number;
  deviceMemory: number | undefined;
}

export default function ScanLimiter({ children, onLimitReached }: ScanLimiterProps) {
  const [isAllowed, setIsAllowed] = useState<boolean | null>(null);
  const [deviceId, setDeviceId] = useState<string>('');
  const [scansUsed, setScansUsed] = useState(0);

  useEffect(() => {
    checkScanLimit();
  }, []);

  const generateDeviceFingerprint = (): DeviceFingerprint => {
    return {
      userAgent: navigator.userAgent,
      language: navigator.language,
      platform: navigator.platform,
      screenResolution: `${screen.width}x${screen.height}`,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      cookieEnabled: navigator.cookieEnabled,
      doNotTrack: navigator.doNotTrack,
      hardwareConcurrency: navigator.hardwareConcurrency,
      deviceMemory: (navigator as any).deviceMemory
    };
  };

  const generateDeviceId = (fingerprint: DeviceFingerprint): string => {
    // Create a hash-like identifier from device characteristics
    const fingerprintString = JSON.stringify(fingerprint);
    
    // Simple hash function (in production, use a proper crypto hash)
    let hash = 0;
    for (let i = 0; i < fingerprintString.length; i++) {
      const char = fingerprintString.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    
    return Math.abs(hash).toString(36);
  };

  const checkScanLimit = () => {
    try {
      // Check if user is authenticated first
      const userData = localStorage.getItem('thandev-user');
      if (userData) {
        // User is authenticated, allow unlimited scans
        setIsAllowed(true);
        return;
      }

      const fingerprint = generateDeviceFingerprint();
      const currentDeviceId = generateDeviceId(fingerprint);
      setDeviceId(currentDeviceId);

      // Check if this device has already used its free scan
      const scanData = localStorage.getItem('thandev-scan-limit');
      const parsedData = scanData ? JSON.parse(scanData) : null;

      if (parsedData && parsedData.deviceId === currentDeviceId) {
        // Device has been used before
        const scansUsed = parsedData.scansUsed || 0;
        setScansUsed(scansUsed);
        
        if (scansUsed >= 1) {
          // Free scan limit reached
          setIsAllowed(false);
          onLimitReached();
          return;
        }
      }

      // Device can scan (first time or within limit)
      setIsAllowed(true);
    } catch (error) {
      console.error('Error checking scan limit:', error);
      // On error, allow scan (fail open)
      setIsAllowed(true);
    }
  };

  const recordScan = () => {
    try {
      // Check if user is authenticated first
      const userData = localStorage.getItem('thandev-user');
      if (userData) {
        // User is authenticated, no need to record scan limit
        return;
      }

      const scanData = {
        deviceId,
        scansUsed: scansUsed + 1,
        lastScan: new Date().toISOString(),
        fingerprint: generateDeviceFingerprint()
      };
      
      localStorage.setItem('thandev-scan-limit', JSON.stringify(scanData));
      setScansUsed(scansUsed + 1);
      
      // If this was the free scan, trigger limit reached
      if (scansUsed + 1 >= 1) {
        setTimeout(() => {
          setIsAllowed(false);
          onLimitReached();
        }, 1000); // Allow scan to complete first
      }
    } catch (error) {
      console.error('Error recording scan:', error);
    }
  };

  if (isAllowed === null) {
    // Loading state
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <span className="ml-3 text-[var(--muted)]">Checking scan availability...</span>
      </div>
    );
  }

  if (!isAllowed) {
    // Limit reached - show upgrade prompt
    return (
      <div className="space-y-6">
        {/* Limit Reached Message */}
        <div className="relative overflow-hidden rounded-2xl border border-orange-200/50 bg-gradient-to-br from-orange-50/50 to-orange-100/30 p-8 backdrop-blur-sm dark:border-orange-800/50 dark:from-orange-950/40 dark:to-orange-900/20">
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-transparent" />
          <div className="relative z-10 text-center">
            <div className="mb-6">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-orange-500/20 to-orange-600/20 flex items-center justify-center">
                <div className="text-2xl">🔒</div>
              </div>
              <h2 className="text-2xl font-bold text-orange-800 dark:text-orange-200 mb-2">
                Free Scan Limit Reached
              </h2>
              <p className="text-orange-600 dark:text-orange-300 mb-4">
                You've used your free security scan. Create an account to continue scanning unlimited websites.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
              <div className="text-left">
                <h3 className="font-semibold text-orange-800 dark:text-orange-200 mb-2">Free Account Includes:</h3>
                <ul className="text-sm text-orange-600 dark:text-orange-300 space-y-1">
                  <li>• Unlimited security scans</li>
                  <li>• Detailed vulnerability reports</li>
                  <li>• Scan history tracking</li>
                  <li>• Email notifications</li>
                </ul>
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-orange-800 dark:text-orange-200 mb-2">Pro Features:</h3>
                <ul className="text-sm text-orange-600 dark:text-orange-300 space-y-1">
                  <li>• Advanced vulnerability detection</li>
                  <li>• API access for automation</li>
                  <li>• Priority support</li>
                  <li>• Custom scan schedules</li>
                </ul>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <button
                onClick={() => window.location.href = '/auth/signup'}
                className="px-8 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white font-semibold rounded-lg hover:from-blue-600 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200 shadow-lg hover:shadow-xl"
              >
                Create Free Account
              </button>
              <button
                onClick={() => window.location.href = '/auth/signin'}
                className="px-8 py-3 border border-[var(--border)] text-[var(--fg)] font-semibold rounded-lg hover:bg-[var(--surface)] focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-all duration-200"
              >
                Sign In
              </button>
            </div>
          </div>
        </div>

        {/* Device Info */}
        <div className="relative overflow-hidden rounded-2xl border border-[var(--border)]/50 bg-gradient-to-br from-[var(--surface)] to-[var(--surface-2)] p-6 shadow-lg">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-transparent" />
          <div className="relative z-10">
            <h3 className="text-lg font-semibold text-[var(--fg)] mb-4">Device Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-[var(--muted)]">Device ID:</span>
                <span className="ml-2 font-mono text-[var(--fg)]">{deviceId}</span>
              </div>
              <div>
                <span className="text-[var(--muted)]">Scans Used:</span>
                <span className="ml-2 font-semibold text-orange-600 dark:text-orange-400">{scansUsed}/1</span>
              </div>
              <div>
                <span className="text-[var(--muted)]">Platform:</span>
                <span className="ml-2 text-[var(--fg)]">{navigator.platform}</span>
              </div>
              <div>
                <span className="text-[var(--muted)]">Browser:</span>
                <span className="ml-2 text-[var(--fg)]">{navigator.userAgent.split(' ')[0]}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Render children with scan recording capability
  return (
    <div>
      {React.cloneElement(children as React.ReactElement, { onScanComplete: recordScan })}
      
      {/* Free scan indicator */}
      <div className="mt-4 relative overflow-hidden rounded-xl border border-green-200/50 bg-gradient-to-br from-green-50/50 to-green-100/30 p-4 backdrop-blur-sm dark:border-green-800/50 dark:from-green-950/40 dark:to-green-900/20">
        <div className="absolute inset-0 bg-gradient-to-br from-green-500/5 to-transparent" />
        <div className="relative z-10 flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-medium text-green-700 dark:text-green-300">
            Free scan available ({1 - scansUsed} remaining)
          </span>
        </div>
      </div>
    </div>
  );
}
