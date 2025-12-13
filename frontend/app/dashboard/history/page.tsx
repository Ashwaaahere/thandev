import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import HistoryClient from '@/components/Dashboard/HistoryClient';

export const metadata: Metadata = {
  title: 'History | Thandev',
  description: 'View your security and performance scan history with detailed results and analysis',
  keywords: 'scan history, performance scans, security scans, scan results, thandev',
  openGraph: {
    title: 'History | Thandev',
    description: 'View your security and performance scan history with detailed results and analysis',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'History | Thandev',
    description: 'View your security and performance scan history with detailed results and analysis',
  },
  alternates: {
    canonical: '/dashboard/history',
  },
};

export default async function HistoryPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/auth/signin');
  }

  return <HistoryClient />;
}
