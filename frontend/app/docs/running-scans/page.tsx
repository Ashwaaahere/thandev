import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Running Scans | Documentation | Thandev',
  description: 'Basic/Pro/Advanced scans and scan lifecycle guide',
  alternates: {
    canonical: `${SITE_URL}/docs/running-scans`,
  },
};

const mdxContent = `# Running Scans

Thandev offers three scan levels that provide different coverage and duration. Understanding the scan lifecycle helps you plan and monitor your security assessments effectively.

## Scan Levels

### Basic Scans

**Duration**: 3-8 minutes  
**Tools**: HTTPX, Nuclei  
**Best For**: Quick surface scans, initial assessments, regular monitoring

**Coverage**:
- HTTP surface discovery (HTTPX)
- Common vulnerability detection (Nuclei with standard templates)

**Use Cases**:
- Quick checks before deployments
- Regular security monitoring
- Initial vulnerability assessment
- Non-critical applications

### Pro Scans

**Duration**: 10-25 minutes  
**Tools**: HTTPX, Nuclei, FFuF, Nmap, SSLScan, Dalfox  
**Best For**: Comprehensive security assessments, production applications

**Coverage**:
- All Basic scan tools
- Directory and file discovery (FFuF)
- Network port scanning and service detection (Nmap)
- SSL/TLS configuration analysis (SSLScan)
- Cross-Site Scripting (XSS) detection (Dalfox)

**Use Cases**:
- Pre-production security assessments
- Regular comprehensive scans
- Compliance and security audits
- Production applications

### Advanced Scans

**Duration**: 20-45 minutes  
**Tools**: All Pro tools + SQLMap  
**Best For**: Deep security assessments, critical applications, penetration testing support

**Coverage**:
- All Pro scan tools
- SQL injection testing (SQLMap)

**Use Cases**:
- Critical application security assessments
- Deep penetration testing support
- High-risk target evaluation
- Comprehensive security audits

**Note**: Advanced scans are more aggressive and may trigger security alerts or rate limiting on some targets.

## Scan Lifecycle

Understanding the scan lifecycle helps you track progress and troubleshoot issues.

### 1. Scan Initiation

**Status**: \`pending\`

When you start a scan:
1. Scan job is created in the database
2. Status set to \`pending\`
3. Scan queued for execution

**What You See**: "Scan queued" or "Starting scan..."

### 2. Planning Phase

**Status**: \`planning\` (if Brain Service available)

If the Brain Service is available:
1. Target URL is analyzed
2. AI-powered scan plan is generated
3. Tools and execution modes are selected intelligently
4. Plan is stored for execution

**What You See**: "Planning scan..." or "Generating scan plan..."

**Note**: If the Brain Service is unavailable, scans skip to execution with default configurations.

### 3. Execution Phase

**Status**: \`running\`

The scan executes:
1. Each tool runs in sequence based on the plan
2. Tool outputs are captured and stored
3. Findings are ingested into the database
4. Progress updates are sent (via polling)

**What You See**: "Running scan... Tool X of Y", progress indicators

**Tools Execute In Order**:
1. HTTPX (HTTP discovery)
2. Nuclei (vulnerability scanning)
3. FFuF (directory fuzzing) - Pro/Advanced only
4. Nmap (port scanning) - Pro/Advanced only
5. SSLScan (SSL/TLS analysis) - Pro/Advanced only
6. Dalfox (XSS detection) - Pro/Advanced only
7. SQLMap (SQL injection) - Advanced only

### 4. Processing Phase

**Status**: \`processing\`

After tool execution:
1. Findings are parsed from tool outputs
2. Deduplication identifies duplicate findings
3. Findings are enriched with metadata (if Brain Service available)
4. Scan summary is generated

**What You See**: "Processing results..." or "Analyzing findings..."

### 5. Completion

**Status**: \`completed\`

Scan is complete:
1. All findings are stored in the database
2. Scan summary includes risk score and finding counts
3. Results are available for viewing
4. PDF reports can be generated

**What You See**: "Scan completed", results page with findings

### 6. Error Handling

**Status**: \`failed\` or \`error\`

If a scan fails:
1. Error is logged with details
2. Partial findings may be available
3. Error message explains the failure

**Common Failures**:
- Target unreachable or invalid URL
- Network connectivity issues
- Tool execution errors
- Timeout errors (very large targets)
- Brain Service dependency failures

## Monitoring Scan Progress

### Real-Time Updates

Thandev uses **polling** (not WebSocket) for status updates:

- Status checks every few seconds
- Progress bars show tool execution
- Real-time finding counts
- Estimated time remaining

**Note**: WebSocket real-time updates are not currently available. Polling provides near-real-time status updates.

### Scan Status Indicators

- **Pending**: Scan queued, waiting to start
- **Planning**: Generating scan plan (if Brain Service available)
- **Running**: Tools executing, findings being discovered
- **Processing**: Analyzing results, deduplicating findings
- **Completed**: Scan finished, results available
- **Failed**: Scan encountered an error
- **Cancelled**: Scan was cancelled (if supported)

## Best Practices

1. **Start with Basic**: For new targets, start with a Basic scan to understand surface area
2. **Plan for Duration**: Ensure you have time to monitor longer scans (Pro/Advanced)
3. **Verify Domain First**: Complete domain verification before production scans
4. **Monitor Progress**: Check scan status regularly, especially for long-running scans
5. **Review Findings Promptly**: Review results soon after completion for timely remediation
6. **Use Appropriate Level**: Match scan level to target criticality and available time

## Limitations

### Current Limitations

- **No Scheduled Scans**: Scans must be initiated manually
- **Polling-Based Updates**: No WebSocket real-time updates
- **Brain Service Dependency**: AI planning requires Brain Service availability
- **Tool Parsing Edge Cases**: Some tool outputs may not parse perfectly
- **No Scan Cancellation**: Currently, scans cannot be cancelled once started
- **No CI/CD Integration**: No native GitHub Actions, Jenkins, or other CI/CD integrations

### Tool-Specific Limitations

- **Nuclei**: Template coverage depends on Nuclei template library updates
- **Nmap**: May be blocked by firewalls or rate limiting
- **SQLMap**: Can be aggressive and may trigger security alerts
- **FFuF**: Directory discovery may miss hidden or protected paths

## Key Points

- Three scan levels: Basic (3-8 min), Pro (10-25 min), Advanced (20-45 min)
- Scan lifecycle: pending → planning → running → processing → completed
- Status updates use polling (not WebSocket)
- AI planning requires Brain Service availability
- Tools execute in sequence, not parallel
- Deduplication merges duplicate findings automatically
- Scan results are available immediately after completion

## FAQ

**Q: How do I choose the right scan level?**  
A: Start with Basic for quick checks. Use Pro for comprehensive assessments. Use Advanced for critical applications or deep security testing.

**Q: Can I cancel a running scan?**  
A: Not currently. Scans must complete or fail. Contact support for urgent issues.

**Q: What if the Brain Service is unavailable?**  
A: Scans will proceed with default tool configurations, but AI-powered planning won't be available.

**Q: How long do scans actually take?**  
A: Duration varies by target size and complexity. Basic: 3-8 minutes. Pro: 10-25 minutes. Advanced: 20-45 minutes. Very large targets may take longer.

**Q: Can scans run in parallel?**  
A: Depends on your plan limits. Check your plan's concurrency limits in [Plans & Limits](/docs/plans-limits).

**Q: What happens if a tool fails during execution?**  
A: The scan continues with other tools. Partial findings from successful tools will be available. Failed tools are logged in the scan details.

**Q: Do scans work offline?**  
A: No. Scans require internet connectivity to reach targets and communicate with Thandev services.

---

**Last updated**: 2025-12-26`;

export default async function RunningScansPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Running Scans"
      description="Basic/Pro/Advanced scans and scan lifecycle"
      href="/docs/running-scans"
      lastUpdated="2025-12-26"
    />
  );
}


