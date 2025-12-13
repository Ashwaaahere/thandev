'use client';

import { usePathname } from 'next/navigation';
import Navbar from './Navbar';

export default function ConditionalNavbar() {
  const pathname = usePathname();
  
  // Hide navbar for dashboard and projects pages (they use dashboard layout)
  if (pathname.startsWith('/dashboard') || pathname.startsWith('/projects')) {
    return null;
  }
  
  return <Navbar />;
}




