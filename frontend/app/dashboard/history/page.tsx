import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import ScanHistoryClient from '@/components/Dashboard/ScanHistoryClient';

export const metadata: Metadata = {
  title: 'Scan History | Thandev',
  description: 'View your performance and security scan history with detailed results and analysis',
  keywords: 'scan history, performance scans, security scans, scan results, thandev',
  openGraph: {
    title: 'Scan History | Thandev',
    description: 'View your performance and security scan history with detailed results and analysis',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Scan History | Thandev',
    description: 'View your performance and security scan history with detailed results and analysis',
  },
  alternates: {
    canonical: '/dashboard/history',
  },
};

export default async function ScanHistoryPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/auth/signin');
  }

  return <ScanHistoryClient user={session.user} />;
}
