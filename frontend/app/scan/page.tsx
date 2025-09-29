import ScanClient from "@/components/Scan/ScanClient";
import ScanLimiter from "@/components/Scan/ScanLimiter";

export const metadata = {
  title: "Surface Scan - Vulnerability Assessment Tool",
  description: "Professional surface scan tool for vulnerability scan, penetration testing, and security analysis. Scan websites for common vulnerabilities, security misconfigurations, and potential threats.",
  keywords: [
    "surface scan tool",
    "vulnerability scan",
    "penetration testing",
    "security analysis",
    "website scan",
    "security testing",
    "vulnerability scan",
    "web application security",
    "security audit",
    "threat detection"
  ],
  openGraph: {
    title: "Surface Scan - Vulnerability Assessment Tool",
    description: "Professional surface scan tool for vulnerability scan, penetration testing, and security analysis.",
    type: "website",
    url: "https://thandev.com/scan",
    images: [
      {
        url: "/og-scan.png",
        width: 1200,
        height: 630,
        alt: "Thandev Surface Scan",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Surface Scan - Vulnerability Assessment Tool",
    description: "Professional surface scan tool for vulnerability scan, penetration testing, and security analysis.",
    images: ["/og-scan.png"],
  },
  alternates: {
    canonical: "/scan",
  },
};

export default function ScanPage() {
  // Static structured data for SEO
  const scanStructuredData = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    "name": "Thandev Surface Scan",
    "description": "Professional surface scan tool for vulnerability scan and penetration testing",
    "url": "https://thandev.com/scan",
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
      "Vulnerability scanning",
      "Security assessment",
      "Penetration testing",
      "Threat detection",
      "Security reporting",
      "Real-time analysis"
    ]
  };

  return (
    <>
      {/* Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(scanStructuredData),
        }}
      />
      
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Hero section */}
        <section className="mb-12 text-center">
          <div className="mb-6">
            <h1 className="text-4xl font-bold text-[var(--fg)] mb-4">
              Surface Scan
            </h1>
            <p className="text-lg text-[var(--muted)] max-w-2xl mx-auto">
              Professional vulnerability scan and penetration testing tool. Scan websites for security vulnerabilities, misconfigurations, and potential threats.
            </p>
          </div>
        </section>

               {/* Client-side scanner with limiter */}
               <ScanLimiter>
                 <ScanClient />
               </ScanLimiter>
      </main>
    </>
  );
}
