import { redirect } from 'next/navigation';
import { getSafeServerSession } from '@/lib/auth-safe';
import AuthPage from "@/components/Auth/AuthPage";

export const metadata = {
  title: "Authentication - Thandev Security Platform",
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
    title: "Authentication - Thandev Security Platform",
    description: "Sign in or create your Thandev account to access unlimited security scans and vulnerability assessments.",
    type: "website",
    url: "https://thandev.com/auth",
  },
  twitter: {
    card: "summary_large_image",
    title: "Authentication - Thandev Security Platform",
    description: "Sign in or create your Thandev account to access unlimited security scans and vulnerability assessments.",
  },
  alternates: {
    canonical: "/auth",
  },
};

export default async function Auth() {
  const session = await getSafeServerSession();
  
  if (session) {
    redirect('/dashboard');
  }

  return <AuthPage />;
}

