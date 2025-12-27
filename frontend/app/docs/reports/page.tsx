import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


export const metadata: Metadata = {
  title: 'Reports | Documentation | Thandev',
  description: 'Executive vs Full PDF reports and sharing safely',
};

const mdxContent = `# Reports

Thandev generates comprehensive PDF reports that summarize scan results for different audiences. Understanding the two report types and how to share them safely helps you communicate security findings effectively.

## Report Types

### Executive Report

**Audience**: Executives, management, stakeholders  
**Length**: Concise, 5-15 pages  
**Focus**: High-level overview, business impact, risk summary

**Contents**:
- Executive summary
- Risk score and overall security posture
- Critical and High findings summary
- Business impact assessment
- Remediation priorities and recommendations
- Visual charts and graphs

**Best For**:
- Presenting to management
- Board presentations
- Compliance audits
- Stakeholder updates
- High-level security assessments

### Full Technical Report

**Audience**: Security teams, developers, technical staff  
**Length**: Comprehensive, 20-100+ pages  
**Focus**: Detailed technical findings, remediation guidance, evidence

**Contents**:
- Complete scan details
- All findings with full technical details
- Finding locations and evidence
- Step-by-step remediation guidance
- Tool outputs and raw data
- Code examples and configuration fixes

**Best For**:
- Development team remediation
- Detailed security audits
- Technical reviews
- Penetration testing documentation
- Compliance documentation

## Generating Reports

### Step 1: Access Report Generation

1. Navigate to your completed scan
2. Click "Generate Report" or "Download Report"
3. Select report type: Executive or Full Technical

### Step 2: Select Report Type

**Executive Report**:
- Choose "Executive" or "Summary" mode
- Report focuses on high-level findings and business impact

**Full Technical Report**:
- Choose "Full" or "Technical" mode
- Report includes all findings with detailed technical information

### Step 3: Download PDF

1. Report generation may take a few moments
2. PDF downloads automatically or click download link
3. Save the PDF securely

**Note**: Reports are generated on-demand and may take 30-60 seconds for large scans.

## Report Contents

### Executive Report Sections

1. **Cover Page**: Scan metadata, date, target information
2. **Executive Summary**: High-level overview, risk score, key findings
3. **Risk Overview**: Visual risk breakdown by severity
4. **Critical Findings**: Summary of Critical vulnerabilities
5. **High Findings**: Summary of High-priority vulnerabilities
6. **Business Impact**: Explanation of risks in business terms
7. **Recommendations**: Prioritized remediation guidance
8. **Appendices**: Supporting charts and graphs

### Full Technical Report Sections

1. **Cover Page**: Complete scan metadata
2. **Table of Contents**: Navigable report structure
3. **Executive Summary**: High-level overview (condensed)
4. **Methodology**: Scan configuration, tools used, scope
5. **Findings Detail**: Complete finding details including:
   - Location (URL, parameter, path)
   - Description and technical details
   - Severity and risk assessment
   - Evidence and proof of concept
   - Remediation guidance with code examples
   - References and additional resources
6. **Risk Scoring**: Detailed risk score calculation
7. **Tool Outputs**: Raw tool outputs (if included)
8. **Appendices**: Supporting documentation, charts, raw data

## Sharing Reports Safely

### Security Considerations

PDF reports contain sensitive security information:
- **Vulnerability Details**: Specific security weaknesses in your applications
- **Exploitation Paths**: How vulnerabilities can be exploited
- **System Information**: URLs, paths, and system details
- **Risk Assessments**: Overall security posture

### Best Practices for Sharing

1. **Restrict Access**: Only share reports with authorized personnel
2. **Use Secure Channels**: Send via encrypted email or secure file sharing
3. **Mark as Confidential**: Clearly label reports as confidential or sensitive
4. **Set Expiration**: Consider setting expiration dates for shared reports
5. **Track Recipients**: Keep a log of who received reports
6. **Version Control**: Track report versions to avoid confusion

### Sharing Scenarios

**Internal Teams**:
- Use secure file sharing (SharePoint, Google Drive with restrictions)
- Share via encrypted email
- Restrict access to specific team members only

**External Stakeholders**:
- Use secure file sharing platforms
- Consider redacting sensitive details for non-technical audiences
- Use Executive reports for external stakeholders when possible

**Compliance Audits**:
- Provide reports via secure, audited channels
- Maintain records of shared reports
- Use Full Technical reports for compliance documentation

**Development Teams**:
- Share via secure collaboration tools
- Provide Full Technical reports with detailed remediation guidance
- Track remediation progress in project management tools

## Report Limitations

### Current Limitations

- **PDF Format Only**: Reports are only available as PDFs (no Word, JSON, or other formats)
- **On-Demand Generation**: Reports must be generated manually (no scheduled generation)
- **No Customization**: Report templates cannot be customized or branded
- **No Partial Reports**: Cannot generate reports for subsets of findings
- **Single Language**: Reports are in English only

### Data Accuracy

- **Snapshot in Time**: Reports reflect findings at scan completion time
- **May Include False Positives**: Review findings before sharing reports
- **Tool-Dependent**: Report accuracy depends on tool output parsing

## Key Points

- Two report types: Executive (high-level, 5-15 pages) and Full Technical (detailed, 20-100+ pages)
- Reports are generated on-demand as PDFs
- Executive reports are best for management and stakeholders
- Full Technical reports are best for development teams and detailed audits
- Share reports securely via encrypted channels
- Restrict access to authorized personnel only
- Mark reports as confidential or sensitive

## FAQ

**Q: Can I customize report branding or templates?**  
A: Not currently. Reports use standard Thandev templates and cannot be customized.

**Q: Can I generate reports for specific findings only?**  
A: Not currently. Reports include all findings from a scan. Use your PDF viewer to navigate to specific sections.

**Q: How long do reports take to generate?**  
A: Usually 30-60 seconds for most scans. Very large scans with many findings may take longer.

**Q: Can I export reports in other formats (Word, JSON, CSV)?**  
A: Not currently. Reports are only available as PDFs.

**Q: Are reports stored permanently?**  
A: Reports are generated on-demand. Thandev may cache generated reports temporarily, but you should download and store them securely.

**Q: Can I share reports publicly?**  
A: Not recommended. Reports contain sensitive security information and should only be shared with authorized personnel.

**Q: Do reports include false positives?**  
A: Reports include all findings detected by tools. Review findings and verify before sharing reports widely.

**Q: Can I schedule automatic report generation?**  
A: Not currently. Reports must be generated manually after scan completion.

---

**Last updated**: 2025-12-26`;

export default async function ReportsPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Reports"
      description="Executive vs Full PDF reports and sharing safely"
      href="/docs/reports"
      lastUpdated="2025-12-26"
    />
  );
}


