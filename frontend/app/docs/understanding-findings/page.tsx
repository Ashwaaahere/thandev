import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Understanding Findings | Documentation | Thandev',
  description: 'Severities, false positives, and what to do with findings',
  alternates: {
    canonical: `${SITE_URL}/docs/understanding-findings`,
  },
};

const mdxContent = `# Understanding Findings

Security findings are the core output of Thandev scans. Understanding how findings are categorized, prioritized, and what to do with them helps you effectively address security vulnerabilities.

## Finding Severities

Findings are classified into five severity levels based on potential impact and exploitability:

### Critical

**Color**: Red  
**Risk Score Impact**: High

**Characteristics**:
- Immediate security risk
- Easily exploitable vulnerabilities
- Can lead to complete system compromise
- Data breaches or unauthorized access

**Examples**:
- SQL injection vulnerabilities
- Remote code execution (RCE)
- Authentication bypasses
- Critical configuration errors

**Action**: Address immediately. These pose significant risk and should be remediated as soon as possible.

### High

**Color**: Orange  
**Risk Score Impact**: High

**Characteristics**:
- Significant security risk
- Exploitable with moderate effort
- Can lead to data exposure or system compromise
- Requires attention within days

**Examples**:
- Cross-Site Scripting (XSS) vulnerabilities
- Insecure direct object references
- Missing security headers
- SSL/TLS misconfigurations

**Action**: Address within days to weeks. High-priority issues that should be fixed promptly.

### Medium

**Color**: Yellow  
**Risk Score Impact**: Medium

**Characteristics**:
- Moderate security risk
- May require specific conditions to exploit
- Information disclosure or limited impact
- Should be addressed in planned releases

**Examples**:
- Weak encryption algorithms
- Information disclosure in error messages
- Missing security best practices
- Outdated dependencies (moderate risk)

**Action**: Address in planned releases or within weeks. Important but not urgent.

### Low

**Color**: Blue  
**Risk Score Impact**: Low

**Characteristics**:
- Minor security risk
- Difficult to exploit or limited impact
- Informational issues
- Best practice violations

**Examples**:
- Missing security headers (non-critical)
- Verbose error messages (low risk)
- Information disclosure (non-sensitive)
- Outdated dependencies (low risk)

**Action**: Address as time permits. Low priority but still worth fixing.

### Info

**Color**: Gray  
**Risk Score Impact**: Minimal

**Characteristics**:
- Informational findings
- No immediate security risk
- Best practices or recommendations
- Can improve security posture

**Examples**:
- Security headers present (good)
- HTTPS usage (good)
- Informational messages
- Configuration recommendations

**Action**: Review when convenient. These are informative but not urgent.

## False Positives

Not all findings represent real vulnerabilities. Some may be false positives.

### What Are False Positives?

False positives are findings that:
- Are flagged as vulnerabilities but aren't actually exploitable
- Result from tool misconfigurations or parsing issues
- Represent edge cases in tool detection logic
- Are mitigated by other security controls not visible to scanners

### Common False Positive Sources

1. **Tool Parsing Edge Cases**: Some tool outputs may not parse perfectly, leading to incorrect findings
2. **Detection Logic Limitations**: Tools may flag vulnerabilities that are mitigated elsewhere
3. **Environment Differences**: Findings may be valid in test environments but not production
4. **Configuration Misunderstandings**: Tools may not understand custom security configurations

### Handling False Positives

1. **Investigate First**: Don't dismiss findings without investigation
2. **Verify Exploitability**: Test if the vulnerability is actually exploitable
3. **Check Context**: Consider other security controls that may mitigate the risk
4. **Document Decisions**: Keep records of why findings were marked as false positives
5. **Re-scan After Changes**: If you make changes, re-scan to verify

**Note**: Thandev doesn't currently have built-in false positive marking. Use your project management tools to track false positives and remediation status.

## Finding Details

Each finding includes detailed information to help with remediation:

### Location

- **URL**: The specific URL where the vulnerability was found
- **Parameter**: The parameter or input field affected (if applicable)
- **Path**: The endpoint or page path

### Description

- **Vulnerability Type**: What kind of vulnerability this is
- **Technical Details**: How the vulnerability works
- **Impact Summary**: What could happen if exploited

### Remediation Guidance

- **How to Fix**: Step-by-step remediation instructions
- **Code Examples**: Example fixes or configurations
- **Best Practices**: Security best practices related to this finding

### Metadata

- **Discovery Date**: When this finding was first discovered
- **Last Seen**: When this finding was last observed
- **Tool Source**: Which security tool discovered this finding
- **Severity**: Critical, High, Medium, Low, or Info

## What to Do with Findings

### 1. Review and Prioritize

1. **Sort by Severity**: Start with Critical and High findings
2. **Assess Context**: Consider your application's specific security requirements
3. **Check for Duplicates**: Ensure findings aren't duplicates or related issues
4. **Identify False Positives**: Investigate and mark false positives

### 2. Remediate

1. **Start with Critical**: Address Critical findings immediately
2. **Follow Guidance**: Use the remediation guidance provided in finding details
3. **Test Fixes**: Verify that fixes actually resolve the vulnerability
4. **Re-scan**: Run another scan to confirm findings are resolved

### 3. Track Progress

1. **Use Project Management**: Track findings in your project management tools
2. **Set Deadlines**: Assign remediation deadlines based on severity
3. **Document Decisions**: Record why certain findings were deferred or marked false positives
4. **Monitor Trends**: Track which types of findings appear most frequently

### 4. Learn and Improve

1. **Root Cause Analysis**: Understand why vulnerabilities were introduced
2. **Process Improvements**: Update development practices to prevent similar issues
3. **Training**: Educate team members on security best practices
4. **Prevention**: Implement measures to catch issues earlier in the development cycle

## Finding Lifecycle

Findings follow a lifecycle that helps track their status:

### First Seen

- **Discovery**: Finding is first discovered during a scan
- **Status**: New finding, needs review
- **Action**: Investigate and prioritize

### Ongoing

- **Last Seen**: Finding appears in subsequent scans
- **Status**: Unresolved, still present
- **Action**: Continue remediation efforts

### Resolved

- **Not Seen**: Finding no longer appears in scans
- **Status**: Likely resolved (or mitigated)
- **Action**: Verify fix with manual testing

### Reappeared

- **Re-discovered**: Finding reappears after being resolved
- **Status**: Regression or incomplete fix
- **Action**: Re-investigate and fix properly

## Key Points

- Five severity levels: Critical (immediate), High (days), Medium (weeks), Low (when convenient), Info (informational)
- False positives exist—investigate before dismissing
- Finding details include location, description, remediation guidance, and metadata
- Prioritize by severity, but consider context and exploitability
- Track findings through their lifecycle (first seen, ongoing, resolved, reappeared)
- Re-scan after fixes to verify remediation

## FAQ

**Q: How accurate are severity classifications?**  
A: Severities are based on industry standards, but context matters. Review each finding in the context of your application.

**Q: Can I change a finding's severity?**  
A: Not in Thandev directly. Use your project management tools to track custom priorities based on your context.

**Q: What if I disagree with a severity rating?**  
A: Severities are guidelines. Use your judgment based on your application's specific risks and requirements.

**Q: How do I mark something as a false positive?**  
A: Thandev doesn't currently have built-in false positive marking. Track false positives in your project management tools.

**Q: Do findings expire?**  
A: Findings persist until they're no longer detected in scans. Re-scan to verify if fixes resolved findings.

**Q: Can I export findings?**  
A: Yes. Use PDF reports (Executive or Full) to export findings. See [Reports](/docs/reports) for details.

**Q: How do I know if a fix worked?**  
A: Re-run a scan on the same target. If the finding no longer appears, the fix likely worked. Verify manually as well.

---

**Last updated**: 2025-12-26`;

export default async function UnderstandingFindingsPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Understanding Findings"
      description="Severities, false positives, and what to do"
      href="/docs/understanding-findings"
      lastUpdated="2025-12-26"
    />
  );
}


