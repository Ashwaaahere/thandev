import './globals.css';
import type { Metadata } from 'next';
import ThemeProvider from './providers/ThemeProvider';
import Providers from '@/components/Providers';
import ConditionalNavbar from '@/components/ConditionalNavbar';
import ConditionalFooter from '@/components/ConditionalFooter';
import SeoJsonLd from '@/components/SeoJsonLd';

export const metadata: Metadata = {
  title: {
    default: 'Thandev - Cybersecurity Intelligence Platform',
    template: '%s | Thandev'
  },
  icons: {
    icon: '/logo.png',
    shortcut: '/logo.png',
    apple: '/logo.png',
  },
  description: 'Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, security news aggregation, and professional surface scanning. GitHub-authenticated access for developers.',
  keywords: [
    'cybersecurity',
    'threat intelligence',
    'vulnerability tracking',
    'security news',
    'CVE database',
    'exploit monitoring',
    'cyber threats',
    'security platform',
    'threat detection',
    'security analytics',
    'surface scanning',
    'vulnerability scanner',
    'github authentication',
    'developer security tools'
  ],
  authors: [{ name: 'Thandev Team' }],
  creator: 'Thandev',
  publisher: 'Thandev',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL('https://thandev.io'),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://thandev.io',
    siteName: 'Thandev',
    title: 'Thandev - Cybersecurity Intelligence Platform',
    description: 'Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation.',
    images: [
      {
        url: 'https://thandev.io/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Thandev - Cybersecurity Intelligence Platform',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Thandev - Cybersecurity Intelligence Platform',
    description: 'Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation.',
    images: ['/og-image.png'],
    creator: '@thandev',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  verification: {
    // Add your Google Search Console verification code here
    // google: 'your-google-verification-code',
    // yandex: 'your-yandex-verification-code',
    // yahoo: 'your-yahoo-verification-code',
  },
  category: 'Cybersecurity',
  classification: 'Security Software',
  applicationName: 'Thandev',
  manifest: '/manifest.json',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Comprehensive structured data using @graph format
  // This replaces SoftwareApplication (which requires aggregateRating/review) with proper schema types
  const structuredData = [
    {
      "@type": "Organization",
      "@id": "https://thandev.io/#organization",
      "name": "Thandev",
      "url": "https://thandev.io/",
      "logo": {
        "@type": "ImageObject",
        "url": "https://thandev.io/logo.png",
        "width": 512,
        "height": 512,
      },
      "description": "Cybersecurity intelligence platform providing real-time threat monitoring, vulnerability tracking, and security scanning.",
      // Note: sameAs omitted as no social links found in footer
    },
    {
      "@type": "WebSite",
      "@id": "https://thandev.io/#website",
      "url": "https://thandev.io/",
      "name": "Thandev",
      "description": "Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation.",
      "publisher": {
        "@id": "https://thandev.io/#organization",
      },
      "potentialAction": {
        "@type": "SearchAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": "https://thandev.io/search?q={search_term_string}"
        },
        "query-input": "required name=search_term_string"
      }
    },
    {
      "@type": "LandingPage",
      "@id": "https://thandev.io/#webpage",
      "url": "https://thandev.io/",
      "name": "Thandev - Cybersecurity Intelligence Platform",
      "description": "Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, security news aggregation, and professional surface scanning.",
      "isPartOf": {
        "@id": "https://thandev.io/#website",
      },
      "about": {
        "@id": "https://thandev.io/#product",
      },
    },
    {
      "@type": "Product",
      "@id": "https://thandev.io/#product",
      "name": "Thandev",
      "description": "Cybersecurity intelligence platform providing real-time threat monitoring, vulnerability tracking, CVE database access, exploit monitoring, and professional security surface scanning for developers and security teams.",
      "category": "Cybersecurity",
      "brand": {
        "@id": "https://thandev.io/#organization",
      },
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD",
        "availability": "https://schema.org/PreOrder",
        "url": "https://thandev.io/private-beta",
        "description": "Beta access available - request early access or sign in with GitHub",
      },
      // Note: aggregateRating and review intentionally omitted - no fake reviews
    },
  ];

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Structured Data - Using @graph format for multiple schema types */}
        <SeoJsonLd schema={structuredData} />
        {/* Preconnect to improve performance */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* DNS Prefetch for external resources */}
        <link rel="dns-prefetch" href="https://api.github.com" />
        <link rel="dns-prefetch" href="https://github.com" />
        {/* Manifest */}
        <link rel="manifest" href="/manifest.json" />
        {/* Theme color for mobile browsers */}
        <meta name="theme-color" content="#6366f1" />
        <meta name="msapplication-TileColor" content="#6366f1" />
        {/* Apple touch icon */}
        <link rel="apple-touch-icon" href="/logo.png" />
        {/* theme init: light/dark before first paint */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
          (function(){
            try {
              var t = localStorage.getItem('theme');
              if(!t){
                t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
              }
              var r = document.documentElement;
              r.classList.toggle('dark', t === 'dark');
              r.classList.toggle('light', t === 'light');
            } catch (e) {}
          })();`,
          }}
        />
      </head>

      <body>
        <Providers>
          <ThemeProvider>
            <ConditionalNavbar />
            <main className="min-h-screen">{children}</main>
            <ConditionalFooter />
          </ThemeProvider>
        </Providers>
      </body>
    </html>
  );
}
