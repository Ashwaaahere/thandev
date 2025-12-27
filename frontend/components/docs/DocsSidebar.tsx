'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { docsNav, docsSections, type NavItem } from '@/lib/docs/nav';
import DocsSearch from './DocsSearch';

interface DocsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function DocsSidebar({ isOpen, onClose }: DocsSidebarProps) {
  const pathname = usePathname();

  const handleSearchSelect = (item: NavItem) => {
    onClose();
    window.location.href = item.href;
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        style={{ background: 'var(--surface)' }}
      >
        <div className="flex flex-col h-full border-r" style={{ borderColor: 'var(--border)' }}>
          {/* Header */}
          <div className="px-4 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <Link href="/docs" className="flex items-center gap-2 mb-4">
              <div className="h-8 w-8 rounded-lg" style={{ background: 'var(--brand)' }} />
              <span className="text-lg font-bold" style={{ color: 'var(--fg)' }}>
                Documentation
              </span>
            </Link>
            <DocsSearch onSelect={handleSearchSelect} />
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-4 py-4 scrollbar-thin">
            <div className="space-y-6">
              {docsSections.map((section) => {
                const sectionItems = docsNav.filter(item => item.section === section);
                return (
                  <div key={section}>
                    <h3
                      className="text-xs font-semibold uppercase tracking-wider mb-2"
                      style={{ color: 'var(--muted)' }}
                    >
                      {section}
                    </h3>
                    <div className="space-y-1">
                      {sectionItems.map((item) => {
                        const isActive = pathname === item.href;
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            onClick={onClose}
                            className={`
                              block px-3 py-2 rounded-lg text-sm font-medium transition-colors
                              ${isActive ? 'text-white shadow-sm' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}
                            `}
                            style={{
                              background: isActive ? 'var(--brand)' : 'transparent',
                              color: isActive ? 'white' : 'var(--fg)',
                            }}
                          >
                            {item.title}
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </nav>
        </div>
      </aside>
    </>
  );
}


