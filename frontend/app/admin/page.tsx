import { redirect } from 'next/navigation';
import { getSafeServerSession } from '@/lib/auth-safe';
import AdminDashboard from '@/components/Admin/AdminDashboard';

// Force dynamic rendering since we use getServerSession which requires headers
export const dynamic = 'force-dynamic';

export default async function AdminPage() {
  const session = await getSafeServerSession();

  // Check if user is admin from session OR if they're a superadmin by external_user_id
  const isAdmin = session?.user?.isAdmin;
  const externalUserId = (session as any)?.externalUserId;
  const isSuperadmin = externalUserId && (
    externalUserId === '97579623' || 
    externalUserId === '4708392'
  );
  const effectiveIsAdmin = isAdmin || isSuperadmin;

  if (!session || !effectiveIsAdmin) {
    redirect('/dashboard');
  }

  return <AdminDashboard session={session} />;
}

