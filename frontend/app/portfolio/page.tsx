import type { Metadata } from 'next';
import PortfolioClient from './PortfolioClient';

const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Ashwathaman Satish Kumar | Cybersecurity Engineer Portfolio',
  description: 'Cybersecurity professional & Security Engineer candidate specializing in AppSec, SAST/DAST automation, penetration testing, access-control validation, and SecOps.',
  alternates: {
    canonical: `${SITE_URL}/portfolio`,
  },
  openGraph: {
    title: 'Ashwathaman Satish Kumar | Cybersecurity Engineer Portfolio',
    description: 'Security+ Certified Cybersecurity Professional & Security Engineer candidate.',
    url: `${SITE_URL}/portfolio`,
  },
};

export default function PortfolioPage() {
  return <PortfolioClient />;
}
