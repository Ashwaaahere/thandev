import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import AdminDashboard from '@/components/Admin/AdminDashboard';

export default async function AdminPage() {
  const session = await getServerSession(authOptions);

  if (!session || !session.user?.isAdmin) {
    redirect('/auth');
  }

  return <AdminDashboard session={session} />;
}

