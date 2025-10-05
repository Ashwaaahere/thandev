'use client';

import { usePathname } from 'next/navigation';
import Navbar from './Navbar';

export default function ConditionalNavbar() {
  const pathname = usePathname();
  
  // Hide navbar for dashboard pages
  if (pathname.startsWith('/dashboard')) {
    return null;
  }
  
  return <Navbar />;
}




