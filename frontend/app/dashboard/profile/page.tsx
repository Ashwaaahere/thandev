import { Metadata } from 'next';
import { getServerSession } from 'next-auth';
import { redirect } from 'next/navigation';
import { authOptions } from '@/lib/auth';
import ProfileClient from '@/components/Dashboard/ProfileClient';

export const metadata: Metadata = {
  title: 'Profile - Thandev Security Platform',
  description: 'Manage your profile settings and account information',
  keywords: ['profile', 'account', 'settings', 'security', 'thandev'],
  openGraph: {
    title: 'Profile - Thandev Security Platform',
    description: 'Manage your profile settings and account information',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Profile - Thandev Security Platform',
    description: 'Manage your profile settings and account information',
  },
};

export default async function ProfilePage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/auth');
  }

  return <ProfileClient user={session.user} />;
}
