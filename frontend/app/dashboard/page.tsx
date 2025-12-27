import { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { getSafeServerSession } from '@/lib/auth-safe'
import DashboardClient from '@/components/Dashboard/DashboardClient'

export const metadata: Metadata = {
  title: 'Dashboard | Thandev',
  description: 'Your security testing dashboard - manage scans, view reports, and track your security journey',
  keywords: 'dashboard, security testing, vulnerability assessment, scan management, thandev',
  openGraph: {
    title: 'Dashboard | Thandev',
    description: 'Your security testing dashboard - manage scans, view reports, and track your security journey',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Dashboard | Thandev',
    description: 'Your security testing dashboard - manage scans, view reports, and track your security journey',
  },
  alternates: {
    canonical: '/dashboard',
  },
}

const dashboardStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Dashboard",
  "description": "Security testing dashboard for Thandev platform",
  "url": "/dashboard",
  "isPartOf": {
    "@type": "WebSite",
    "name": "Thandev",
    "url": "/"
  }
}

export default async function DashboardPage() {
  const session = await getSafeServerSession();
  
  if (!session) {
    redirect('/auth');
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(dashboardStructuredData) }}
      />
      <DashboardClient user={session.user} session={session} />
    </>
  )
}
