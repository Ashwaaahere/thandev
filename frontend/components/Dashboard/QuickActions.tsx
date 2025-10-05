'use client';

import Link from 'next/link';

export default function QuickActions() {
  const actions = [
    {
      title: 'New Surface Scan',
      description: 'Start a comprehensive security assessment',
      href: '/dashboard/scan',
      icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z',
      color: 'bg-blue-500',
      textColor: 'text-blue-600 dark:text-blue-400'
    },
    {
      title: 'View Reports',
      description: 'Access detailed security reports',
      href: '/dashboard/reports',
      icon: 'M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
      color: 'bg-green-500',
      textColor: 'text-green-600 dark:text-green-400'
    },
    {
      title: 'Vulnerability Database',
      description: 'Browse latest security threats',
      href: '/exploits',
      icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z',
      color: 'bg-red-500',
      textColor: 'text-red-600 dark:text-red-400'
    },
    {
      title: 'Security News',
      description: 'Stay updated with latest news',
      href: '/news',
      icon: 'M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z',
      color: 'bg-purple-500',
      textColor: 'text-purple-600 dark:text-purple-400'
    }
  ];

  return (
    <div className="rounded-xl border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      {/* Header */}
      <div className="px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <h2 className="text-lg font-semibold" style={{ color: 'var(--fg)' }}>
          Quick Actions
        </h2>
      </div>

      {/* Content */}
      <div className="p-6">
        <div className="space-y-4">
          {actions.map((action, index) => (
            <Link
              key={index}
              href={action.href}
              className="block p-4 rounded-lg border hover:shadow-md transition-all duration-200 group hover:bg-[var(--surface)]"
              style={{ 
                borderColor: 'var(--border)', 
                background: 'var(--surface-2)'
              }}
            >
              <div className="flex items-start gap-4">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${action.color} bg-opacity-10 group-hover:bg-opacity-20 transition-all duration-200`}>
                  <svg className={`w-5 h-5 ${action.textColor}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={action.icon} />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium mb-1 group-hover:opacity-80 transition-opacity" style={{ color: 'var(--fg)' }}>
                    {action.title}
                  </h3>
                  <p className="text-sm" style={{ color: 'var(--muted)' }}>
                    {action.description}
                  </p>
                </div>
                <div className="flex-shrink-0">
                  <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform duration-200" style={{ color: 'var(--muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Additional Info */}
        <div className="mt-6 p-4 rounded-lg" style={{ background: 'var(--brand)', opacity: 0.05 }}>
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5" style={{ color: 'var(--brand)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h4 className="text-sm font-medium mb-1" style={{ color: 'var(--fg)' }}>
                Pro Tip
              </h4>
              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                Run regular scans to maintain security posture and catch vulnerabilities early.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


