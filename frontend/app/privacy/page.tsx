import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Privacy Policy | Thandev',
  description: 'Privacy Policy for Thandev - How we collect, use, and protect your data',
  keywords: 'privacy policy, data protection, GDPR, thandev, security testing',
  openGraph: {
    title: 'Privacy Policy | Thandev',
    description: 'Privacy Policy for Thandev - How we collect, use, and protect your data',
    type: 'website',
    url: 'https://thandev.io/privacy',
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
                Last updated: January 30, 2026
              </p>
            </div>

            {/* Content */}
            <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-8 md:p-12">
              <div className="prose prose-lg max-w-none dark:prose-invert">
                
                {/* Overview */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Overview
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    This Privacy Policy describes how Thandev ("we," "our," or "us") collects, uses, stores, and protects information 
                    when you use our cybersecurity scanning and threat intelligence platform. By using our services, you agree to the 
                    collection and use of information in accordance with this policy. Scan targets (URLs/domains) and scan results are 
                    stored in our server database to provide you with access to your scan history and reports.
                  </p>
                </section>

                {/* Information We Collect */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Information We Collect
                  </h2>
                  
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    1. Account Information
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    When you create an account, we collect:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-6">
                    <li>Email address (required for account creation)</li>
                    <li>Username (required for account identification)</li>
                    <li>Full name (optional, if provided)</li>
                    <li>Authentication provider information (e.g., GitHub username and ID if you sign in with GitHub)</li>
                  </ul>

                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    2. Scan Data
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    When you use our scanning services, we collect and store the following information in our server database:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-6">
                    <li>Target URLs and domains you submit for scanning</li>
                    <li>Scan configurations and preferences (scan level, tool selections)</li>
                    <li>Scan execution timestamps (created, started, completed)</li>
                    <li>Scan results, including vulnerability findings, tool outputs, and generated reports</li>
                    <li>Scan status and error messages (if any)</li>
                    <li>Project information (project names, descriptions, associated URLs)</li>
                  </ul>

                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    3. Usage and Technical Logs
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We may automatically collect technical information when you access our platform:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-6">
                    <li>IP address (for security monitoring and abuse prevention)</li>
                    <li>User agent and browser type (for compatibility and debugging)</li>
                    <li>Request logs and API usage patterns (for service improvement)</li>
                    <li>Error logs (for troubleshooting and platform stability)</li>
                  </ul>
                  {/* TODO: Add specific log retention period (e.g., "Logs are retained for 30-90 days") */}

                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-3">
                    4. Cookies and Local Storage
                  </h3>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We use cookies and local storage for:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li>Session management and authentication (to keep you logged in)</li>
                    <li>User preferences and settings</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mt-4">
                    You can control cookies through your browser settings. Disabling cookies may affect your ability to use certain features of our platform.
                  </p>
                </section>

                {/* How We Use Information */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    How We Use Your Information
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We use the information we collect to:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2">
                    <li><strong>Provide our services:</strong> Execute security scans, generate reports, display scan history and results in your dashboard</li>
                    <li><strong>Maintain and secure the platform:</strong> Debug issues, monitor for abuse and security threats, prevent unauthorized access</li>
                    <li><strong>Communications:</strong> Send product updates, security notifications, and respond to support requests (if you contact us)</li>
                    <li><strong>Service improvement:</strong> Analyze usage patterns to enhance features and user experience</li>
                    <li><strong>Legal compliance:</strong> Comply with applicable laws, regulations, and legal processes</li>
                  </ul>
                </section>

                {/* Information Sharing */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Information Sharing and Disclosure
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We do not sell your personal information. We may share your information only in the following limited circumstances:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-4">
                    <li><strong>Service providers and subprocessors:</strong> We may share data with trusted third-party service providers who assist in operating our platform, such as:
                      <ul className="list-disc pl-6 mt-2 space-y-1">
                        <li>Hosting and cloud infrastructure providers</li>
                        <li>Database and storage services</li>
                        {/* TODO: Add specific subprocessor list (e.g., Azure, Supabase, Vercel) */}
                        {/* TODO: Add analytics providers if used */}
                        {/* TODO: Add email service providers if used */}
                      </ul>
                    </li>
                    <li><strong>Legal compliance:</strong> When required by law, court order, or government request, or to protect our rights, property, or safety</li>
                    <li><strong>Business transfers:</strong> In connection with a merger, acquisition, or sale of assets, your information may be transferred to the acquiring entity</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    All service providers are contractually obligated to protect your information and use it only for the purposes we specify.
                  </p>
                </section>

                {/* Data Retention */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Data Retention
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    We retain your information as follows:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-4">
                    <li><strong>Account data and scan results:</strong> We retain your account information and scan data while your account is active. You can request deletion of your account and associated data at any time.</li>
                    <li><strong>Deletion requests:</strong> Upon account deletion or data deletion request, we will delete your personal information and scan data from our systems, subject to any legal retention requirements.</li>
                    {/* TODO: Add specific log retention period (e.g., "Technical logs are retained for 30-90 days") */}
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We retain information only for as long as necessary to fulfill the purposes outlined in this Privacy Policy, unless a longer retention period is required or permitted by law.
                  </p>
                </section>

                {/* Data Security */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Data Security
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We implement appropriate technical and organizational measures to protect your information against unauthorized access, 
                    alteration, disclosure, or destruction. These measures include:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mt-4">
                    <li>Encryption in transit (HTTPS/TLS) for all data transmission</li>
                    <li>Access controls and authentication mechanisms</li>
                    <li>Least privilege access principles for our team</li>
                    <li>Security monitoring and incident response procedures</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mt-4">
                    However, no method of transmission over the internet or electronic storage is 100% secure. While we strive to protect 
                    your information, we cannot guarantee absolute security.
                  </p>
                </section>

                {/* International Users */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    International Users
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Your information may be processed and stored in locations where our service providers operate, which may be outside 
                    your country of residence. By using our services, you consent to the transfer of your information to these locations. 
                    We ensure that appropriate safeguards are in place to protect your information in accordance with this Privacy Policy.
                  </p>
                  {/* TODO: Specify primary hosting region(s) (e.g., "Our primary infrastructure is hosted in [region]") */}
                </section>

                {/* Your Rights */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Your Choices and Rights
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    Depending on your location, you may have the following rights regarding your personal information:
                  </p>
                  <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 space-y-2 mb-4">
                    <li><strong>Access:</strong> Request access to your personal information and scan data</li>
                    <li><strong>Correction:</strong> Request correction of inaccurate or incomplete information</li>
                    <li><strong>Deletion:</strong> Request deletion of your personal information and scan data</li>
                    <li><strong>Data portability:</strong> Request a copy of your data in a portable format</li>
                    <li><strong>Objection:</strong> Object to certain processing activities (where applicable)</li>
                    <li><strong>Withdrawal of consent:</strong> Withdraw consent where processing is based on consent</li>
                  </ul>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                    If you are located in the European Economic Area (EEA) or United Kingdom, you have additional rights under the 
                    General Data Protection Regulation (GDPR), including the right to restrict processing and the right to lodge 
                    a complaint with a supervisory authority.
                  </p>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    To exercise these rights, please contact us at <strong>help@thandev.io</strong>. We will respond to your request 
                    within a reasonable timeframe and in accordance with applicable law.
                  </p>
                </section>

                {/* Children's Privacy */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Children's Privacy
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    Our services are not intended for children under the age of {/* TODO: Confirm age threshold (13 or 16) */}13. We do not 
                    knowingly collect personal information from children. If you become aware that a child has provided us with personal 
                    information, please contact us immediately at <strong>help@thandev.io</strong>, and we will take steps to delete such information.
                  </p>
                </section>

                {/* Changes to Privacy Policy */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Changes to This Privacy Policy
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    We may update this Privacy Policy from time to time to reflect changes in our practices or for other operational, 
                    legal, or regulatory reasons. We will notify you of any material changes by posting the updated Privacy Policy on 
                    this page and updating the "Last updated" date. Your continued use of our services after such changes constitutes 
                    acceptance of the updated Privacy Policy.
                  </p>
                </section>

                {/* Contact Information */}
                <section className="mb-8">
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                    Contact Us
                  </h2>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    If you have any questions, concerns, or requests regarding this Privacy Policy or our data practices, please contact us:
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
