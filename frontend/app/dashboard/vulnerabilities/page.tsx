import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { redirect } from 'next/navigation';
import VulnerabilitiesClient from '@/components/Dashboard/VulnerabilitiesClient';
import { thandevFetchJSON } from '@/lib/thandevApi';

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

// Force dynamic rendering since we use getServerSession which requires headers
export const dynamic = 'force-dynamic';

export default async function VulnerabilitiesPage({
  searchParams,
}: {
  searchParams: { 
    projectId?: string;
    scan_id?: string;
    severity?: string;
    status?: string;
    tool?: string;
    category?: string;
    vuln_type?: string;
    search?: string;
    page?: string;
  };
}) {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/auth/signin');
  }

  // Fetch initial data on the server for fresh data on every page load
  try {
    const params = new URLSearchParams();
    params.append('limit', '20');
    params.append('offset', '0');
    
    // Apply search params filters
    if (searchParams.projectId) {
      params.append('project_id', searchParams.projectId);
    }
    if (searchParams.scan_id) {
      params.append('scan_id', searchParams.scan_id);
    }
    if (searchParams.severity) {
      params.append('severity', searchParams.severity);
    }
    if (searchParams.status) {
      params.append('status', searchParams.status);
    }
    if (searchParams.tool) {
      params.append('tool', searchParams.tool);
    }
    if (searchParams.category) {
      params.append('category', searchParams.category);
    }
    if (searchParams.vuln_type) {
      params.append('vuln_type', searchParams.vuln_type);
    }
    if (searchParams.search) {
      params.append('search', searchParams.search);
    }
    if (searchParams.page) {
      const page = parseInt(searchParams.page) || 0;
      params.set('offset', (page * 20).toString());
    }

    // Fetch findings and projects in parallel
    const [findingsData, projectsData] = await Promise.all([
      thandevFetchJSON<{
        items: any[];
        total: number;
      }>(`/api/findings?${params.toString()}`, session).catch(() => ({ items: [], total: 0 })),
      thandevFetchJSON<{
        items: any[];
        total: number;
      }>('/api/projects', session).catch(() => ({ items: [], total: 0 })),
    ]);

    return (
      <VulnerabilitiesClient
        initialProjectId={searchParams.projectId}
        initialFindings={findingsData.items || []}
        initialTotal={findingsData.total || 0}
        initialProjects={projectsData.items || []}
        initialPage={searchParams.page ? parseInt(searchParams.page) || 0 : 0}
      />
    );
  } catch (error) {
    console.error('Error loading vulnerabilities on server:', error);
    // Still render client component, it will handle the error state
    return (
      <VulnerabilitiesClient
        initialProjectId={searchParams.projectId}
        initialFindings={[]}
        initialTotal={0}
        initialProjects={[]}
        initialPage={0}
      />
    );
  }
}
