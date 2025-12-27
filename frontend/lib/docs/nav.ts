export interface NavItem {
  title: string;
  href: string;
  section: string;
  shortDescription: string;
  keywords: string[];
}

export const docsNav: NavItem[] = [
  // Start Here
  {
    title: 'Overview',
    href: '/docs/overview',
    section: 'Start Here',
    shortDescription: 'What Thandev is and what it does',
    keywords: ['overview', 'introduction', 'what is thandev', 'platform', 'security testing'],
  },
  {
    title: 'Getting Started',
    href: '/docs/getting-started',
    section: 'Start Here',
    shortDescription: 'Account approval and first scan flow',
    keywords: ['getting started', 'first scan', 'account', 'approval', 'onboarding', 'setup'],
  },
  {
    title: 'Domain Verification',
    href: '/docs/domain-verification',
    section: 'Start Here',
    shortDescription: 'DNS TXT verification and rules',
    keywords: ['domain', 'verification', 'dns', 'txt', 'ownership', 'root domain'],
  },
  // Using Thandev
  {
    title: 'Running Scans',
    href: '/docs/running-scans',
    section: 'Using Thandev',
    shortDescription: 'Basic/Pro/Advanced scans and scan lifecycle',
    keywords: ['scans', 'scanning', 'basic', 'pro', 'advanced', 'scan levels', 'lifecycle'],
  },
  {
    title: 'Understanding Findings',
    href: '/docs/understanding-findings',
    section: 'Using Thandev',
    shortDescription: 'Severities, false positives, and what to do',
    keywords: ['findings', 'vulnerabilities', 'severity', 'false positives', 'remediation'],
  },
  {
    title: 'Reports',
    href: '/docs/reports',
    section: 'Using Thandev',
    shortDescription: 'Executive vs Full PDF reports and sharing safely',
    keywords: ['reports', 'pdf', 'executive', 'full report', 'sharing', 'export'],
  },
  {
    title: 'Plans & Limits',
    href: '/docs/plans-limits',
    section: 'Using Thandev',
    shortDescription: 'Plans, quotas, concurrency, and fair use',
    keywords: ['plans', 'limits', 'quotas', 'pricing', 'concurrency', 'fair use'],
  },
  {
    title: 'Tool Catalog',
    href: '/docs/tool-catalog',
    section: 'Using Thandev',
    shortDescription: 'All security tools covered and their limits',
    keywords: ['tools', 'nuclei', 'nmap', 'sslscan', 'httpx', 'ffuf', 'dalfox', 'sqlmap'],
  },
  {
    title: 'FAQ',
    href: '/docs/faq',
    section: 'Using Thandev',
    shortDescription: 'General troubleshooting and common questions',
    keywords: ['faq', 'troubleshooting', 'help', 'questions', 'support'],
  },
  // Trust & Legal
  {
    title: 'Security Overview',
    href: '/docs/security-overview',
    section: 'Trust & Legal',
    shortDescription: 'High-level security posture and CIA triad summary',
    keywords: ['security', 'posture', 'cia', 'confidentiality', 'integrity', 'availability'],
  },
  {
    title: 'Responsible Disclosure',
    href: '/docs/responsible-disclosure',
    section: 'Trust & Legal',
    shortDescription: 'How to report a vulnerability in Thandev',
    keywords: ['responsible disclosure', 'vulnerability', 'bug report', 'security issue'],
  },
  {
    title: 'Acceptable Use',
    href: '/docs/acceptable-use',
    section: 'Trust & Legal',
    shortDescription: 'No unauthorized scanning and abuse handling',
    keywords: ['acceptable use', 'terms', 'abuse', 'unauthorized', 'policy'],
  },
  {
    title: 'Privacy',
    href: '/docs/privacy',
    section: 'Trust & Legal',
    shortDescription: 'Data collected, storage, retention, and third parties',
    keywords: ['privacy', 'data', 'collection', 'storage', 'retention', 'gdpr'],
  },
  {
    title: 'Terms of Service',
    href: '/docs/terms',
    section: 'Trust & Legal',
    shortDescription: 'Terms of service - simple but protective',
    keywords: ['terms', 'tos', 'terms of service', 'legal', 'agreement'],
  },
];

export const docsSections = ['Start Here', 'Using Thandev', 'Trust & Legal'] as const;

export function getNavItemByHref(href: string): NavItem | undefined {
  return docsNav.find(item => item.href === href);
}

export function getNavItemsBySection(section: string): NavItem[] {
  return docsNav.filter(item => item.section === section);
}


