import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import ScanHistoryClient from '@/components/Dashboard/ScanHistoryClient';

export const metadata: Metadata = {
  title: 'Scan History | Thandev',
  description: 'View your performance and security scan history',
  keywords: 'scan history, performance scans, security scans, thandev',
};

export default async function ScanHistoryPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/auth');
  }

  return (
    <ScanHistoryClient user={session.user} />
  );
}
