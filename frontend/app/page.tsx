import type { Metadata } from 'next';
import ThandevLandingClient from './ThandevLandingClient';

const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Thandev — Cybersecurity Intelligence Platform for Developers',
  description: 'Thandev is a comprehensive cybersecurity intelligence platform providing real-time threat monitoring, CVE tracking, vulnerability scanning, security news aggregation, and professional security surface scanning. Trusted by developers and security teams worldwide.',
  alternates: {
    canonical: `${SITE_URL}/`,
  },
  openGraph: {
    title: 'Thandev — Cybersecurity Intelligence Platform for Developers',
    description: 'Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation.',
    url: `${SITE_URL}/`,
  },
};

export default function ThandevLanding() {
  return <ThandevLandingClient />;
}
