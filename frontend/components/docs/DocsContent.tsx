'use client';

import dynamic from 'next/dynamic';
import { MDXRemoteSerializeResult } from 'next-mdx-remote';
import { usePathname } from 'next/navigation';
import { docsNav, getNavItemByHref } from '@/lib/docs/nav';
import DocsRightSidebar from './DocsRightSidebar';

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
  const pathname = usePathname();
  const navItem = getNavItemByHref(pathname);
  const section = navItem?.section || '';

  return (
    <div className="flex-1 flex">
      {/* Main Content */}
      <div className="flex-1 max-w-4xl mx-auto px-6 py-8 lg:px-12">
        {/* Breadcrumbs */}
        {section && (
          <nav className="mb-6 text-sm" style={{ color: 'var(--muted)' }}>
            <span className="uppercase">{section}</span>
            <span className="mx-2">/</span>
            <span className="uppercase">{title}</span>
          </nav>
        )}

        {/* Title and Description */}
        <div className="mb-8">
          <div className="flex items-start justify-between gap-4 mb-4">
            <h1
              className="text-4xl lg:text-5xl font-bold"
              style={{ color: 'var(--fg)' }}
            >
              {title}
            </h1>
            <CopyLinkButton href={href} />
          </div>
          {description && (
            <div
              className="pl-4 border-l-4 mb-6"
              style={{
                borderColor: 'rgb(59, 130, 246)',
              }}
            >
              <p className="text-base leading-relaxed" style={{ color: 'var(--muted)' }}>
                {description}
              </p>
            </div>
          )}
        </div>

        {/* Content */}
        <div
          className="prose prose-lg max-w-none mb-12"
          style={{
            color: 'var(--fg)',
          }}
        >
          <MdxContent source={source} />
        </div>

        {/* Footer */}
        {lastUpdated && (
          <div
            className="flex items-center justify-between pt-8 border-t"
            style={{
              borderColor: 'var(--border)',
            }}
          >
            <div className="text-xs" style={{ color: 'var(--muted)' }}>
              Last updated: {lastUpdated}
            </div>
            <div className="flex items-center gap-4">
              <a
                href="https://twitter.com/thandev"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs hover:opacity-80 transition-opacity"
                style={{ color: 'var(--muted)' }}
              >
                Twitter
              </a>
              <a
                href="https://github.com/thandev"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs hover:opacity-80 transition-opacity"
                style={{ color: 'var(--muted)' }}
              >
                GitHub
              </a>
              <a
                href="https://discord.gg/thandev"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs hover:opacity-80 transition-opacity"
                style={{ color: 'var(--muted)' }}
              >
                Discord
              </a>
            </div>
          </div>
        )}
      </div>

      {/* Right Sidebar */}
      <DocsRightSidebar />
    </div>
  );
}

