'use client';

import { SessionProvider } from 'next-auth/react';
import { ToastProvider } from './Toast';
import ErrorBoundary from './ErrorBoundary';

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <SessionProvider>
        <ToastProvider>
          {children}
        </ToastProvider>
      </SessionProvider>
    </ErrorBoundary>
  );
}


