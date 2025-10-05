import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Documentation | Thandev',
  description: 'Complete documentation for Thandev security testing platform',
  keywords: ['documentation', 'thandev', 'security testing', 'help', 'guide'],
  openGraph: {
    title: 'Documentation | Thandev',
    description: 'Complete documentation for Thandev security testing platform',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Documentation | Thandev',
    description: 'Complete documentation for Thandev security testing platform',
  },
};

export default function DocsPage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-8">
          Documentation
        </h1>
        <div className="prose prose-lg max-w-none">
          <p className="text-gray-600 dark:text-gray-300">
            Documentation is coming soon. This page will contain comprehensive guides and help for using the Thandev platform.
          </p>
        </div>
      </div>
    </div>
  );
}