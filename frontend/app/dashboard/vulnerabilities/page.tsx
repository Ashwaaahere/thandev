import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import VulnerabilitiesClient from '@/components/Dashboard/VulnerabilitiesClient';

export const metadata: Metadata = {
  title: 'Vulnerabilities | Thandev',
  description: 'View and prioritize security issues detected by your scans',
  keywords: 'vulnerabilities, security issues, findings, CVE, CWE, thandev',
  openGraph: {
    title: 'Vulnerabilities | Thandev',
    description: 'View and prioritize security issues detected by your scans',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Vulnerabilities | Thandev',
    description: 'View and prioritize security issues detected by your scans',
  },
  alternates: {
    canonical: '/dashboard/vulnerabilities',
  },
};

export default async function VulnerabilitiesPage({
  searchParams,
}: {
  searchParams: { projectId?: string };
}) {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/auth/signin');
  }

  return <VulnerabilitiesClient initialProjectId={searchParams.projectId} />;
}
