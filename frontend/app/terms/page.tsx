import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service | Thandev',
  description: 'Terms of Service for Thandev - Your comprehensive security testing platform',
  keywords: 'terms of service, legal, thandev, security testing, vulnerability assessment',
  openGraph: {
    title: 'Terms of Service | Thandev',
    description: 'Terms of Service for Thandev - Your comprehensive security testing platform',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Terms of Service | Thandev',
    description: 'Terms of Service for Thandev - Your comprehensive security testing platform',
  },
  alternates: {
    canonical: '/terms',
  },
}

const termsStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Terms of Service",
  "description": "Terms of Service for Thandev security testing platform",
  "url": "/terms",
  "isPartOf": {
    "@type": "WebSite",
    "name": "Thandev",
    "url": "/"
  }
}

export default function TermsPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(termsStructuredData) }}
      />
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="text-center mb-12">
              <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-4">
                Terms of Service
              </h1>
              <p className="text-lg text-gray-600 dark:text-gray-300">
                Last updated: {new Date().toLocaleDateString()}
              </p>
            </div>

            {/* Content */}
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-8 md:p-12">
              <div className="prose prose-lg max-w-none dark:prose-invert">
                
                {/* Introduction */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Introduction
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Welcome to Thandev. These Terms of Service ("Terms") govern your use of our security testing platform 
                    and services. By accessing or using our platform, you agree to be bound by these Terms.
                  </p>
                </section>

                {/* Acceptance of Terms */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Acceptance of Terms
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    By using Thandev, you acknowledge that you have read, understood, and agree to be bound by these Terms. 
                    If you do not agree to these Terms, please do not use our services.
                  </p>
                </section>

                {/* Service Description */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Service Description
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    Thandev provides comprehensive security testing services including:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Surface scanning and vulnerability assessment</li>
                    <li>Security testing automation tools</li>
                    <li>Exploit database and security intelligence</li>
                    <li>News and updates on security vulnerabilities</li>
                    <li>Educational resources and documentation</li>
                  </ul>
                </section>

                {/* User Responsibilities */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    User Responsibilities
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    As a user of Thandev, you agree to:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Use our services only for legitimate security testing purposes</li>
                    <li>Not attempt to scan systems you do not own or have explicit permission to test</li>
                    <li>Respect rate limits and usage restrictions</li>
                    <li>Provide accurate information when creating an account</li>
                    <li>Not use our services for malicious or illegal activities</li>
                    <li>Comply with all applicable laws and regulations</li>
                  </ul>
                </section>

                {/* Prohibited Uses */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Prohibited Uses
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    You may not use Thandev for:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Unauthorized scanning of third-party systems</li>
                    <li>Any illegal or malicious activities</li>
                    <li>Attempting to circumvent security measures</li>
                    <li>Distributing malware or malicious code</li>
                    <li>Violating any applicable laws or regulations</li>
                    <li>Interfering with the proper functioning of our services</li>
                  </ul>
                </section>

                {/* Service Availability */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Service Availability
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We strive to maintain high availability of our services, but we do not guarantee uninterrupted access. 
                    We reserve the right to modify, suspend, or discontinue any part of our services at any time.
                  </p>
                </section>

                {/* Limitation of Liability */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Limitation of Liability
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    To the maximum extent permitted by law, Thandev shall not be liable for any indirect, incidental, 
                    special, consequential, or punitive damages arising out of or relating to your use of our services.
                  </p>
                </section>

                {/* Changes to Terms */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Changes to Terms
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We reserve the right to modify these Terms at any time. We will notify users of any material changes 
                    by posting the new Terms on our website. Your continued use of our services after such changes 
                    constitutes acceptance of the new Terms.
                  </p>
                </section>

                {/* Contact Information */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Contact Information
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    If you have any questions about these Terms, please contact us at:
                  </p>
                  <div className="mt-4 p-4 bg-gray-50 dark:bg-slate-700 rounded-lg">
                    <p className="text-gray-700 dark:text-gray-300">
                      <strong>Email:</strong> legal@thandev.com<br />
                      <strong>Website:</strong> https://thandev.com<br />
                      <strong>Address:</strong> [Your Business Address]
                    </p>
                  </div>
                </section>

                {/* Disclaimer */}
                <div className="mt-12 p-6 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    <strong>Note:</strong> This is a demo Terms of Service page. Please replace this content with your 
                    actual legal terms and consult with a legal professional before publishing.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}




