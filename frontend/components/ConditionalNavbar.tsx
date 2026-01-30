'use client';

import { usePathname } from 'next/navigation';
import Navbar from './Navbar';

export default function ConditionalNavbar() {
  const pathname = usePathname();
  
  // Hide navbar for dashboard, projects, and docs pages (they use their own layouts)
  if (
    pathname.startsWith('/dashboard') || 
    pathname.startsWith('/projects') ||
    pathname.startsWith('/docs')
  ) {
    return null;
  }
  
  return <Navbar />;
}




