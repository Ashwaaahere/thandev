import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import DashboardScanClient from '../../../components/Dashboard/DashboardScanClient';

export const metadata: Metadata = {
  title: 'Professional Security Scanner - Thandev Dashboard',
  description: 'Advanced security scanning with detailed analysis and reporting for authenticated users',
  keywords: ['security scan', 'vulnerability assessment', 'professional scanner', 'thandev dashboard'],
  openGraph: {
    title: 'Professional Security Scanner - Thandev Dashboard',
    description: 'Advanced security scanning with detailed analysis and reporting for authenticated users',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Professional Security Scanner - Thandev Dashboard',
    description: 'Advanced security scanning with detailed analysis and reporting for authenticated users',
  },
};

export default async function DashboardScanPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth');
  }

  return <DashboardScanClient user={session.user} />;
}

