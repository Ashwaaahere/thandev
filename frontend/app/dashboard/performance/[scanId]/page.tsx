import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import PerformanceDetailClient from '@/components/Dashboard/PerformanceDetailClient';

export const metadata: Metadata = {
  title: 'Performance Scan Details - Thandev Dashboard',
  description: 'View detailed performance scan results',
  keywords: ['performance scan', 'page speed', 'web vitals', 'thandev dashboard'],
};

export default async function PerformanceDetailPage({
  params,
}: {
  params: { scanId: string };
}) {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth/signin');
  }

  return <PerformanceDetailClient scanId={params.scanId} session={session} />;
}
