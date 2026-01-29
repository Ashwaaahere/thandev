import type { Metadata } from 'next';
import { redirect } from 'next/navigation';

const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Documentation | Thandev',
  description: 'Comprehensive documentation for Thandev cybersecurity intelligence platform. Learn how to use security scanning tools, understand scan results, and get the most out of your security testing.',
  alternates: {
    canonical: `${SITE_URL}/docs`,
  },
};

export default function DocsPage() {
  redirect('/docs/overview');
}