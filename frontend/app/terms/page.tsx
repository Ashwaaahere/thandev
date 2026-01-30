import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Terms of Service | Thandev',
  description: 'Terms of Service for Thandev - Your comprehensive security testing platform',
  keywords: 'terms of service, legal, thandev, security testing, vulnerability assessment',
  openGraph: {
    title: 'Terms of Service | Thandev',
    description: 'Terms of Service for Thandev - Your comprehensive security testing platform',
    type: 'website',
    url: 'https://thandev.io/terms',
  },
  twitter: {
    card: 'summary',
    title: 'Terms of Service | Thandev',
    description: 'Terms of Service for Thandev - Your comprehensive security testing platform',
  },
  alternates: {
    canonical: 'https://thandev.io/terms',
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
                Last updated: January 30, 2025
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
                    Welcome to Thandev. These Terms of Service ("Terms") govern your access to and use of our cybersecurity scanning 
                    and threat intelligence platform and services (collectively, the "Service"). By accessing or using our Service, 
                    you agree to be bound by these Terms. If you do not agree to these Terms, you may not use our Service.
                  </p>
                </section>

                {/* Acceptance of Terms */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    1. Acceptance of Terms
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    By creating an account, accessing, or using Thandev, you acknowledge that you have read, understood, and agree to 
                    be bound by these Terms and our Privacy Policy. If you are using the Service on behalf of an organization, you 
                    represent and warrant that you have authority to bind that organization to these Terms.
                  </p>
                </section>

                {/* Service Description */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    2. Service Description
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    Thandev provides a cybersecurity scanning and threat intelligence platform that includes:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-4">
                    <li>Automated security scanning and vulnerability assessment</li>
                    <li>Threat intelligence and CVE tracking</li>
                    <li>Security news aggregation</li>
                    <li>Exploit database access</li>
                    <li>Scan reporting and dashboard features</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    <strong>Beta Service:</strong> Thandev is currently in beta. Features, functionality, and service availability 
                    may change without notice. We do not guarantee uninterrupted access or that the Service will be error-free. 
                    Service availability and performance are provided on a "best effort" basis during the beta period.
                  </p>
                </section>

                {/* Authorization and Acceptable Use */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    3. Authorization and Acceptable Use
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    <strong>CRITICAL:</strong> You may only use Thandev to scan systems, networks, or applications that you own, 
                    operate, or have explicit written permission to test. Unauthorized scanning is illegal and may result in 
                    criminal or civil liability.
                  </p>
                  
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    Permitted Use
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    You may use Thandev only for:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-6">
                    <li>Scanning systems you own or operate</li>
                    <li>Scanning systems for which you have explicit written authorization from the owner</li>
                    <li>Legitimate security testing and vulnerability assessment purposes</li>
                  </ul>

                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    Prohibited Activities
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    You are strictly prohibited from using Thandev to:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Scan, probe, or test any system, network, or application without explicit authorization from the owner</li>
                    <li>Attempt to gain unauthorized access to any system, network, or data</li>
                    <li>Target government systems, critical infrastructure, or third-party services without explicit authorization</li>
                    <li>Perform credential stuffing, brute force attacks, or password cracking</li>
                    <li>Distribute, deliver, or deploy malware, ransomware, or malicious code</li>
                    <li>Steal, exfiltrate, or misuse data obtained through scanning</li>
                    <li>Exploit vulnerabilities discovered through scanning for malicious purposes</li>
                    <li>Interfere with, disrupt, or damage the Service or any third-party systems</li>
                    <li>Bypass or circumvent security controls or access restrictions on the Service</li>
                    <li>Use the Service for any illegal activity or in violation of any applicable laws or regulations</li>
                    <li>Violate the rights of others, including intellectual property rights, privacy rights, or contractual obligations</li>
                    <li>Impersonate others or provide false information when creating an account</li>
                  </ul>
                </section>

                {/* User Responsibilities */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    4. User Responsibilities
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    You are solely responsible for:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li><strong>Authorization:</strong> Obtaining and maintaining proper authorization before scanning any target</li>
                    <li><strong>Accuracy:</strong> Ensuring that target URLs, domains, and scan configurations you submit are accurate and authorized</li>
                    <li><strong>Compliance:</strong> Complying with all applicable laws, regulations, and third-party terms of service</li>
                    <li><strong>Account security:</strong> Maintaining the confidentiality of your account credentials and promptly notifying us of any unauthorized access</li>
                    <li><strong>Use of results:</strong> How you interpret, act upon, or share scan results and findings</li>
                    <li><strong>False positives/negatives:</strong> Understanding that scan results may contain false positives (incorrectly identified vulnerabilities) or false negatives (missed vulnerabilities)</li>
                    <li><strong>Professional judgment:</strong> Using professional security expertise to validate findings before taking action</li>
                  </ul>
                </section>

                {/* Scan Results Disclaimer */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    5. Scan Results Disclaimer
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    <strong>Important:</strong> Scan results and findings provided by Thandev are informational only and provided on a 
                    "best effort" basis. You acknowledge and agree that:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Scan results do not guarantee the security of your systems</li>
                    <li>Scans may miss vulnerabilities (false negatives)</li>
                    <li>Scans may report vulnerabilities that do not exist (false positives)</li>
                    <li>Tool outputs may contain errors, inaccuracies, or outdated information</li>
                    <li>Scan results are not professional security advice, security audits, or penetration testing reports</li>
                    <li>You should not rely solely on automated scan results for security decisions</li>
                    <li>Thandev is not responsible for any actions you take based on scan results</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mt-4">
                    For comprehensive security assessments, consult qualified security professionals and conduct manual testing in addition 
                    to automated scanning.
                  </p>
                </section>

                {/* Accounts */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    6. Accounts
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    To use certain features of the Service, you must create an account. You agree to:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-4">
                    <li>Provide accurate, current, and complete information when creating your account</li>
                    <li>Maintain and update your account information to keep it accurate</li>
                    <li>Maintain the security of your account credentials</li>
                    <li>Accept responsibility for all activities that occur under your account</li>
                    <li>Notify us immediately of any unauthorized use of your account</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We reserve the right to suspend or terminate your account at any time, with or without notice, if you violate 
                    these Terms, engage in prohibited activities, pose a security risk, or for any other reason we deem necessary to 
                    protect the Service, other users, or third parties.
                  </p>
                </section>

                {/* Data and Content */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    7. Data and Content
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    <strong>Your Content:</strong> You retain ownership of any target URLs, domains, and scan configurations you submit 
                    to the Service ("Your Content"). You grant Thandev a limited, non-exclusive, worldwide license to use, store, and 
                    process Your Content solely to provide the Service to you. Scan results and reports generated by the Service are 
                    stored in our server database and are associated with your account.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    <strong>Our Content:</strong> The Service, including all software, user interfaces, documentation, and content 
                    provided by Thandev (excluding Your Content), is owned by Thandev and protected by intellectual property laws.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    You may not copy, modify, distribute, sell, or lease any part of the Service or our content without our prior 
                    written consent.
                  </p>
                </section>

                {/* Third-Party Tools */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    8. Third-Party Tools
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    Thandev uses third-party open-source security testing tools and templates to perform scans. These tools are used 
                    under their respective open-source licenses. Tool names and trademarks belong to their respective owners.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    For a complete list of tools, their licenses, and attribution, please see our{" "}
                    <a href="/docs/tool-catalog" className="text-blue-600 dark:text-blue-400 hover:underline" target="_blank" rel="noopener noreferrer">
                      Tool Catalog
                    </a>.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Thandev is not responsible for the accuracy, reliability, or performance of third-party tools. Use of these tools 
                    is subject to their respective license terms and limitations.
                  </p>
                </section>

                {/* Intellectual Property */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    9. Intellectual Property
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    The Thandev platform, including its software, user interfaces, branding, logos, and documentation, is the exclusive 
                    property of Thandev and is protected by copyright, trademark, and other intellectual property laws. You may not use 
                    our trademarks, logos, or branding without our prior written permission.
                  </p>
                </section>

                {/* Limitation of Liability */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    10. Limitation of Liability
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THANDEV AND ITS AFFILIATES, OFFICERS, DIRECTORS, EMPLOYEES, AND 
                    AGENTS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT 
                    NOT LIMITED TO LOSS OF PROFITS, DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES, ARISING OUT OF OR RELATING TO YOUR 
                    USE OF OR INABILITY TO USE THE SERVICE.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    IN NO EVENT SHALL THANDEV'S TOTAL LIABILITY TO YOU FOR ALL CLAIMS ARISING OUT OF OR RELATING TO THE SERVICE EXCEED 
                    {/* TODO: Add jurisdiction-specific liability cap if required (e.g., "$100 USD" or "the amount you paid to Thandev in the 12 months preceding the claim") */}
                    THE AMOUNT YOU PAID TO THANDEV IN THE 12 MONTHS PRECEDING THE CLAIM, OR $100 USD, WHICHEVER IS GREATER.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Some jurisdictions do not allow the exclusion or limitation of certain damages, so some of the above limitations 
                    may not apply to you.
                  </p>
                </section>

                {/* Indemnification */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    11. Indemnification
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    You agree to indemnify, defend, and hold harmless Thandev and its affiliates, officers, directors, employees, and 
                    agents from and against any and all claims, damages, obligations, losses, liabilities, costs, and expenses 
                    (including reasonable attorneys' fees) arising out of or relating to: (a) your use of the Service; (b) your violation 
                    of these Terms; (c) your violation of any third-party rights, including unauthorized scanning or access; (d) any 
                    content you submit to the Service; or (e) your violation of any applicable laws or regulations.
                  </p>
                </section>

                {/* Governing Law */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    12. Governing Law and Dispute Resolution
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    {/* TODO: Founder to specify jurisdiction (e.g., "These Terms shall be governed by and construed in accordance with the laws of [State/Country], without regard to its conflict of law provisions.") */}
                    These Terms shall be governed by and construed in accordance with applicable laws. Any disputes arising out of or 
                    relating to these Terms or the Service shall be resolved through binding arbitration or in the courts of 
                    {/* TODO: Specify venue (e.g., "[City, State/Country]") */}the appropriate jurisdiction.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    If any provision of these Terms is found to be unenforceable or invalid, that provision shall be limited or 
                    eliminated to the minimum extent necessary, and the remaining provisions shall remain in full force and effect.
                  </p>
                </section>

                {/* Changes to Terms */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    13. Changes to Terms
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We reserve the right to modify these Terms at any time. We will notify users of any material changes by posting 
                    the updated Terms on this page and updating the "Last updated" date. Your continued use of the Service after such 
                    changes constitutes acceptance of the updated Terms. If you do not agree to the updated Terms, you must stop using 
                    the Service and may delete your account.
                  </p>
                </section>

                {/* Contact Information */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    14. Contact Information
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    If you have any questions about these Terms, please contact us:
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
