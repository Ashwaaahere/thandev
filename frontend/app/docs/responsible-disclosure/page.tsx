import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Responsible Disclosure | Documentation | Thandev',
  description: 'How to report a vulnerability in Thandev',
  alternates: {
    canonical: `${SITE_URL}/docs/responsible-disclosure`,
  },
};

const mdxContent = `# Responsible Disclosure

Thandev values security and welcomes responsible disclosure of security vulnerabilities. This guide explains how to report security issues in Thandev safely and ethically.

## What is Responsible Disclosure?

Responsible disclosure is the practice of:

- **Reporting Security Issues Privately**: Disclosing vulnerabilities to Thandev first, not publicly
- **Giving Time to Fix**: Allowing time for vulnerabilities to be patched before public disclosure
- **Following Coordinated Disclosure**: Working with Thandev to coordinate public disclosure if needed
- **Acting Ethically**: Not exploiting vulnerabilities or accessing unauthorized data

## What to Report

### Security Vulnerabilities

Report security vulnerabilities in Thandev, including:

- **Authentication Bypasses**: Issues that allow unauthorized access
- **Authorization Flaws**: Problems with access controls or permissions
- **Data Exposure**: Unintended data leaks or information disclosure
- **Injection Vulnerabilities**: SQL injection, XSS, command injection, etc.
- **Cryptographic Issues**: Weak encryption, improper key management, etc.
- **Configuration Errors**: Misconfigurations that create security risks
- **Infrastructure Issues**: Problems with underlying infrastructure or services

### What Not to Report

Do not report:

- **Feature Requests**: Suggestions for new features (use normal support channels)
- **Non-Security Bugs**: General bugs that don't have security implications
- **Social Engineering**: Issues requiring social engineering or physical access
- **Denial of Service**: DoS/DDoS vulnerabilities (unless significant)
- **Spam or Phishing**: Spam or phishing issues (use normal reporting channels)
- **Missing Security Headers**: Missing headers that don't create actual vulnerabilities
- **Self-XSS**: Cross-site scripting that requires user interaction with attacker-controlled input

## How to Report

### Step 1: Prepare Your Report

Include the following information:

1. **Description**: Clear description of the vulnerability
2. **Impact**: What an attacker could do with this vulnerability
3. **Steps to Reproduce**: Detailed steps to reproduce the issue
4. **Proof of Concept**: If possible, provide a proof of concept (without exploiting the vulnerability)
5. **Affected Components**: Which parts of Thandev are affected
6. **Suggested Fix**: If you have ideas for how to fix it (optional)

### Step 2: Submit Your Report

**Email**: security@thandev.com (or use in-app security reporting if available)

**Subject**: "Security Vulnerability Report - [Brief Description]"

**Important**: 
- Do not publicly disclose the vulnerability
- Do not post on public forums, social media, or bug bounty platforms without coordination
- Do not attempt to exploit the vulnerability beyond what's necessary to demonstrate it

### Step 3: Wait for Response

- **Initial Response**: You should receive an acknowledgment within 48-72 hours
- **Investigation**: Thandev will investigate and verify the vulnerability
- **Timeline**: You'll be informed of expected resolution timeline
- **Updates**: Regular updates provided on status and progress

### Step 4: Coordination

- **Fix Development**: Thandev develops and tests fixes
- **Verification**: You may be asked to verify the fix (optional)
- **Public Disclosure**: Coordinate public disclosure timeline if desired

## Timeline Expectations

### Typical Timeline

- **Initial Response**: 48-72 hours
- **Investigation**: 1-2 weeks
- **Fix Development**: 2-4 weeks (varies by severity)
- **Deployment**: Depends on fix complexity and release cycle
- **Public Disclosure**: 30-90 days after fix deployment (if coordinated)

**Note**: Timeline may vary based on vulnerability severity, complexity, and Thandev's resources.

## What to Expect

### Acknowledgment

- **Confirmation**: You'll receive confirmation that your report was received
- **Tracking ID**: You may receive a tracking ID for reference
- **Contact**: You may be contacted for additional information

### Investigation

- **Verification**: Thandev will verify and reproduce the vulnerability
- **Assessment**: Severity and impact will be assessed
- **Prioritization**: Fix will be prioritized based on severity

### Resolution

- **Fix Development**: Fix will be developed and tested
- **Deployment**: Fix will be deployed in a future release
- **Verification**: You may be asked to verify the fix (optional)

### Recognition

- **Credits**: You may be credited in security advisories (if you agree)
- **Thank You**: Recognition for responsible disclosure
- **Hall of Fame**: You may be listed in a security hall of fame (if applicable)

## Guidelines

### Do's

- ✅ Report vulnerabilities privately to Thandev
- ✅ Provide clear, detailed information about the vulnerability
- ✅ Give Thandev time to fix the issue before public disclosure
- ✅ Act in good faith and avoid exploiting the vulnerability
- ✅ Respect user data and privacy during testing

### Don'ts

- ❌ Publicly disclose vulnerabilities before Thandev has had time to fix them
- ❌ Exploit vulnerabilities beyond what's necessary to demonstrate them
- ❌ Access or modify data that doesn't belong to you
- ❌ Disrupt Thandev services or infrastructure
- ❌ Demand payment or rewards for vulnerability reports

## Security Testing

### Safe Testing

If you want to test Thandev for vulnerabilities:

1. **Use Your Own Account**: Test only using accounts and data you own
2. **Avoid Disruption**: Don't disrupt services or impact other users
3. **Limit Scope**: Don't test vulnerabilities that could affect other users
4. **Report Promptly**: Report vulnerabilities immediately after discovery

### Out of Scope

The following are generally out of scope:

- **Social Engineering**: Attacks requiring social engineering
- **Physical Access**: Issues requiring physical access to infrastructure
- **DoS/DDoS**: Denial of service attacks (unless significant)
- **Spam**: Spam or phishing issues
- **Third-Party Services**: Vulnerabilities in third-party services Thandev uses

## Legal Considerations

### Safe Harbor

Thandev provides safe harbor for security researchers acting in good faith:

- **No Legal Action**: Thandev will not pursue legal action against researchers who follow responsible disclosure
- **Good Faith**: Researchers must act in good faith and avoid harm
- **Authorization**: Testing must be limited to authorized scope

**Important**: This safe harbor does not extend to:
- Malicious attacks
- Unauthorized access to other users' data
- Disruption of services
- Violations of laws or regulations

### Compliance

- **Follow Laws**: Ensure your testing complies with applicable laws
- **Respect Terms**: Follow Thandev's Terms of Service
- **Privacy**: Respect user privacy and data protection requirements

## Key Points

- Report security vulnerabilities privately to Thandev first
- Include detailed information: description, impact, steps to reproduce, proof of concept
- Give Thandev time to fix issues before public disclosure
- Act ethically: don't exploit vulnerabilities or access unauthorized data
- Expect acknowledgment within 48-72 hours
- Typical fix timeline: 2-4 weeks (varies by severity)
- Safe harbor provided for good-faith security research

## FAQ

**Q: Will I be paid for reporting vulnerabilities?**  
A: Thandev does not currently offer monetary rewards for vulnerability reports. Recognition and credits may be provided.

**Q: Can I publicly disclose the vulnerability?**  
A: Please coordinate with Thandev before public disclosure. We prefer responsible disclosure with time to fix issues.

**Q: How long should I wait before public disclosure?**  
A: Typically 30-90 days after fix deployment, but coordinate with Thandev for specific timelines.

**Q: What if Thandev doesn't respond?**  
A: If you don't receive an acknowledgment within 72 hours, follow up or use alternative contact methods.

**Q: Can I test Thandev for vulnerabilities?**  
A: Yes, but use your own account and data, avoid disruption, and report vulnerabilities promptly.

**Q: Will I be credited for reporting vulnerabilities?**  
A: Yes, with your permission, you may be credited in security advisories or a security hall of fame.

**Q: What if I accidentally accessed someone else's data?**  
A: Report it immediately to Thandev. Do not access, copy, or share the data. Act in good faith.

---

**Last updated**: 2025-12-26`;

export default async function ResponsibleDisclosurePage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Responsible Disclosure"
      description="How to report a vulnerability in Thandev"
      href="/docs/responsible-disclosure"
      lastUpdated="2025-12-26"
    />
  );
}


