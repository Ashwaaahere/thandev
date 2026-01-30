import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy | Thandev',
  description: 'Privacy Policy for Thandev - How we collect, use, and protect your data',
  keywords: 'privacy policy, data protection, GDPR, thandev, security testing',
  openGraph: {
    title: 'Privacy Policy | Thandev',
    description: 'Privacy Policy for Thandev - How we collect, use, and protect your data',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Privacy Policy | Thandev',
    description: 'Privacy Policy for Thandev - How we collect, use, and protect your data',
  },
  alternates: {
    canonical: 'https://thandev.io/privacy',
  },
}

const privacyStructuredData = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Privacy Policy",
  "description": "Privacy Policy for Thandev security testing platform",
  "url": "/privacy",
  "isPartOf": {
    "@type": "WebSite",
    "name": "Thandev",
    "url": "/"
  }
}

export default function PrivacyPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(privacyStructuredData) }}
      />
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
        <div className="container mx-auto px-4 py-16">
          <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="text-center mb-12">
              <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-4">
                Privacy Policy
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
                    At Thandev, we are committed to protecting your privacy and ensuring the security of your personal information. 
                    This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our 
                    security testing platform and services.
                  </p>
                </section>

                {/* Information We Collect */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Information We Collect
                  </h2>
                  
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    Personal Information
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We may collect the following types of personal information:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-6">
                    <li>Name and email address when you create an account</li>
                    <li>Profile information you choose to provide</li>
                    <li>Communication preferences</li>
                    <li>Payment information (processed securely through third-party providers)</li>
                  </ul>

                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    Usage Information
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We automatically collect certain information about your use of our services:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-6">
                    <li>IP address and device information</li>
                    <li>Browser type and version</li>
                    <li>Pages visited and time spent on our platform</li>
                    <li>Scan history and results (stored locally on your device)</li>
                    <li>Error logs and performance data</li>
                  </ul>

                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    Scan Data
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    When you use our scanning services, we may collect:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>URLs and domains you choose to scan</li>
                    <li>Scan results and vulnerability data</li>
                    <li>Scan configuration preferences</li>
                    <li>Device fingerprinting data for rate limiting</li>
                  </ul>
                </section>

                {/* How We Use Information */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    How We Use Your Information
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We use the collected information for the following purposes:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Providing and maintaining our security testing services</li>
                    <li>Processing your requests and transactions</li>
                    <li>Improving our platform and developing new features</li>
                    <li>Communicating with you about updates and important information</li>
                    <li>Enforcing our Terms of Service and preventing abuse</li>
                    <li>Complying with legal obligations</li>
                    <li>Analyzing usage patterns to enhance user experience</li>
                  </ul>
                </section>

                {/* Information Sharing */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Information Sharing and Disclosure
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We do not sell, trade, or rent your personal information to third parties. We may share your information in the following circumstances:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>With your explicit consent</li>
                    <li>To comply with legal obligations or court orders</li>
                    <li>To protect our rights, property, or safety</li>
                    <li>With trusted service providers who assist in operating our platform</li>
                    <li>In connection with a business transfer or acquisition</li>
                  </ul>
                </section>

                {/* Data Security */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Data Security
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We implement appropriate technical and organizational measures to protect your personal information against 
                    unauthorized access, alteration, disclosure, or destruction. However, no method of transmission over the 
                    internet or electronic storage is 100% secure, and we cannot guarantee absolute security.
                  </p>
                </section>

                {/* Data Retention */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Data Retention
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We retain your personal information only for as long as necessary to fulfill the purposes outlined in this 
                    Privacy Policy, unless a longer retention period is required or permitted by law. Scan data is typically 
                    stored locally on your device and can be cleared at any time.
                  </p>
                </section>

                {/* Your Rights */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Your Rights
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    Depending on your location, you may have the following rights regarding your personal information:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Access to your personal information</li>
                    <li>Correction of inaccurate or incomplete information</li>
                    <li>Deletion of your personal information</li>
                    <li>Restriction of processing</li>
                    <li>Data portability</li>
                    <li>Objection to processing</li>
                    <li>Withdrawal of consent</li>
                  </ul>
                </section>

                {/* Cookies and Tracking */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Cookies and Tracking Technologies
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We use cookies and similar tracking technologies to enhance your experience on our platform. You can control 
                    cookie preferences through your browser settings. Some features may not function properly if cookies are disabled.
                  </p>
                </section>

                {/* Third-Party Services */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Third-Party Services
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Our platform may integrate with third-party services for analytics, payment processing, and other functionalities. 
                    These services have their own privacy policies, and we encourage you to review them.
                  </p>
                </section>

                {/* Children's Privacy */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Children's Privacy
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Our services are not intended for children under 13 years of age. We do not knowingly collect personal 
                    information from children under 13. If you become aware that a child has provided us with personal information, 
                    please contact us immediately.
                  </p>
                </section>

                {/* Changes to Privacy Policy */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Changes to This Privacy Policy
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We may update this Privacy Policy from time to time. We will notify you of any material changes by posting 
                    the new Privacy Policy on our website and updating the "Last updated" date. Your continued use of our services 
                    after such changes constitutes acceptance of the updated Privacy Policy.
                  </p>
                </section>

                {/* Contact Information */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Contact Us
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    If you have any questions about this Privacy Policy or our data practices, please contact us:
                  </p>
                  <div className="mt-4 p-4 bg-gray-50 dark:bg-slate-700 rounded-lg">
                    <p className="text-gray-700 dark:text-gray-300">
                      <strong>Email:</strong> help@thandev.io<br />
                      <strong>Website:</strong> https://thandev.io
                    </p>
                  </div>
                </section>

              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}




