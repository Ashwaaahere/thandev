import type { Metadata } from 'next';
import ThandevLandingClient from './ThandevLandingClient';

const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Thandev — Cybersecurity Scanning Tool | Web Security Testing Platform',
  description: 'Professional web security scanning tool used by real cybersecurity teams. Test your applications like security experts with automated vulnerability scanning, penetration testing, and threat detection.',
  alternates: {
    canonical: `${SITE_URL}/`,
  },
  openGraph: {
    title: 'Thandev — Cybersecurity Scanning Tool | Web Security Testing Platform',
    description: 'Professional web security scanning tool used by real cybersecurity teams. Test your applications like security experts with automated vulnerability scanning.',
    url: `${SITE_URL}/`,
  },
};

export default function ThandevLanding() {
  return <ThandevLandingClient />;
}
