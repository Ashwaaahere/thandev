import { redirect } from 'next/navigation';
import { getSafeServerSession } from '@/lib/auth-safe';
import AdminDashboard from '@/components/Admin/AdminDashboard';

// Force dynamic rendering since we use getServerSession which requires headers
export const dynamic = 'force-dynamic';

export default async function AdminPage() {
  const session = await getSafeServerSession();

  if (!session) {
    redirect('/auth');
  }

  // Check if user is admin from session OR if they're a superadmin by external_user_id
  const isAdmin = session?.user?.isAdmin;
  const externalUserId = (session as any)?.externalUserId;
  const token = (session as any)?.token;
  const tokenExternalUserId = token?.externalUserId || token?.sub;
  
  // Check superadmin status from multiple sources
  const isSuperadmin = (externalUserId || tokenExternalUserId) && (
    externalUserId === '97579623' || 
    externalUserId === '4708392' ||
    tokenExternalUserId === '97579623' || 
    tokenExternalUserId === '4708392'
  );
  const effectiveIsAdmin = isAdmin || isSuperadmin;

  if (!effectiveIsAdmin) {
    // If user is a superadmin but session hasn't refreshed, redirect to auth to force refresh
    if (isSuperadmin && !isAdmin) {
      // Force sign out and redirect to auth to trigger bootstrap
      redirect('/auth?callbackUrl=/admin');
    }
    redirect('/dashboard');
  }

  return <AdminDashboard session={session} />;
}

