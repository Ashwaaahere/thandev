import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import ReportsClient from '@/components/Dashboard/ReportsClient';

export const metadata: Metadata = {
  title: 'Reports | Thandev',
  description: 'Access detailed security scan reports',
  keywords: 'reports, security scans, PDF reports, scan history, thandev',
  openGraph: {
    title: 'Reports | Thandev',
    description: 'Access detailed security scan reports',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Reports | Thandev',
    description: 'Access detailed security scan reports',
  },
};

export default async function ReportsPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth/signin');
  }

  return <ReportsClient />;
}
