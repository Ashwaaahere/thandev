'use client';

import { usePathname } from 'next/navigation';
import Footer from './Footer';

export default function ConditionalFooter() {
  const pathname = usePathname();
  
  // Hide footer for dashboard and projects pages (they use dashboard layout)
  if (pathname.startsWith('/dashboard') || pathname.startsWith('/projects')) {
    return null;
  }
  
  return <Footer />;
}




