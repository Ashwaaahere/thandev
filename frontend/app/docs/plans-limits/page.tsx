import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Plans & Limits | Documentation | Thandev',
  description: 'Plans, quotas, concurrency, and fair use policy',
  alternates: {
    canonical: `${SITE_URL}/docs/plans-limits`,
  },
};

const mdxContent = `# Plans & Limits

Thandev operates on a plan-based system where administrators assign plans to users. Understanding plan limits, quotas, and fair use policies helps you use the platform effectively.

## Plan Assignment

### How Plans Work

- **Admin-Assigned**: Plans are assigned by administrators (no self-selection)
- **Manual Assignment**: Admins evaluate your needs and assign appropriate plans
- **Plan Changes**: Contact administrators to request plan upgrades or changes
- **Tenant-Based**: Plans apply to your tenant (account)

### Requesting Plan Changes

To request a plan change:
1. Contact your administrator or support team
2. Explain your usage needs and requirements
3. Provide justification for plan upgrade/downgrade
4. Wait for admin review and assignment

## Plan Types

### Basic Plan

**Typical Limits** (examples—actual limits may vary):
- **Scans per Month**: Limited (e.g., 10-20 scans)
- **Concurrent Scans**: 1-2 simultaneous scans
- **Projects**: Limited number of projects
- **Findings Storage**: Standard retention

**Best For**:
- Individual developers
- Small projects
- Occasional security testing
- Learning and experimentation

### Pro Plan

**Typical Limits** (examples—actual limits may vary):
- **Scans per Month**: Moderate (e.g., 50-100 scans)
- **Concurrent Scans**: 3-5 simultaneous scans
- **Projects**: Multiple projects
- **Findings Storage**: Extended retention

**Best For**:
- Development teams
- Regular security testing
- Multiple applications
- Production security assessments

### Enterprise Plan

**Typical Limits** (examples—actual limits may vary):
- **Scans per Month**: High or unlimited
- **Concurrent Scans**: 10+ simultaneous scans
- **Projects**: Unlimited projects
- **Findings Storage**: Long-term retention
- **Priority Support**: Faster response times

**Best For**:
- Large organizations
- High-volume scanning needs
- Enterprise security programs
- Compliance and audit requirements

**Note**: Actual plan limits are set by administrators and may vary. Contact your administrator for specific limits.

## Quotas and Limits

### Scan Quotas

**Monthly Scan Limits**:
- Plans include a monthly scan quota
- Quotas reset at the beginning of each month
- Exceeding quotas may block new scans until reset
- Contact administrators to request quota increases

**Understanding Quota Usage**:
- Each scan consumes one quota unit
- Failed scans may or may not count toward quotas (varies by plan)
- Scan quota usage is visible in your account dashboard

### Concurrent Scan Limits

**Simultaneous Scans**:
- Plans limit how many scans can run simultaneously
- Exceeding concurrent limits queues new scans
- Queued scans start automatically when capacity is available
- Concurrent limits prevent resource exhaustion

**Best Practices**:
- Plan scan schedules to avoid hitting concurrent limits
- Start scans with appropriate delays if needed
- Monitor active scans before starting new ones

### Project Limits

**Number of Projects**:
- Plans may limit the number of projects you can create
- Exceeding project limits blocks new project creation
- Archive or delete unused projects to free up space
- Contact administrators to request limit increases

### Findings Storage

**Storage Retention**:
- Findings are stored for a period based on your plan
- Basic plans: Standard retention (e.g., 90 days)
- Pro plans: Extended retention (e.g., 180 days)
- Enterprise plans: Long-term retention (e.g., 1 year+)

**Storage Limits**:
- Large numbers of findings may approach storage limits
- Export and archive old findings if needed
- Contact administrators if approaching limits

## Fair Use Policy

### Acceptable Usage

Thandev is intended for legitimate security testing:

- **Owned Domains**: Scan only domains you own or have permission to test
- **Reasonable Frequency**: Don't abuse scanning resources with excessive scans
- **Appropriate Targets**: Use demo targets for learning, production domains only when authorized
- **Respect Rate Limits**: Don't attempt to bypass platform limits or restrictions

### Unacceptable Usage

**Prohibited Activities**:
- Scanning domains without authorization
- Attempting to bypass quotas or limits
- Excessive resource consumption
- Malicious or abusive behavior
- Sharing accounts or credentials
- Violating platform terms of service

### Abuse Handling

**If Abuse is Detected**:
1. Account may be temporarily suspended
2. Administrators will investigate
3. Repeat offenses may result in permanent bans
4. Legal action may be pursued for serious violations

**Appeals Process**:
- Contact support to appeal suspensions
- Provide explanation and context
- Demonstrate legitimate usage
- Follow administrator guidance

## Monitoring Usage

### Dashboard Metrics

Your dashboard shows:
- **Scans This Month**: Current month's scan count
- **Remaining Quota**: How many scans you have left
- **Active Scans**: Currently running scans
- **Concurrent Usage**: How many scans are running simultaneously

### Usage Alerts

- **Quota Warnings**: Alerts when approaching monthly quotas
- **Concurrent Limit Warnings**: Notifications when hitting concurrent limits
- **Storage Warnings**: Alerts when approaching storage limits

## Key Points

- Plans are assigned by administrators (no self-selection)
- Plans include limits for scans, concurrency, projects, and storage
- Monthly scan quotas reset at the beginning of each month
- Concurrent scan limits prevent resource exhaustion
- Fair use policy prohibits unauthorized scanning and abuse
- Monitor usage in your dashboard to avoid hitting limits
- Contact administrators for plan changes or limit increases

## FAQ

**Q: Can I choose my own plan?**  
A: No. Plans are assigned by administrators based on your needs and usage.

**Q: What happens if I exceed my monthly quota?**  
A: New scans may be blocked until the quota resets at the beginning of the next month. Contact administrators to request quota increases.

**Q: Do failed scans count toward my quota?**  
A: This varies by plan. Check with your administrator for specific policies.

**Q: Can I run more concurrent scans than my limit?**  
A: No. Additional scans will be queued and start automatically when capacity is available.

**Q: How do I request a plan upgrade?**  
A: Contact your administrator or support team with your usage needs and justification for an upgrade.

**Q: What if I need temporary quota increases for a project?**  
A: Contact administrators to request temporary quota increases. They may approve requests for legitimate use cases.

**Q: How long are findings stored?**  
A: Storage retention varies by plan. Basic: typically 90 days. Pro: typically 180 days. Enterprise: typically 1 year+. Contact administrators for specific retention periods.

**Q: Can I share my account with team members?**  
A: No. Accounts are individual. Each team member should have their own account. Contact administrators for team/organization setup.

---

**Last updated**: 2025-12-26`;

export default async function PlansLimitsPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Plans & Limits"
      description="Plans, quotas, concurrency, and fair use"
      href="/docs/plans-limits"
      lastUpdated="2025-12-26"
    />
  );
}


