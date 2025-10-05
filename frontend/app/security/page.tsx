import { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Security Policy | Thandev',
  description: 'Security policy and vulnerability disclosure information for Thandev',
  keywords: 'security policy, vulnerability disclosure, security contact, thandev',
  robots: 'noindex, nofollow',
  openGraph: {
    title: 'Security Policy | Thandev',
    description: 'Security policy and vulnerability disclosure information for Thandev',
    type: 'website',
  },
  alternates: {
    canonical: '/security',
  },
}

export default function SecurityPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="text-center mb-12">
            <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-4">
              Security Policy
            </h1>
            <p className="text-lg text-gray-600 dark:text-gray-300">
              Responsible disclosure and security practices
            </p>
          </div>

          {/* Content */}
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-8 md:p-12">
            <div className="prose prose-lg max-w-none dark:prose-invert">
              
              {/* Introduction */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  Security First
                </h2>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                  At Thandev, we take security seriously. As a security testing platform, 
                  we understand the importance of maintaining the highest security standards 
                  and practicing responsible disclosure.
                </p>
              </section>

              {/* Reporting Vulnerabilities */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  Reporting Security Vulnerabilities
                </h2>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                  If you discover a security vulnerability in our platform, please report it 
                  responsibly. We appreciate your help in keeping our platform secure.
                </p>
                
                <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6 mb-6">
                  <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-100 mb-3">
                    How to Report
                  </h3>
                  <ul className="space-y-2 text-blue-800 dark:text-blue-200">
                    <li><strong>Email:</strong> security@thandev.com</li>
                    <li><strong>Response Time:</strong> We will respond within 48 hours</li>
                    <li><strong>Confidentiality:</strong> Your report will be kept confidential</li>
                    <li><strong>Recognition:</strong> We maintain a security acknowledgments page</li>
                  </ul>
                </div>

                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-red-900 dark:text-red-100 mb-3">
                    Important: Do Not
                  </h3>
                  <ul className="space-y-2 text-red-800 dark:text-red-200">
                    <li>• Report vulnerabilities through public channels</li>
                    <li>• Access or modify data that doesn't belong to you</li>
                    <li>• Disrupt our services or other users' data</li>
                    <li>• Use automated tools that may cause system instability</li>
                  </ul>
                </div>
              </section>

              {/* What We're Looking For */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  What We're Looking For
                </h2>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                      In Scope
                    </h3>
                    <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                      <li>• Cross-site scripting (XSS)</li>
                      <li>• SQL injection</li>
                      <li>• Cross-site request forgery (CSRF)</li>
                      <li>• Authentication bypass</li>
                      <li>• Authorization flaws</li>
                      <li>• Information disclosure</li>
                      <li>• Server-side request forgery (SSRF)</li>
                      <li>• Remote code execution</li>
                    </ul>
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
                      Out of Scope
                    </h3>
                    <ul className="space-y-2 text-gray-700 dark:text-gray-300">
                      <li>• Social engineering attacks</li>
                      <li>• Physical security issues</li>
                      <li>• Denial of service attacks</li>
                      <li>• Issues in third-party services</li>
                      <li>• Spam or social engineering</li>
                      <li>• Issues requiring physical access</li>
                      <li>• Vulnerabilities in dependencies</li>
                    </ul>
                  </div>
                </div>
              </section>

              {/* Our Process */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  Our Security Process
                </h2>
                <div className="space-y-4">
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-semibold">1</div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">Initial Response</h3>
                      <p className="text-gray-700 dark:text-gray-300">We'll acknowledge your report within 48 hours</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-semibold">2</div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">Investigation</h3>
                      <p className="text-gray-700 dark:text-gray-300">We'll investigate and validate the vulnerability</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-semibold">3</div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">Fix Development</h3>
                      <p className="text-gray-700 dark:text-gray-300">We'll develop and test a fix for the vulnerability</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-500 text-white rounded-full flex items-center justify-center font-semibold">4</div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">Deployment</h3>
                      <p className="text-gray-700 dark:text-gray-300">We'll deploy the fix and notify you of the resolution</p>
                    </div>
                  </div>
                </div>
              </section>

              {/* Recognition */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  Recognition
                </h2>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
                  We maintain a security acknowledgments page to recognize security researchers 
                  who help us keep our platform secure. If you would like to be recognized, 
                  please let us know when you submit your report.
                </p>
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-green-900 dark:text-green-100 mb-2">
                    Hall of Fame
                  </h3>
                  <p className="text-green-800 dark:text-green-200">
                    Security researchers who have helped us improve our platform will be 
                    listed on our acknowledgments page with their permission.
                  </p>
                </div>
              </section>

              {/* Contact Information */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  Contact Information
                </h2>
                <div className="bg-gray-50 dark:bg-slate-700 rounded-lg p-6">
                  <p className="text-gray-700 dark:text-gray-300 mb-4">
                    For security-related inquiries, please contact us at:
                  </p>
                  <div className="space-y-2">
                    <p className="text-gray-700 dark:text-gray-300">
                      <strong>Email:</strong> security@thandev.com
                    </p>
                    <p className="text-gray-700 dark:text-gray-300">
                      <strong>PGP Key:</strong> Available upon request
                    </p>
                    <p className="text-gray-700 dark:text-gray-300">
                      <strong>Response Time:</strong> Within 48 hours
                    </p>
                  </div>
                </div>
              </section>

              {/* Legal */}
              <section className="mb-8">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                  Legal
                </h2>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                  By participating in our security program, you agree to comply with all 
                  applicable laws and regulations. We reserve the right to modify this 
                  security policy at any time.
                </p>
              </section>

            </div>
          </div>
        </div>
      </div>
    </div>
  )
}




