import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


export const metadata: Metadata = {
  title: 'Privacy | Documentation | Thandev',
  description: 'Data collected, storage, retention, and third parties',
};

const mdxContent = `# Privacy Policy

This privacy policy explains what data Thandev collects, how it's used, stored, and shared. Your privacy is important to us.

## Data We Collect

### Account Information

- **GitHub Profile Data**: Name, email, profile picture (from GitHub OAuth)
- **Account Details**: Account status, plan assignment, tenant information
- **Authentication Data**: OAuth tokens, session information

### Scan Data

- **Target URLs**: URLs you scan
- **Scan Configurations**: Scan levels, tool selections, scan settings
- **Scan Results**: Findings, vulnerabilities, tool outputs
- **Scan Metadata**: Timestamps, scan status, execution details

### Usage Data

- **Platform Usage**: Features used, pages visited, interactions
- **Scan History**: Scan frequency, scan types, target patterns
- **Performance Data**: Scan durations, tool execution times, system performance

### Technical Data

- **IP Addresses**: IP addresses used to access Thandev
- **Browser Information**: Browser type, version, device information
- **Logs**: Application logs, error logs, security logs

## How We Use Data

### Service Provision

- **Scan Execution**: Execute security scans on your targets
- **Result Storage**: Store and display scan results and findings
- **Account Management**: Manage your account, plans, and access
- **Support**: Provide customer support and respond to inquiries

### Platform Improvement

- **Analytics**: Analyze usage patterns to improve services
- **Performance Optimization**: Optimize platform performance and reliability
- **Feature Development**: Develop new features based on usage patterns
- **Bug Fixes**: Identify and fix bugs and issues

### Security and Compliance

- **Security Monitoring**: Monitor for security threats and abuse
- **Compliance**: Comply with legal and regulatory requirements
- **Fraud Prevention**: Prevent fraud, abuse, and unauthorized access
- **Audit Logging**: Maintain audit logs for accountability

## Data Storage

### Storage Location

- **Cloud Infrastructure**: Data stored in cloud infrastructure (location varies by deployment)
- **Database Storage**: Structured data stored in databases
- **File Storage**: Scan outputs and files stored in secure file storage
- **Backup Storage**: Regular backups stored securely

### Encryption

- **Encryption at Rest**: Sensitive data encrypted when stored
- **Encryption in Transit**: All data transmitted encrypted using TLS 1.2+
- **Key Management**: Encryption keys managed securely

### Retention

Data retention periods vary by data type and plan:

- **Account Data**: Retained while account is active
- **Scan Results**: Retained according to plan limits (Basic: ~90 days, Pro: ~180 days, Enterprise: ~1 year+)
- **Logs**: Retained for operational and security purposes (typically 30-90 days)
- **Backup Data**: Retained according to backup policies

**Note**: Actual retention periods may vary. Contact support for specific retention policies.

## Data Sharing

### Third-Party Services

Thandev uses third-party services that may process your data:

- **GitHub**: Authentication via GitHub OAuth (GitHub privacy policy applies)
- **Cloud Providers**: Infrastructure and hosting services
- **Analytics Services**: Usage analytics and monitoring (if used)
- **Support Tools**: Customer support and communication tools

### Legal Requirements

We may share data when required by law:

- **Legal Requests**: Respond to legal requests, subpoenas, court orders
- **Law Enforcement**: Cooperate with law enforcement investigations
- **Compliance**: Comply with legal and regulatory requirements
- **Protection**: Protect rights, property, or safety of Thandev or users

### Business Transfers

In the event of a business transfer:

- **Mergers/Acquisitions**: Data may be transferred as part of business transfers
- **Asset Sales**: Data may be included in asset sales
- **Notifications**: Users notified of significant business transfers

### No Sale of Data

**Thandev does not sell your data** to third parties for marketing or advertising purposes.

## Your Rights

### Access

- **View Your Data**: Access your account data, scan results, and findings
- **Export Data**: Export your data via PDF reports or data export features
- **Request Information**: Request information about data we hold about you

### Correction

- **Update Account Information**: Update your account information via account settings
- **Correct Data**: Request corrections to inaccurate data

### Deletion

- **Delete Account**: Request account deletion (subject to retention requirements)
- **Delete Scan Data**: Delete individual scans or findings (subject to retention policies)
- **Data Deletion**: Request deletion of specific data

**Note**: Some data may be retained for legal, security, or operational reasons even after deletion requests.

### Objection and Restriction

- **Opt-Out**: Opt out of certain data processing activities (where applicable)
- **Restrict Processing**: Request restrictions on data processing (where applicable)
- **Withdraw Consent**: Withdraw consent for data processing (where applicable)

### Portability

- **Data Export**: Request export of your data in a portable format
- **Data Transfer**: Transfer data to another service (where technically feasible)

## Data Security

### Security Measures

Thandev implements security measures to protect your data:

- **Encryption**: Data encrypted in transit and at rest
- **Access Controls**: Access controls limit data access to authorized personnel
- **Multi-Tenant Isolation**: Data isolation ensures tenants cannot access other tenants' data
- **Security Monitoring**: Continuous monitoring for security threats
- **Regular Audits**: Regular security audits and assessments

### Security Incidents

If a security incident affects your data:

- **Detection**: Incidents detected via monitoring and alerts
- **Investigation**: Incidents investigated to determine scope and impact
- **Notification**: Affected users notified if necessary (per applicable laws)
- **Remediation**: Measures taken to contain and remediate incidents

## Cookies and Tracking

### Cookies

Thandev may use cookies for:

- **Authentication**: Session management and authentication
- **Preferences**: Storing user preferences and settings
- **Analytics**: Analyzing usage patterns (if applicable)

### Tracking

- **No Third-Party Tracking**: Thandev does not use third-party tracking for advertising
- **Analytics**: Internal analytics may track usage patterns (anonymized where possible)

## Children's Privacy

Thandev is not intended for users under 18 years of age. We do not knowingly collect data from children.

## International Data Transfers

If data is transferred internationally:

- **Adequate Safeguards**: Appropriate safeguards implemented for international transfers
- **Compliance**: Compliance with applicable data protection laws
- **User Rights**: User rights protected regardless of transfer location

## Changes to Privacy Policy

### Updates

This privacy policy may be updated:

- **Notification**: Users notified of significant changes
- **Review Period**: Opportunity to review changes
- **Effective Date**: Effective date of updated policy

### Continued Use

Continued use of Thandev after policy changes constitutes acceptance of updated policy.

## Contact

### Privacy Inquiries

For privacy inquiries or to exercise your rights:

- **Email**: privacy@thandev.com (or use support contact)
- **Support**: Use in-app support features

### Data Protection Officer

If applicable, contact the Data Protection Officer for privacy matters.

## Key Points

- Data collected includes account info, scan data, usage data, and technical data
- Data used for service provision, platform improvement, and security
- Data stored securely with encryption at rest and in transit
- Retention periods vary by data type and plan
- Data shared with third-party services (GitHub, cloud providers) and when required by law
- Thandev does not sell data to third parties
- Users have rights to access, correct, delete, and export data
- Security measures protect data from unauthorized access

## FAQ

**Q: What data does Thandev collect?**  
A: Account information, scan data, usage data, and technical data. See "Data We Collect" section for details.

**Q: How long is my data stored?**  
A: Retention periods vary by data type and plan. Scan results: Basic ~90 days, Pro ~180 days, Enterprise ~1 year+. Contact support for specific retention policies.

**Q: Does Thandev sell my data?**  
A: No. Thandev does not sell your data to third parties for marketing or advertising purposes.

**Q: Who can see my scan data?**  
A: Only you and authorized Thandev administrators. Multi-tenant isolation ensures data privacy.

**Q: Can I delete my data?**  
A: Yes. You can delete individual scans or request account deletion. Some data may be retained for legal or operational reasons.

**Q: How is my data secured?**  
A: Data is encrypted in transit (TLS) and at rest (database encryption). Access controls and multi-tenant isolation protect data.

**Q: What third parties receive my data?**  
A: GitHub (authentication), cloud providers (infrastructure), and support tools. Data may also be shared when required by law.

**Q: Can I export my data?**  
A: Yes. Export via PDF reports or request data export in a portable format.

---

**Last updated**: 2025-12-26`;

export default async function PrivacyPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Privacy"
      description="Data collected, storage, retention, and third parties"
      href="/docs/privacy"
      lastUpdated="2025-12-26"
    />
  );
}


