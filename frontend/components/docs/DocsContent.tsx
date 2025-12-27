'use client';

import dynamic from 'next/dynamic';
import { MDXRemoteSerializeResult } from 'next-mdx-remote';

// Dynamically import both client components to avoid SSG issues
const MdxContent = dynamic(() => import('@/lib/docs/mdx').then(mod => ({ default: mod.MdxContent })), {
  ssr: false, // MDXRemote uses hooks, disable SSR for SSG compatibility
});

const CopyLinkButton = dynamic(() => import('@/components/docs/CopyLinkButton'), {
  ssr: false, // CopyLinkButton uses window, so no SSR
});

interface DocsContentProps {
  source: MDXRemoteSerializeResult;
  title: string;
  description?: string;
  href: string;
  lastUpdated?: string;
}

export default function DocsContent({ source, title, description, href, lastUpdated }: DocsContentProps) {
  return (
    <div className="max-w-4xl mx-auto px-4 py-8 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex-1">
          <h1 className="text-3xl font-bold mb-2" style={{ color: 'var(--fg)' }}>
            {title}
          </h1>
          {description && (
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              {description}
            </p>
          )}
        </div>
        <CopyLinkButton href={href} />
      </div>

      <div
        className="card p-8 mb-6 prose prose-lg max-w-none"
        style={{
          background: 'var(--surface)',
          borderColor: 'var(--border)',
        }}
      >
        <MdxContent source={source} />
      </div>

      {lastUpdated && (
        <div className="text-xs text-center" style={{ color: 'var(--muted)' }}>
          Last updated: {lastUpdated}
        </div>
      )}
    </div>
  );
}

