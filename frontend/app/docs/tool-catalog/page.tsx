import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


export const metadata: Metadata = {
  title: 'Tool Catalog | Documentation | Thandev',
  description: 'All security tools covered and their limits',
};

const mdxContent = `# Tool Catalog

Thandev integrates multiple industry-standard security testing tools. Understanding each tool's capabilities, coverage, and limitations helps you interpret scan results effectively.

## Tool Overview

Thandev uses seven security tools across different scan levels:

### Basic Scan Tools

- **HTTPX**: HTTP surface discovery
- **Nuclei**: Vulnerability scanner

### Pro Scan Tools

- All Basic tools plus:
- **FFuF**: Web fuzzer for directory discovery
- **Nmap**: Network port scanner and service detection
- **SSLScan**: SSL/TLS configuration analysis
- **Dalfox**: XSS (Cross-Site Scripting) scanner

### Advanced Scan Tools

- All Pro tools plus:
- **SQLMap**: SQL injection testing

## Tool Details

### HTTPX

**Purpose**: HTTP surface discovery and probing  
**Scan Levels**: Basic, Pro, Advanced  
**What It Does**: Discovers HTTP endpoints, identifies web servers, and probes for open services

**Capabilities**:
- HTTP/HTTPS endpoint discovery
- Server identification and fingerprinting
- Status code detection
- Response size and time analysis
- Technology stack detection

**Limitations**:
- May miss hidden or protected endpoints
- Rate limiting may affect discovery
- Cannot discover endpoints behind authentication without credentials

**Output**: Lists of discovered URLs, endpoints, and server information

### Nuclei

**Purpose**: Fast vulnerability scanner with template-based detection  
**Scan Levels**: Basic, Pro, Advanced  
**What It Does**: Uses 1000+ vulnerability templates to detect common security issues

**Capabilities**:
- Template-based vulnerability detection
- Wide coverage of common vulnerabilities
- Fast scanning with parallel execution
- Custom template support (if configured)

**Templates Cover**:
- Common web vulnerabilities (XSS, SQLi, etc.)
- Configuration issues
- Exposed files and directories
- Technology-specific vulnerabilities
- CVE-based vulnerability checks

**Limitations**:
- Coverage depends on template library (updates required for new templates)
- May produce false positives
- Template parsing edge cases may miss some issues
- Cannot test authenticated endpoints without credentials

**Output**: Lists of detected vulnerabilities with severity, description, and evidence

### FFuF (Fuzz Faster U Fuzz)

**Purpose**: Web fuzzer for directory and file discovery  
**Scan Levels**: Pro, Advanced  
**What It Does**: Discovers hidden directories and files by fuzzing common paths

**Capabilities**:
- Directory and file discovery
- Parameter fuzzing
- Custom wordlist support (if configured)
- Fast parallel fuzzing
- Response filtering and analysis

**Limitations**:
- Effectiveness depends on wordlist quality
- May miss non-standard paths
- Can be noisy and produce many false positives
- Protected directories may not be discovered without authentication

**Output**: Lists of discovered directories and files with status codes and sizes

### Nmap

**Purpose**: Network port scanner and service detection  
**Scan Levels**: Pro, Advanced  
**What It Does**: Discovers open ports and identifies running services

**Capabilities**:
- Port scanning (TCP/UDP)
- Service version detection
- Operating system detection (if permitted)
- Script-based vulnerability scanning (limited)
- Network topology mapping

**Limitations**:
- May be blocked by firewalls or rate limiting
- Slower than web-focused tools
- Cannot scan targets behind strict firewalls
- Some scans may trigger security alerts

**Output**: Lists of open ports, services, versions, and potential vulnerabilities

### SSLScan

**Purpose**: SSL/TLS configuration analysis  
**Scan Levels**: Pro, Advanced  
**What It Does**: Analyzes SSL/TLS configurations for security issues

**Capabilities**:
- SSL/TLS version detection
- Cipher suite analysis
- Certificate validation checks
- Weak cipher detection
- Protocol support analysis

**Limitations**:
- Only tests SSL/TLS endpoints
- May not catch all configuration issues
- Certificate validation may vary by client
- Some findings may be informational only

**Output**: SSL/TLS configuration details, vulnerabilities, and recommendations

### Dalfox

**Purpose**: XSS (Cross-Site Scripting) vulnerability scanner  
**Scan Levels**: Pro, Advanced  
**What It Does**: Specifically targets XSS vulnerabilities in web applications

**Capabilities**:
- XSS vulnerability detection
- Parameter-based XSS testing
- Multiple XSS payload testing
- Bypass technique testing

**Limitations**:
- Focuses only on XSS vulnerabilities
- May miss context-specific XSS issues
- False positives possible with complex applications
- Cannot test authenticated endpoints without credentials

**Output**: Lists of detected XSS vulnerabilities with payloads and evidence

### SQLMap

**Purpose**: SQL injection vulnerability testing  
**Scan Levels**: Advanced only  
**What It Does**: Tests for SQL injection vulnerabilities using various techniques

**Capabilities**:
- SQL injection detection
- Database fingerprinting
- Data extraction (if vulnerable and permitted)
- Multiple injection point testing
- Bypass technique testing

**Limitations**:
- Most aggressive tool—may trigger security alerts
- Can be slow on complex applications
- May produce false positives
- Cannot test authenticated endpoints without credentials
- Some protections (WAF, rate limiting) may block testing

**Output**: SQL injection vulnerabilities, database information (if accessible), and exploitation details

## Tool Execution

### Execution Order

Tools execute in a specific sequence:

1. **HTTPX**: Discovers endpoints first
2. **Nuclei**: Scans discovered endpoints for vulnerabilities
3. **FFuF**: Discovers directories and files (Pro/Advanced)
4. **Nmap**: Scans network ports (Pro/Advanced)
5. **SSLScan**: Analyzes SSL/TLS configurations (Pro/Advanced)
6. **Dalfox**: Tests for XSS vulnerabilities (Pro/Advanced)
7. **SQLMap**: Tests for SQL injection (Advanced only)

### Parallel vs Sequential

- Tools execute **sequentially** (one after another)
- Individual tools may use parallel execution internally
- Scan completion time depends on tool execution order

### Tool Failures

If a tool fails:
- Scan continues with remaining tools
- Partial findings from successful tools are available
- Failed tool details are logged in scan results
- Scan may complete with partial results

## Tool Output Parsing

### Finding Ingestion

Tool outputs are parsed to extract findings:
- **Structured Parsing**: Tools with structured output (JSON) are parsed directly
- **Text Parsing**: Tools with text output require parsing logic
- **Edge Cases**: Some tool outputs may not parse perfectly

### Known Parsing Limitations

- **Tool Parsing Edge Cases**: Some findings may not be extracted correctly
- **Format Variations**: Tool output format changes may affect parsing
- **Error Handling**: Malformed tool output may skip findings
- **False Positives**: Parsing may misinterpret tool output

**Note**: If you notice missing findings, check scan logs for parsing errors or contact support.

## Coverage Gaps

### What Tools Don't Cover

Tools have limitations and may not detect:
- **Business Logic Vulnerabilities**: Application-specific logic flaws
- **Authentication Bypasses**: Without credentials, authenticated vulnerabilities may be missed
- **Session Management Issues**: Complex session-related vulnerabilities
- **Race Conditions**: Timing-based vulnerabilities
- **Client-Side Vulnerabilities**: Some client-side issues may not be fully tested

### Complementary Testing

Thandev tools complement but don't replace:
- Manual penetration testing
- Code reviews
- Security architecture reviews
- Compliance audits
- Bug bounty programs

## Key Points

- Seven tools: HTTPX, Nuclei, FFuF, Nmap, SSLScan, Dalfox, SQLMap
- Tools execute sequentially in a specific order
- Each tool has specific capabilities and limitations
- Tool output parsing may have edge cases
- Tools don't cover all vulnerability types (e.g., business logic)
- Tool effectiveness depends on target characteristics and configuration

## FAQ

**Q: Can I customize tool configurations?**  
A: Not currently. Tools use default configurations optimized for general use cases.

**Q: Why aren't some vulnerabilities detected?**  
A: Tools have limitations. Some vulnerabilities require manual testing, credentials, or specialized techniques.

**Q: Can I add custom Nuclei templates?**  
A: Not currently. Thandev uses the default Nuclei template library.

**Q: Do tools test authenticated endpoints?**  
A: Not currently. Tools test public endpoints only. Authenticated testing requires credentials (not currently supported).

**Q: Why does SQLMap only run in Advanced scans?**  
A: SQLMap is aggressive and can trigger security alerts. Advanced scans are for deep security assessments where this is appropriate.

**Q: What if a tool fails during execution?**  
A: The scan continues with other tools. Partial findings from successful tools are available.

**Q: How accurate are tool findings?**  
A: Tools are generally accurate but may produce false positives. Always verify findings before remediation.

**Q: Can I see raw tool outputs?**  
A: Raw tool outputs may be available in Full Technical PDF reports. Check report contents for tool output sections.

---

**Last updated**: 2025-12-26`;

export default async function ToolCatalogPage() {
  const mdxSource = await serializeMdx(mdxContent);

  return (
    <DocsContent
      source={mdxSource}
      title="Tool Catalog"
      description="All security tools covered and their limits"
      href="/docs/tool-catalog"
      lastUpdated="2025-12-26"
    />
  );
}


