import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import PerformanceScannerClient from '@/components/Dashboard/PerformanceScannerClient';

export const metadata: Metadata = {
  title: 'Performance Scanner - Thandev Dashboard',
  description: 'Run performance checks on your targets',
  keywords: ['performance scan', 'page speed', 'web vitals', 'thandev dashboard'],
  openGraph: {
    title: 'Performance Scanner - Thandev Dashboard',
    description: 'Run performance checks on your targets',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Performance Scanner - Thandev Dashboard',
    description: 'Run performance checks on your targets',
  },
};

export default async function PerformanceScanPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth/signin');
  }

  return <PerformanceScannerClient />;
}
