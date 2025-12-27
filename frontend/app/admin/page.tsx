import { redirect } from 'next/navigation';
import { getSafeServerSession } from '@/lib/auth-safe';
import AdminDashboard from '@/components/Admin/AdminDashboard';

export default async function AdminPage() {
  const session = await getSafeServerSession();

  if (!session || !session.user?.isAdmin) {
    redirect('/auth');
  }

  return <AdminDashboard session={session} />;
}

