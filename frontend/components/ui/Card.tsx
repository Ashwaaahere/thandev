'use client';

import { ReactNode } from 'react';

const cardBase =
  'rounded-xl border shadow-sm transition-colors';
const cardStyle = { background: 'var(--card)', borderColor: 'var(--border)' };

export function Card({
  children,
  className = '',
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`${cardBase} ${className}`} style={cardStyle} {...rest}>
      {children}
    </div>
  );
}

export function CardAlt({
  children,
  className = '',
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`${cardBase} ${className}`}
      style={{ background: 'var(--card-2)', borderColor: 'var(--border)' }}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 pt-5 ${className}`}>{children}</div>;
}

export function CardTitle({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <h2
      className={`text-lg font-semibold ${className}`}
      style={{ color: 'var(--text)' }}
    >
      {children}
    </h2>
  );
}

export function CardDescription({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <p className={`text-sm mt-0.5 ${className}`} style={{ color: 'var(--muted)' }}>
      {children}
    </p>
  );
}

export function CardContent({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`px-5 pb-5 ${className}`}>{children}</div>;
}
