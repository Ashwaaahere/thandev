import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import ProjectOverviewClient from "@/components/Projects/ProjectOverviewClient";

// Force dynamic rendering since we use getServerSession which requires headers
export const dynamic = 'force-dynamic';

export default async function ProjectOverviewPage({
  params,
}: {
  params: { projectId: string };
}) {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth');
  }
  
  return <ProjectOverviewClient projectId={params.projectId} session={session} />;
}
