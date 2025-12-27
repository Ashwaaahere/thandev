import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';

export const metadata: Metadata = {
  title: 'FAQ | Documentation | Thandev',
  description: 'General troubleshooting and common questions',
};

const mdxContent = `# FAQ

Frequently asked questions and troubleshooting guide for common Thandev issues.

## General Questions

### What is Thandev?

Thandev is a comprehensive security testing platform that helps organizations identify vulnerabilities in their web applications and infrastructure. It combines multiple industry-standard security tools with an intelligent AI planning system.

### How do I get started?

1. Sign up with GitHub OAuth
2. Wait for admin approval (1-2 business days)
3. Complete domain verification for production targets
4. Create a project and run your first scan

See [Getting Started](/docs/getting-started) for detailed steps.

### How long does account approval take?

Typically 1-2 business days. You'll receive an email notification when your account is approved.

### Can I choose my plan?

No. Plans are assigned by administrators based on your needs and usage. Contact your administrator to request plan changes.

## Scanning Questions

### How long do scans take?

- **Basic scans**: 3-8 minutes
- **Pro scans**: 10-25 minutes
- **Advanced scans**: 20-45 minutes

Actual duration depends on target size and complexity.

### Can I cancel a running scan?

Not currently. Scans must complete or fail. Contact support for urgent issues.

### What scan level should I use?

- **Basic**: Quick checks, initial assessments, regular monitoring
- **Pro**: Comprehensive assessments, production applications
- **Advanced**: Deep security assessments, critical applications, penetration testing support

See [Running Scans](/docs/running-scans) for details.

### Why did my scan fail?

Common scan failure reasons:
- Target unreachable or invalid URL
- Network connectivity issues
- Tool execution errors
- Timeout errors (very large targets)
- Brain Service dependency failures

Check scan logs for specific error messages.

### Can I schedule automatic scans?

Not currently. Scans must be initiated manually through the dashboard.

### Do scans work offline?

No. Scans require internet connectivity to reach targets and communicate with Thandev services.

## Domain Verification

### Do I need to verify domains?

Yes, for production targets. Domain verification is required before scanning production domains. Demo targets (bWAPP, itsecgames) don't require verification.

### How long does domain verification take?

Usually 5-15 minutes after adding the DNS TXT record. Rarely up to 48 hours.

### Do I need to verify every subdomain?

No. Verify the root domain (e.g., \`example.com\`) and you can scan all subdomains under it.

### What if verification fails?

- Wait a few more minutes (DNS propagation delay)
- Verify the TXT record value is exactly correct
- Check that the record is at the root domain
- Use a DNS lookup tool to confirm the record is live

See [Domain Verification](/docs/domain-verification) for troubleshooting.

## Findings Questions

### How accurate are findings?

Tools are generally accurate but may produce false positives. Always verify findings before remediation. Some findings may require manual testing to confirm.

### What should I do with findings?

1. Review and prioritize by severity (Critical → High → Medium → Low → Info)
2. Investigate and verify findings (check for false positives)
3. Remediate starting with Critical and High findings
4. Re-scan to verify fixes

See [Understanding Findings](/docs/understanding-findings) for details.

### Can I mark findings as false positives?

Thandev doesn't currently have built-in false positive marking. Use your project management tools to track false positives and remediation status.

### How long are findings stored?

Storage retention varies by plan:
- **Basic**: Typically 90 days
- **Pro**: Typically 180 days
- **Enterprise**: Typically 1 year+

Contact administrators for specific retention periods.

### Do findings expire?

Findings persist until they're no longer detected in scans. Re-scan to verify if fixes resolved findings.

## Reports Questions

### What report types are available?

- **Executive Report**: High-level overview (5-15 pages) for management and stakeholders
- **Full Technical Report**: Detailed technical findings (20-100+ pages) for development teams

See [Reports](/docs/reports) for details.

### How long do reports take to generate?

Usually 30-60 seconds for most scans. Very large scans with many findings may take longer.

### Can I export reports in other formats?

Not currently. Reports are only available as PDFs.

### Can I customize report templates?

Not currently. Reports use standard Thandev templates and cannot be customized.

## Platform Limits

### What happens if I exceed my monthly quota?

New scans may be blocked until the quota resets at the beginning of the next month. Contact administrators to request quota increases.

### Can I run more concurrent scans than my limit?

No. Additional scans will be queued and start automatically when capacity is available.

### How do I request a plan upgrade?

Contact your administrator or support team with your usage needs and justification for an upgrade.

See [Plans & Limits](/docs/plans-limits) for details.

## Technical Questions

### Does Thandev support WebSocket real-time updates?

Not currently. Status updates use polling (not WebSocket). Polling provides near-real-time status updates.

### What if the Brain Service is unavailable?

Scans will proceed with default tool configurations, but AI-powered planning won't be available. Scans will still complete successfully.

### Can I integrate Thandev with CI/CD?

Not currently. Thandev doesn't provide native CI/CD integrations, but API access may be available for custom integrations.

### Can I customize tool configurations?

Not currently. Tools use default configurations optimized for general use cases.

### Do tools test authenticated endpoints?

Not currently. Tools test public endpoints only. Authenticated testing requires credentials (not currently supported).

## Troubleshooting

### My scan is stuck or taking too long

- Check scan status in the dashboard
- Very large targets may take longer than typical durations
- Contact support if scans are stuck for extended periods

### I can't verify my domain

- Verify the TXT record value is exactly correct (no extra spaces)
- Check that the record is at the root domain (not a subdomain)
- Wait a few minutes for DNS propagation
- Use a DNS lookup tool to confirm the record is live

### I'm not seeing expected findings

- Check if tools completed successfully (may have failed)
- Verify findings weren't filtered or deduplicated
- Some vulnerabilities may require manual testing to detect
- Tool parsing edge cases may miss some findings

### Reports are not generating

- Ensure scan is completed (not pending or running)
- Try generating report again after a few moments
- Contact support if issues persist

### I'm hitting rate limits or quotas

- Check your plan limits in the dashboard
- Contact administrators to request quota increases
- Plan scan schedules to avoid hitting limits

## Getting Help

### Where can I get support?

- **Documentation**: Check these docs pages for detailed guides
- **Dashboard**: Use in-app help and support features
- **Administrators**: Contact your account administrator
- **Support Team**: Reach out to Thandev support for technical issues

### How do I report a bug?

Use the in-app bug reporting feature or contact support with:
- Description of the issue
- Steps to reproduce
- Screenshots or error messages
- Browser/device information (if relevant)

### Can I suggest a feature?

Yes! Contact support or administrators with feature suggestions. Thandev is continuously improving based on user feedback.

## Key Points

- Account approval typically takes 1-2 business days
- Plans are assigned by administrators (no self-selection)
- Domain verification is required for production scans
- Scans must be initiated manually (no scheduling)
- Findings should be verified before remediation
- Reports are PDF-only and cannot be customized
- Contact administrators for plan changes or limit increases
- Support is available through documentation, dashboard, and administrators

---

**Last updated**: 2025-12-26`;

export default async function FAQPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="FAQ"
      description="General troubleshooting and common questions"
      href="/docs/faq"
      lastUpdated="2025-12-26"
    />
  );
}


