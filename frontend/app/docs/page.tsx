import type { Metadata } from 'next';
import Link from 'next/link';
import { docsNav, docsSections } from '@/lib/docs/nav';

const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Documentation | Thandev',
  description: 'Comprehensive documentation for Thandev cybersecurity intelligence platform. Learn how to use security scanning tools, understand scan results, and get the most out of your security testing.',
  alternates: {
    canonical: `${SITE_URL}/docs`,
  },
};

export default function DocsPage() {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <div className="max-w-7xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold mb-4" style={{ color: 'var(--fg)' }}>
            Documentation
          </h1>
          <p className="text-lg" style={{ color: 'var(--muted)' }}>
            Comprehensive guides and resources for using Thandev security testing platform
          </p>
        </div>

        {/* Documentation Sections */}
        <div className="space-y-12">
          {docsSections.map((section) => {
            const sectionItems = docsNav.filter((item) => item.section === section);
            return (
              <div key={section}>
                <h2 className="text-2xl font-bold mb-6" style={{ color: 'var(--fg)' }}>
                  {section}
                </h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {sectionItems.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="block p-6 rounded-lg border transition-all hover:shadow-lg"
                      style={{
                        background: 'var(--surface)',
                        borderColor: 'var(--border)',
                      }}
                    >
                      <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--fg)' }}>
                        {item.title}
                      </h3>
                      <p className="text-sm" style={{ color: 'var(--muted)' }}>
                        {item.shortDescription}
                      </p>
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {/* Quick Start CTA */}
        <div className="mt-16 p-8 rounded-lg border" style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
          <h2 className="text-2xl font-bold mb-4" style={{ color: 'var(--fg)' }}>
            Getting Started
          </h2>
          <p className="mb-6" style={{ color: 'var(--muted)' }}>
            New to Thandev? Start with our overview and getting started guides to learn the basics.
          </p>
          <div className="flex gap-4">
            <Link
              href="/docs/overview"
              className="px-6 py-3 rounded-lg font-medium transition-colors"
              style={{
                background: 'var(--brand)',
                color: 'white',
              }}
            >
              Read Overview
            </Link>
            <Link
              href="/docs/getting-started"
              className="px-6 py-3 rounded-lg font-medium border transition-colors"
              style={{
                borderColor: 'var(--border)',
                color: 'var(--fg)',
              }}
            >
              Get Started Guide
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
