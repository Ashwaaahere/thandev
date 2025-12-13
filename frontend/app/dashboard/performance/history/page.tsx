import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import PerformanceHistoryClient from '@/components/Dashboard/PerformanceHistoryClient';

export const metadata: Metadata = {
  title: 'Performance Scan History - Thandev Dashboard',
  description: 'View and manage your performance scan results',
  keywords: ['performance scans', 'scan history', 'performance metrics', 'thandev dashboard'],
  openGraph: {
    title: 'Performance Scan History - Thandev Dashboard',
    description: 'View and manage your performance scan results',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Performance Scan History - Thandev Dashboard',
    description: 'View and manage your performance scan results',
  },
};

export default async function PerformanceHistoryPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth/signin');
  }

  return <PerformanceHistoryClient />;
}
