'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Heading {
  id: string;
  text: string;
  level: number;
}

interface DocsRightSidebarProps {
  content?: string;
}

export default function DocsRightSidebar({ content }: DocsRightSidebarProps) {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState<string>('');

  useEffect(() => {
    // Extract headings from rendered DOM
    if (typeof window !== 'undefined') {
      // Wait for content to render
      const timeout = setTimeout(() => {
        const mainContent = document.querySelector('main') || document.body;
        const headingElements = mainContent.querySelectorAll('h2, h3');
        const extractedHeadings: Heading[] = [];

        headingElements.forEach((el) => {
          let id = el.id;
          if (!id && el.textContent) {
            // Generate ID from text content
            id = el.textContent
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, '-')
              .replace(/^-+|-+$/g, '');
            el.id = id;
          }
          
          if (id && el.textContent) {
            extractedHeadings.push({
              id,
              text: el.textContent.trim(),
              level: parseInt(el.tagName.charAt(1)),
            });
          }
        });

        setHeadings(extractedHeadings);

        // Set up intersection observer for active heading
        if (headingElements.length > 0) {
          const observer = new IntersectionObserver(
            (entries) => {
              // Find the first intersecting heading
              const intersecting = entries
                .filter((e) => e.isIntersecting)
                .sort((a, b) => {
                  const aTop = a.boundingClientRect.top;
                  const bTop = b.boundingClientRect.top;
                  return aTop - bTop;
                });

              if (intersecting.length > 0) {
                setActiveId(intersecting[0].target.id);
              }
            },
            { rootMargin: '-100px 0% -66% 0%' }
          );

          headingElements.forEach((el) => observer.observe(el));

          return () => {
            headingElements.forEach((el) => observer.unobserve(el));
          };
        }
      }, 100);

      return () => clearTimeout(timeout);
    }
  }, [content]);

  if (headings.length === 0) {
    return null;
  }

  return (
    <aside
      className="hidden xl:block w-64 flex-shrink-0 pl-8"
      style={{ borderLeft: '1px solid var(--border)' }}
    >
      <div className="sticky top-24">
        {/* On This Page */}
        <div className="mb-8">
          <h3
            className="text-xs font-semibold uppercase tracking-wider mb-4"
            style={{ color: 'var(--muted)' }}
          >
            On This Page
          </h3>
          <nav className="space-y-1">
            {headings.map((heading) => (
              <a
                key={heading.id}
                href={`#${heading.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  const element = document.getElementById(heading.id);
                  if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    setActiveId(heading.id);
                  }
                }}
                className={`block text-sm transition-colors ${
                  heading.level === 3 ? 'pl-4' : ''
                } ${
                  activeId === heading.id
                    ? 'font-medium'
                    : 'hover:opacity-80'
                }`}
                style={{
                  color:
                    activeId === heading.id
                      ? 'var(--brand)'
                      : 'var(--muted)',
                }}
              >
                {heading.text}
              </a>
            ))}
          </nav>
        </div>

        {/* Need Help Section */}
        <div
          className="p-4 rounded-lg border"
          style={{
            background: 'var(--surface)',
            borderColor: 'var(--border)',
          }}
        >
          <h3
            className="text-sm font-semibold mb-2"
            style={{ color: 'var(--fg)' }}
          >
            Need help?
          </h3>
          <p
            className="text-xs mb-3"
            style={{ color: 'var(--muted)' }}
          >
            Can&apos;t find what you&apos;re looking for? Reach out to our security team.
          </p>
          <Link
            href="/docs/responsible-disclosure"
            className="inline-flex items-center gap-2 text-xs font-medium transition-colors"
            style={{ color: 'var(--brand)' }}
          >
            Contact Security
            <svg
              className="w-3 h-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </Link>
        </div>
      </div>
    </aside>
  );
}

