import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import ProjectsListClient from '@/components/Projects/ProjectsListClient';

export const metadata: Metadata = {
  title: 'Projects | Thandev',
  description: 'Manage your security scanning projects',
  keywords: 'projects, security scanning, vulnerability assessment, thandev',
};

export default async function ProjectsPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth');
  }
  
  return <ProjectsListClient />;
}
