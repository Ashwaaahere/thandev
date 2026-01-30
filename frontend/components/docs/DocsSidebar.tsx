'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { docsNav, docsSections, type NavItem } from '@/lib/docs/nav';

interface DocsSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function DocsSidebar({ isOpen, onClose }: DocsSidebarProps) {
  const pathname = usePathname();

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
        style={{
          background: 'var(--bg)',
          borderRight: '1px solid var(--border)',
        }}
      >
        <div className="flex flex-col h-full">
          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto px-6 py-8 scrollbar-thin">
            <div className="space-y-8">
              {docsSections.map((section) => {
                const sectionItems = docsNav.filter(item => item.section === section);
                return (
                  <div key={section}>
                    <h3
                      className="text-xs font-semibold uppercase tracking-wider mb-3"
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
                              block px-3 py-2 rounded-lg text-sm font-medium transition-all
                              ${isActive ? 'shadow-sm' : ''}
                            `}
                            style={{
                              background: isActive
                                ? 'rgba(99, 102, 241, 0.15)'
                                : 'transparent',
                              color: isActive
                                ? 'rgb(99, 102, 241)'
                                : 'var(--fg)',
                              borderLeft: isActive
                                ? '3px solid rgb(99, 102, 241)'
                                : '3px solid transparent',
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


