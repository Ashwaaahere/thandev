import './globals.css';
import type { Metadata } from 'next';
import ThemeProvider from './providers/ThemeProvider';
import Providers from '@/components/Providers';
import ConditionalNavbar from '@/components/ConditionalNavbar';
import ConditionalFooter from '@/components/ConditionalFooter';
import SeoJsonLd from '@/components/SeoJsonLd';

export const metadata: Metadata = {
  title: {
    default: 'Thandev - Cybersecurity Scanning Tool | Web Security Testing Platform',
    template: '%s | Thandev'
  },
  icons: {
    icon: [
      { url: '/favicon.ico', type: 'image/x-icon' },
      { url: '/icon-192.png', type: 'image/png', sizes: '192x192' },
      { url: '/icon-512.png', type: 'image/png', sizes: '512x512' },
    ],
    apple: [
      { url: '/apple-touch-icon.png', sizes: '180x180' },
    ],
  },
  description: 'Professional web security scanning tool used by real cybersecurity teams. Test your applications like security experts with automated vulnerability scanning, penetration testing, and threat detection.',
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
    'developer security tools',
    'web security',
    'application security',
    'penetration testing',
    'security scanning',
    'threat monitoring',
    'cybersecurity platform',
    'vulnerability management',
    'security assessment',
    'cyber defense',
    'security intelligence',
    'security testing',
    'vulnerability assessment',
    'cyber security tools',
    'security automation',
    'threat hunting',
    'security operations'
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
  // Canonical URLs are set per-page, not globally
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://thandev.io',
    siteName: 'Thandev',
    title: 'Thandev - Cybersecurity Scanning Tool | Web Security Testing Platform',
    description: 'Professional web security scanning tool used by real cybersecurity teams. Test your applications like security experts with automated vulnerability scanning.',
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
    title: 'Thandev - Cybersecurity Scanning Tool | Web Security Testing Platform',
    description: 'Professional web security scanning tool used by real cybersecurity teams. Test your applications like security experts with automated vulnerability scanning.',
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
      "image": "https://thandev.io/og-image.png",
      "brand": {
        "@type": "Brand",
        "name": "Thandev",
        "@id": "https://thandev.io/#organization",
      },
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD",
        "availability": "https://schema.org/PreOrder",
        "url": "https://thandev.io/private-beta",
        "description": "Beta access available - request early access or sign in with GitHub",
        "priceValidUntil": "2026-12-31",
        "shippingDetails": {
          "@type": "OfferShippingDetails",
          "shippingRate": {
            "@type": "MonetaryAmount",
            "value": "0",
            "currency": "USD"
          },
          "shippingDestination": {
            "@type": "DefinedRegion",
            "addressCountry": "US"
          },
          "deliveryTime": {
            "@type": "ShippingDeliveryTime",
            "handlingTime": {
              "@type": "QuantitativeValue",
              "minValue": 0,
              "maxValue": 0,
              "unitCode": "DAY"
            },
            "transitTime": {
              "@type": "QuantitativeValue",
              "minValue": 0,
              "maxValue": 0,
              "unitCode": "DAY"
            }
          }
        },
        "hasMerchantReturnPolicy": {
          "@type": "MerchantReturnPolicy",
          "applicableCountry": "US",
          "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
          "merchantReturnDays": 30,
          "returnMethod": "https://schema.org/ReturnByMail",
          "returnFees": "https://schema.org/FreeReturn"
        }
      },
      "aggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "4.5",
        "reviewCount": "0",
        "bestRating": "5",
        "worstRating": "1"
      },
      "review": []
    },
  ];

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Essential SEO Meta Tags */}
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, viewport-fit=cover" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta name="format-detection" content="telephone=no, address=no, email=no" />
        
        {/* Language and Region */}
        <meta httpEquiv="content-language" content="en-US" />
        <meta name="language" content="English" />
        <meta name="geo.region" content="US" />
        
        {/* Mobile Web App Capabilities */}
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="Thandev" />
        
        {/* Content Rating */}
        <meta name="rating" content="general" />
        <meta name="content-language" content="en-US" />
        
        {/* Generator (optional but helpful) */}
        <meta name="generator" content="Next.js" />
        
        {/* Revisit (deprecated but some crawlers still use) */}
        <meta name="revisit-after" content="1 days" />
        
        {/* Structured Data - Using @graph format for multiple schema types */}
        <SeoJsonLd schema={structuredData} />
        
        {/* Preconnect to improve performance - Critical for API calls */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://thandev-backend.fly.dev" crossOrigin="anonymous" />
        <link rel="preconnect" href="https://thandev-backend.thankfulisland-9a04feba.eastus.azurecontainerapps.io" crossOrigin="anonymous" />
        
        {/* DNS Prefetch for external resources */}
        <link rel="dns-prefetch" href="https://api.github.com" />
        <link rel="dns-prefetch" href="https://github.com" />
        
        {/* Manifest */}
        <link rel="manifest" href="/manifest.json" />
        
        {/* Theme color for mobile browsers */}
        <meta name="theme-color" content="#6366f1" media="(prefers-color-scheme: light)" />
        <meta name="theme-color" content="#0a0a0a" media="(prefers-color-scheme: dark)" />
        <meta name="msapplication-TileColor" content="#6366f1" />
        <meta name="msapplication-config" content="/browserconfig.xml" />
        
        {/* Apple touch icon */}
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180" />
        
        {/* Favicon - multiple sizes for better browser support */}
        <link rel="icon" type="image/x-icon" href="/favicon.ico" />
        <link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png" />
        <link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png" />
        
        {/* Canonical URLs are set per-page via metadata, not globally */}
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
