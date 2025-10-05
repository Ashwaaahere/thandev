import { Metadata } from 'next'
import { getServerSession } from 'next-auth'
import { redirect } from 'next/navigation'
import { authOptions } from '@/lib/auth'
import PerformanceScanClient from '@/components/Dashboard/PerformanceScanClient'

export const metadata: Metadata = {
  title: 'Performance Scan | Thandev',
  description: 'Website performance analysis using Google Lighthouse technology - Core Web Vitals, optimization recommendations, and detailed performance metrics',
  keywords: 'performance scan, lighthouse, core web vitals, website optimization, page speed, performance analysis, thandev',
  openGraph: {
    title: 'Performance Scan | Thandev',
    description: 'Website performance analysis using Google Lighthouse technology - Core Web Vitals, optimization recommendations, and detailed performance metrics',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Performance Scan | Thandev',
    description: 'Website performance analysis using Google Lighthouse technology - Core Web Vitals, optimization recommendations, and detailed performance metrics',
  },
  alternates: {
    canonical: '/dashboard/performance',
  },
}

const performanceStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Performance Scan",
  "description": "Website performance analysis and optimization recommendations",
  "url": "/dashboard/performance",
  "isPartOf": {
    "@type": "WebSite",
    "name": "Thandev",
    "url": "/"
  }
}

export default async function PerformanceScanPage() {
  const session = await getServerSession(authOptions);
  
  if (!session) {
    redirect('/auth');
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(performanceStructuredData) }}
      />
      <PerformanceScanClient user={session.user} />
    </>
  )
}
