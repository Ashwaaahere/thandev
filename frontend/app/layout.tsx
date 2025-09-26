import './globals.css';
import type { Metadata } from 'next';
import ThemeProvider from './providers/ThemeProvider';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';

export const metadata: Metadata = {
  title: {
    default: 'Thandev - Cybersecurity Intelligence Platform',
    template: '%s | Thandev'
  },
  description: 'Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation. Stay ahead of cyber threats with Thandev.',
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
    'security analytics'
  ],
  authors: [{ name: 'Thandev Team' }],
  creator: 'Thandev',
  publisher: 'Thandev',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL('https://thandev.com'),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://thandev.com',
    siteName: 'Thandev',
    title: 'Thandev - Cybersecurity Intelligence Platform',
    description: 'Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation.',
    images: [
      {
        url: '/og-image.png',
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
    google: 'your-google-verification-code',
    yandex: 'your-yandex-verification-code',
    yahoo: 'your-yahoo-verification-code',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const structuredData = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Thandev",
    "description": "Real-time cybersecurity intelligence platform with live threat monitoring, vulnerability tracking, and security news aggregation.",
    "url": "https://thandev.com",
    "applicationCategory": "SecurityApplication",
    "operatingSystem": "Web",
    "offers": {
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "USD"
    },
    "creator": {
      "@type": "Organization",
      "name": "Thandev Team",
      "url": "https://thandev.com"
    },
    "featureList": [
      "Real-time cybersecurity news aggregation",
      "CVE vulnerability tracking",
      "Exploit monitoring",
      "Threat intelligence",
      "Security analytics",
      "Live threat feeds"
    ]
  };

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(structuredData),
          }}
        />
      </head>
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

      <body>
        <ThemeProvider>
          <Navbar />
          <main className="min-h-screen">{children}</main>
          <Footer />
        </ThemeProvider>
      </body>
    </html>
  );
}
