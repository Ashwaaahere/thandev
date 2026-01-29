import { redirect } from 'next/navigation';
import { getSafeServerSession } from '@/lib/auth-safe';
import AuthPage from "@/components/Auth/AuthPage";

const SITE_URL = 'https://thandev.io';

export const metadata = {
  title: "Authentication Security Platform | Thandev",
  description: "Sign in or create your Thandev account to access unlimited security scans, vulnerability assessments, and professional cybersecurity tools.",
  keywords: [
    "authentication",
    "login",
    "signup",
    "security platform",
    "cybersecurity tools",
    "vulnerability scanner",
    "thandev account"
  ],
  openGraph: {
    title: "Authentication Security Platform | Thandev",
    description: "Sign in or create your Thandev account to access unlimited security scans and vulnerability assessments.",
    type: "website",
    url: `${SITE_URL}/auth`,
  },
  twitter: {
    card: "summary_large_image",
    title: "Authentication Security Platform | Thandev",
    description: "Sign in or create your Thandev account to access unlimited security scans and vulnerability assessments.",
  },
  alternates: {
    canonical: `${SITE_URL}/auth`,
  },
};

// Force dynamic rendering since we use getServerSession which requires headers
export const dynamic = 'force-dynamic';

export default async function Auth() {
  const session = await getSafeServerSession();
  
  if (session) {
    redirect('/dashboard');
  }

  return <AuthPage />;
}

