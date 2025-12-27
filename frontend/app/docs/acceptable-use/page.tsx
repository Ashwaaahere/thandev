import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';

export const metadata: Metadata = {
  title: 'Acceptable Use | Documentation | Thandev',
  description: 'No unauthorized scanning and abuse handling',
};

const mdxContent = `# Acceptable Use Policy

Thandev is a security testing platform intended for legitimate security testing purposes. This policy outlines acceptable and unacceptable use of Thandev services.

## Acceptable Use

### Authorized Scanning

You may use Thandev to scan:

- **Domains You Own**: Domains where you have ownership or explicit permission
- **Verified Domains**: Domains you've verified via DNS TXT records
- **Demo Targets**: Admin-approved demo targets (bWAPP, itsecgames) for learning
- **Authorized Targets**: Targets where you have explicit written permission to test

### Legitimate Purposes

Thandev is intended for:

- **Security Testing**: Testing security of applications you own or have permission to test
- **Vulnerability Assessment**: Identifying vulnerabilities in authorized targets
- **Compliance Audits**: Security assessments for compliance purposes
- **Learning and Training**: Educational use with demo targets or authorized applications
- **Security Research**: Legitimate security research with appropriate authorization

### Responsible Usage

- **Respect Rate Limits**: Don't exceed plan limits or attempt to bypass restrictions
- **Appropriate Frequency**: Don't abuse scanning resources with excessive scans
- **Follow Terms**: Comply with Thandev Terms of Service and policies
- **Respect Privacy**: Don't scan targets that expose sensitive personal data
- **Secure Credentials**: Keep your account credentials secure

## Unacceptable Use

### Prohibited Activities

The following activities are strictly prohibited:

#### Unauthorized Scanning

- **Scanning Without Permission**: Scanning domains you don't own or lack permission to test
- **Third-Party Targets**: Scanning targets belonging to others without explicit authorization
- **Public Scanning**: Scanning random or public targets without authorization
- **Competitor Scanning**: Scanning competitors' applications without permission

#### Abuse and Exploitation

- **Resource Abuse**: Excessive scanning that degrades service for others
- **Bypassing Limits**: Attempting to bypass quotas, limits, or restrictions
- **Account Sharing**: Sharing accounts or credentials with others
- **Automated Abuse**: Using automation to abuse services or bypass restrictions

#### Malicious Activities

- **Malicious Intent**: Using Thandev for malicious purposes or attacks
- **Data Exfiltration**: Attempting to extract unauthorized data from targets
- **Service Disruption**: Actions that disrupt Thandev services or infrastructure
- **Violation of Laws**: Activities that violate applicable laws or regulations

#### Prohibited Content

- **Illegal Content**: Scanning targets that host illegal content
- **Harmful Content**: Scanning targets that promote harm or illegal activities
- **Sensitive Data**: Scanning targets that expose sensitive personal or financial data without authorization

### Specific Prohibitions

#### Do Not:

- ❌ Scan domains without domain verification (production targets)
- ❌ Scan targets you don't own or lack explicit permission to test
- ❌ Share accounts or credentials with others
- ❌ Attempt to bypass quotas, limits, or restrictions
- ❌ Use Thandev for attacks or malicious purposes
- ❌ Disrupt Thandev services or infrastructure
- ❌ Violate applicable laws or regulations
- ❌ Access or modify data that doesn't belong to you
- ❌ Perform excessive scanning that degrades service for others

## Abuse Handling

### Detection

Thandev monitors for abuse:

- **Automated Detection**: Systems detect suspicious patterns and abuse indicators
- **Manual Review**: Reports and alerts trigger manual investigation
- **User Reports**: Users can report abuse or suspicious activity
- **Monitoring**: Continuous monitoring of usage patterns and anomalies

### Consequences

If abuse is detected:

#### Warnings

- **First Offense**: Warning and explanation of policy violation
- **Education**: Guidance on acceptable use and policy compliance

#### Temporary Suspension

- **Repeated Offenses**: Temporary account suspension
- **Investigation Period**: Account suspended during investigation
- **Remediation Required**: Must demonstrate understanding and compliance before reinstatement

#### Permanent Ban

- **Serious Violations**: Permanent account ban for serious or repeated violations
- **Legal Action**: Legal action may be pursued for severe violations
- **No Appeals**: Permanent bans may not be appealable depending on violation severity

### Investigation Process

1. **Detection**: Abuse detected via automated systems or reports
2. **Investigation**: Thandev investigates the alleged abuse
3. **Notification**: User notified of alleged violation and investigation
4. **Review**: Evidence reviewed and violation confirmed or dismissed
5. **Action**: Appropriate action taken based on violation severity
6. **Appeal**: User may appeal decisions (depending on violation type)

## Appeals Process

### Requesting an Appeal

If you believe your account was suspended or banned incorrectly:

1. **Contact Support**: Reach out to Thandev support with appeal request
2. **Provide Context**: Explain the situation and provide relevant context
3. **Demonstrate Compliance**: Show understanding of acceptable use and commitment to compliance
4. **Wait for Review**: Allow time for appeal review and decision

### Appeal Timeline

- **Review Period**: Appeals typically reviewed within 5-10 business days
- **Decision**: Decision communicated to user
- **Reinstatement**: If appeal approved, account reinstated with conditions if applicable

### Appeal Considerations

Appeals are more likely to be successful if:

- ✅ Violation was unintentional or accidental
- ✅ User demonstrates understanding of acceptable use
- ✅ User shows commitment to future compliance
- ✅ Context explains why violation occurred

Appeals are less likely to be successful if:

- ❌ Violation was intentional or malicious
- ❌ User shows lack of understanding or remorse
- ❌ Repeated violations indicate pattern of abuse
- ❌ Violation caused significant harm or disruption

## Enforcement

### Enforcement Principles

Thandev enforces this policy:

- **Fairly**: Enforcement is fair and consistent
- **Proportionally**: Consequences match violation severity
- **Transparently**: Users informed of violations and consequences
- **Appealably**: Appeals process available (depending on violation type)

### Cooperation

Thandev may cooperate with:

- **Law Enforcement**: Legal authorities investigating violations
- **Legal Proceedings**: Court proceedings related to violations
- **Security Research**: Legitimate security research and investigations

## Reporting Abuse

### How to Report

If you observe abuse or violations:

1. **In-App Reporting**: Use in-app reporting features if available
2. **Email Support**: Contact support@thandev.com with abuse reports
3. **Include Details**: Provide details of observed abuse or violation
4. **Evidence**: Include evidence or screenshots if available

### What to Include

Abuse reports should include:

- **Description**: Clear description of observed abuse or violation
- **Evidence**: Screenshots, logs, or other evidence
- **Context**: Relevant context or background information
- **Affected Parties**: Who or what was affected by the abuse

## Key Points

- Only scan domains you own or have explicit permission to test
- Domain verification required for production targets
- Demo targets (bWAPP, itsecgames) are approved for learning
- Unauthorized scanning is strictly prohibited
- Abuse may result in warnings, suspensions, or permanent bans
- Appeals process available for certain violations
- Report abuse via in-app reporting or support email

## FAQ

**Q: Can I scan my client's website?**  
A: Only if you have explicit written permission from the client. Domain verification may be required.

**Q: Can I scan competitor websites?**  
A: No. Scanning competitors' websites without permission is prohibited.

**Q: What happens if I accidentally scan an unauthorized target?**  
A: Contact support immediately to explain the situation. Unintentional violations may be handled with warnings if reported promptly.

**Q: Can I share my account with my team?**  
A: No. Accounts are individual. Each team member should have their own account.

**Q: What if someone reports me for abuse incorrectly?**  
A: Contact support to explain the situation. Appeals process is available for review.

**Q: Can I use Thandev for penetration testing?**  
A: Yes, if you have authorization to test the target. Ensure you comply with applicable laws and terms of service.

**Q: What if I exceed my scan quota accidentally?**  
A: Contact support to explain the situation. Accidental quota exceedances may be handled with warnings or quota adjustments.

---

**Last updated**: 2025-12-26`;

export default async function AcceptableUsePage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Acceptable Use"
      description="No unauthorized scanning and abuse handling"
      href="/docs/acceptable-use"
      lastUpdated="2025-12-26"
    />
  );
}


