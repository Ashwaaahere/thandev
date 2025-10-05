import { Metadata } from 'next';
import ProfileClient from '../../../components/Dashboard/ProfileClient';

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

export default function ProfilePage() {
  return <ProfileClient />;
}
