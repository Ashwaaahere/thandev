import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import SecurityScannerClient from '@/components/Dashboard/SecurityScannerClient';

export const metadata: Metadata = {
  title: 'Security Scanner - Thandev Dashboard',
  description: 'Launch a new security assessment for your website or API',
  keywords: ['security scan', 'vulnerability assessment', 'scanner', 'thandev dashboard'],
  openGraph: {
    title: 'Security Scanner - Thandev Dashboard',
    description: 'Launch a new security assessment for your website or API',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Security Scanner - Thandev Dashboard',
    description: 'Launch a new security assessment for your website or API',
  },
};

export default async function DashboardScanPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth/signin');
  }

  return <SecurityScannerClient />;
}

