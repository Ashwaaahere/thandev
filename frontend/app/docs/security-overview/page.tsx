import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Security Overview | Documentation | Thandev',
  description: 'High-level security posture and CIA triad summary',
  alternates: {
    canonical: `${SITE_URL}/docs/security-overview`,
  },
};

const mdxContent = `# Security Overview

Thandev takes security seriously. This document provides a high-level overview of Thandev's security posture and how we protect your data using the CIA triad (Confidentiality, Integrity, Availability).

## Security Philosophy

Thandev is built with security in mind:

- **Secure by Design**: Security considerations are integrated into every aspect of the platform
- **Defense in Depth**: Multiple layers of security controls protect data and systems
- **Least Privilege**: Access controls ensure users only have necessary permissions
- **Continuous Improvement**: Security posture is continuously reviewed and improved

## The CIA Triad

Thandev's security approach is based on the CIA triad: Confidentiality, Integrity, and Availability.

### Confidentiality

**Protecting Data Privacy**

- **Encryption in Transit**: All data transmitted between clients and Thandev is encrypted using TLS 1.2+
- **Encryption at Rest**: Sensitive data stored in databases is encrypted
- **Access Controls**: Multi-tenant architecture ensures data isolation between tenants
- **Authentication**: GitHub OAuth provides secure, industry-standard authentication
- **Authorization**: Role-based access controls limit data access to authorized users only

**What This Means**:
- Your scan data is only accessible to you and authorized administrators
- Data is encrypted when stored and transmitted
- Multi-tenant isolation prevents cross-tenant data access

### Integrity

**Ensuring Data Accuracy**

- **Data Validation**: Input validation prevents malicious or malformed data
- **Audit Logging**: Actions are logged for accountability and investigation
- **Database Constraints**: Database-level constraints ensure data consistency
- **Version Control**: Code and configuration changes are tracked
- **Checksums**: Data integrity checks verify data hasn't been corrupted

**What This Means**:
- Your scan data and findings are accurate and reliable
- Data modifications are tracked and logged
- System integrity is maintained through validation and constraints

### Availability

**Maintaining Service Uptime**

- **Infrastructure Resilience**: Distributed infrastructure reduces single points of failure
- **Monitoring**: System health is continuously monitored
- **Incident Response**: Procedures exist for responding to availability issues
- **Backup and Recovery**: Data backups enable recovery from failures
- **Scalability**: Infrastructure scales to handle demand

**What This Means**:
- Thandev is available when you need it
- System failures are detected and addressed promptly
- Data is backed up and can be recovered if needed

**Note**: While Thandev strives for high availability, we don't guarantee 100% uptime. Some planned maintenance and unexpected incidents may cause temporary service interruptions.

## Security Controls

### Authentication and Authorization

- **GitHub OAuth**: Secure authentication via GitHub (industry-standard OAuth 2.0)
- **Session Management**: Secure session handling with appropriate timeouts
- **Multi-Tenant Isolation**: Data isolation ensures tenants cannot access other tenants' data
- **Role-Based Access**: Access controls based on user roles and permissions

### Data Protection

- **Encryption**: Data encrypted in transit (TLS) and at rest (database encryption)
- **Secure Storage**: Sensitive data stored securely with access controls
- **Data Retention**: Data retained according to plan limits and retention policies
- **Secure Deletion**: Data deleted securely when no longer needed

### Network Security

- **TLS Encryption**: All connections encrypted with TLS 1.2+
- **Firewall Rules**: Network access controlled via firewalls
- **DDoS Protection**: Protection against distributed denial-of-service attacks (if deployed)
- **Secure Communication**: Secure channels for all service-to-service communication

### Application Security

- **Input Validation**: All user inputs validated and sanitized
- **Output Encoding**: Output encoded to prevent injection attacks
- **Secure Coding Practices**: Code follows security best practices
- **Dependency Management**: Dependencies kept up-to-date with security patches

### Monitoring and Logging

- **Security Monitoring**: Security events monitored for suspicious activity
- **Audit Logging**: User actions and system events logged for audit trails
- **Incident Detection**: Automated detection of security incidents
- **Alerting**: Alerts generated for security events requiring attention

## Security Limitations

### Current Limitations

Thandev has some security limitations:

- **No WebSocket Real-Time Updates**: Status updates use polling, which may have different security implications than WebSocket connections
- **Brain Service Dependency**: AI planning depends on Brain Service availability, which may have its own security considerations
- **Tool Parsing Edge Cases**: Tool output parsing may have edge cases that could affect data integrity
- **No Scheduled Scans**: Manual scan initiation may have different security implications than automated scheduled scans

### Shared Responsibility

Security is a shared responsibility:

- **Thandev**: Protects platform infrastructure, data storage, and service availability
- **Users**: Responsible for secure usage, domain verification, and protecting credentials
- **Third Parties**: Third-party services (GitHub OAuth, cloud providers) have their own security measures

## Compliance and Standards

### Security Standards

Thandev follows security best practices and industry standards:

- **OWASP Guidelines**: Application security follows OWASP best practices
- **Encryption Standards**: Uses industry-standard encryption (TLS 1.2+, database encryption)
- **Authentication Standards**: OAuth 2.0 for authentication
- **Data Protection**: Follows data protection best practices

**Note**: Thandev may not be fully compliant with all regulatory requirements (e.g., SOC 2, ISO 27001, GDPR). Check with your compliance team if specific certifications are required.

## Incident Response

### Security Incidents

If a security incident occurs:

1. **Detection**: Security monitoring detects incidents
2. **Investigation**: Incidents are investigated to determine scope and impact
3. **Containment**: Measures taken to contain and mitigate incidents
4. **Recovery**: Services restored and normal operations resumed
5. **Communication**: Affected users notified if necessary
6. **Post-Incident Review**: Incidents reviewed to improve security

### Reporting Security Issues

If you discover a security vulnerability in Thandev, see [Responsible Disclosure](/docs/responsible-disclosure) for reporting procedures.

## Key Points

- Security based on CIA triad: Confidentiality, Integrity, Availability
- Encryption in transit (TLS) and at rest (database encryption)
- Multi-tenant isolation ensures data privacy
- GitHub OAuth provides secure authentication
- Security monitoring and audit logging in place
- Shared responsibility model (Thandev and users)
- Security limitations exist (polling, Brain Service dependency, etc.)
- Incident response procedures in place

## FAQ

**Q: Is my data encrypted?**  
A: Yes. Data is encrypted in transit (TLS) and at rest (database encryption).

**Q: Can other users see my scan data?**  
A: No. Multi-tenant isolation ensures your data is only accessible to you and authorized administrators.

**Q: Is Thandev SOC 2 compliant?**  
A: Thandev follows security best practices but may not be fully compliant with all regulatory requirements. Check with your compliance team if specific certifications are required.

**Q: How are security incidents handled?**  
A: Incidents are detected, investigated, contained, and recovered from. Affected users are notified if necessary. See [Responsible Disclosure](/docs/responsible-disclosure) for reporting security vulnerabilities.

**Q: What happens to my data if Thandev shuts down?**  
A: Data retention policies apply. Contact support for specific data retention and deletion policies.

**Q: Can I export my data?**  
A: Yes. PDF reports allow you to export scan results. Contact support for additional data export options.

**Q: How is authentication secured?**  
A: GitHub OAuth (OAuth 2.0) provides secure authentication. Sessions are managed securely with appropriate timeouts.

---

**Last updated**: 2025-12-26`;

export default async function SecurityOverviewPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Security Overview"
      description="High-level security posture and CIA triad summary"
      href="/docs/security-overview"
      lastUpdated="2025-12-26"
    />
  );
}


