import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';

export const metadata: Metadata = {
  title: 'Overview | Documentation | Thandev',
  description: 'Learn what Thandev is and what it does for security testing',
};

const mdxContent = `# Overview

Thandev is a comprehensive security testing platform that helps organizations identify vulnerabilities in their web applications and infrastructure. It combines multiple industry-standard security tools with an intelligent AI planning system to provide thorough security assessments.

## What Thandev Is

Thandev is a **multi-tenant security testing platform** that offers:

- **Automated Vulnerability Scanning**: Run security scans at three levels (Basic, Pro, Advanced) using tools like Nuclei, Nmap, SSLScan, HTTPX, FFuF, Dalfox, and SQLMap
- **AI-Powered Planning**: The Brain Service uses RAG (Retrieval-Augmented Generation) to intelligently plan scans based on target characteristics
- **Comprehensive Reporting**: Generate Executive and Full technical PDF reports for stakeholders
- **GitHub OAuth Integration**: Seamless authentication for developers
- **Multi-Tenant Architecture**: Isolated tenant/user environments for enterprise use
- **Real-Time Progress Tracking**: Monitor scan progress with polling-based status updates

## What Thandev Is Not

Thandev is **not** a replacement for manual penetration testing or a compliance certification tool. Specifically:

- **Not Real-Time WebSocket-Based**: Status updates use polling, not WebSocket connections
- **Not a Scheduled Scanning Service**: No automated cron-based scheduled scans (manual scans only)
- **Not a CI/CD Integration**: No native GitHub Actions, Jenkins, or other CI/CD integrations
- **Not a Web Application Firewall (WAF)**: Thandev scans for vulnerabilities but doesn't protect against attacks
- **Not a Compliance Tool**: While reports are useful for security assessments, Thandev doesn't provide compliance certification

## Key Features

### Security Scanning

Thandev provides three scan levels:

- **Basic**: Fast scans (3-8 minutes) with essential tools (HTTPX, Nuclei)
- **Pro**: Comprehensive scans (10-25 minutes) with additional tools (FFuF, Nmap, SSLScan, Dalfox)
- **Advanced**: Complete scans (20-45 minutes) with all tools including SQL injection testing (SQLMap)

### Domain Verification

Before scanning production targets, users must verify domain ownership via DNS TXT records. This ensures you only scan domains you own or have explicit permission to test.

### Project-Based Organization

Organize your scans by project. Each project can contain multiple scan jobs and is tied to a verified root domain.

## Getting Started

Ready to start? Check out the [Getting Started](/docs/getting-started) guide to learn about account approval and running your first scan.

## Key Points

- Thandev is a security testing platform, not a protection tool
- Three scan levels (Basic, Pro, Advanced) provide different coverage and duration
- Domain verification is required before scanning production targets
- AI-powered planning via Brain Service enhances scan effectiveness
- Multi-tenant architecture ensures data isolation
- PDF reports available in Executive and Full technical formats

## FAQ

**Q: Can I scan any website?**  
A: No. You can only scan domains you've verified via DNS TXT records. This prevents unauthorized scanning.

**Q: How long do scans take?**  
A: Basic scans: 3-8 minutes. Pro scans: 10-25 minutes. Advanced scans: 20-45 minutes. Actual time depends on target size and complexity.

**Q: Does Thandev protect my application?**  
A: No. Thandev is a testing tool that finds vulnerabilities. You still need to implement security controls (WAF, secure coding practices, etc.) to protect your applications.

**Q: Can I schedule automatic scans?**  
A: Not currently. Scans must be initiated manually through the dashboard.

**Q: What happens if the Brain Service is unavailable?**  
A: Scans will fall back to default tool configurations, but AI-powered planning won't be available.

**Q: Can I integrate Thandev with my CI/CD pipeline?**  
A: Not currently. Thandev doesn't provide native CI/CD integrations, but API access may be available for custom integrations.

---

**Last updated**: 2025-12-26`;

export default async function OverviewPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Overview"
      description="What Thandev is and what it does"
      href="/docs/overview"
      lastUpdated="2025-12-26"
    />
  );
}

