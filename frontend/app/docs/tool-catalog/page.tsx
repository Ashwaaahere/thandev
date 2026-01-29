import { Metadata } from 'next';
import { serializeMdx } from '@/lib/docs/serialize-mdx';
import DocsContent from '@/components/docs/DocsContent';


const SITE_URL = 'https://thandev.io';

export const metadata: Metadata = {
  title: 'Tool Catalog | Documentation | Thandev',
  description: 'All security tools covered and their limits',
  alternates: {
    canonical: `${SITE_URL}/docs/tool-catalog`,
  },
};

const mdxContent = `# Tool Catalog

Thandev integrates multiple industry-standard security testing tools. Understanding each tool's capabilities, coverage, and limitations helps you interpret scan results effectively.

## Tool Overview

Thandev uses eight security tools across different scan levels:

### Basic Scan Tools

- **HTTPX**: HTTP surface discovery
- **Nuclei**: Vulnerability scanner
- **ZAP**: OWASP ZAP passive spider for web application security testing

### Pro Scan Tools

- All Basic tools plus:
- **Nmap**: Network port scanner and service detection
- **SSLScan**: SSL/TLS configuration analysis
- **Dalfox**: XSS (Cross-Site Scripting) scanner
- **ZAP Active Scan**: OWASP ZAP active vulnerability scanning

### Advanced Scan Tools

- All Pro tools plus:
- **SQLMap**: SQL injection testing
- **ZAP AJAX Spider**: OWASP ZAP AJAX-based crawling for modern web apps
- **Enumeration**: Asset discovery using Katana, GAU, and Arjun

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

### ZAP (OWASP ZAP)

**Purpose**: Web application security scanner  
**Scan Levels**: Basic (passive), Pro (passive + active), Advanced (AJAX spider + active)  
**What It Does**: Comprehensive web application security testing using passive and active scanning techniques

**Capabilities**:
- Passive spidering to discover application structure
- Active vulnerability scanning
- AJAX-based crawling for modern single-page applications
- Session management testing
- Authentication testing (when credentials provided)
- API security testing
- OWASP Top 10 vulnerability detection

**Modes**:
- **Passive Spider**: Crawls application without active testing (Basic/Pro)
- **Active Scan**: Actively tests for vulnerabilities (Pro/Advanced)
- **AJAX Spider**: Handles JavaScript-heavy applications (Advanced)

**Limitations**:
- Can be slow on large applications
- May require manual configuration for complex authentication flows
- Some findings may require manual verification
- AJAX spider can be resource-intensive

**Output**: Comprehensive security findings including vulnerabilities, alerts, and recommendations

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

### Enumeration (Asset Discovery)

**Purpose**: Comprehensive asset discovery and enumeration  
**Scan Levels**: Advanced  
**What It Does**: Discovers URLs, endpoints, and parameters using multiple enumeration tools

**Tools Used**:
- **Katana**: Fast web crawler for URL discovery
- **GAU (Get All URLs)**: Discovers URLs from various sources (Wayback Machine, CommonCrawl, etc.)
- **Arjun**: Parameter discovery and fuzzing

**Capabilities**:
- Comprehensive URL discovery from multiple sources
- Parameter discovery and enumeration
- Historical URL discovery (Wayback Machine, CommonCrawl)
- Endpoint enumeration
- Technology stack detection

**Limitations**:
- Can be time-consuming on large applications
- Historical data may include outdated endpoints
- Some sources may have rate limits
- Requires internet connectivity for external sources

**Output**: Comprehensive asset inventory including discovered URLs, parameters, and endpoints

## Tool Execution

### Execution Order

Tools execute in a specific sequence:

1. **HTTPX**: Discovers endpoints first
2. **Enumeration**: Asset discovery using Katana, GAU, and Arjun (Advanced only)
3. **Nuclei**: Scans discovered endpoints for vulnerabilities
4. **ZAP Passive Spider**: Crawls application structure (Basic/Pro/Advanced)
5. **Nmap**: Scans network ports (Pro/Advanced)
6. **SSLScan**: Analyzes SSL/TLS configurations (Pro/Advanced)
7. **Dalfox**: Tests for XSS vulnerabilities (Pro/Advanced)
8. **ZAP Active Scan**: Actively tests for vulnerabilities (Pro/Advanced)
9. **ZAP AJAX Spider**: Handles JavaScript-heavy applications (Advanced only)
10. **SQLMap**: Tests for SQL injection (Advanced only)

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

- Eight tools: HTTPX, Nuclei, ZAP, Nmap, SSLScan, Dalfox, SQLMap, Enumeration (Katana/GAU/Arjun)
- Tools execute sequentially in a specific order
- Each tool has specific capabilities and limitations
- Tool output parsing may have edge cases
- Tools don't cover all vulnerability types (e.g., business logic)
- Tool effectiveness depends on target characteristics and configuration
- ZAP provides comprehensive web application security testing across all scan levels

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

**Q: What is the difference between ZAP passive and active scanning?**  
A: Passive scanning crawls and analyzes without sending attack payloads (safer, faster). Active scanning sends test payloads to detect vulnerabilities (more thorough, may trigger alerts).

**Q: What does Enumeration do?**  
A: Enumeration uses Katana, GAU, and Arjun to discover URLs, endpoints, and parameters from multiple sources including historical archives. This provides comprehensive asset discovery for Advanced scans.

**Q: What if a tool fails during execution?**  
A: The scan continues with other tools. Partial findings from successful tools are available.

**Q: How accurate are tool findings?**  
A: Tools are generally accurate but may produce false positives. Always verify findings before remediation.

**Q: Can I see raw tool outputs?**  
A: Raw tool outputs may be available in Full Technical PDF reports. Check report contents for tool output sections.

## Third-Party Tools & Licenses

Thandev uses multiple open-source security testing tools. Tool names and trademarks belong to their respective owners. Tools are used under their respective open-source licenses.

**For the authoritative license terms, see each upstream license file linked below.**

| Tool | What it's used for | License | Upstream | License Text | Notes |
|------|-------------------|---------|----------|--------------|-------|
| **Nuclei** | Fast vulnerability scanner with template-based detection | MIT | [github.com/projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei) | [LICENSE](https://github.com/projectdiscovery/nuclei/blob/master/LICENSE) | Used for vulnerability scanning across all scan levels |
| **httpx** | HTTP surface discovery and probing | MIT | [github.com/projectdiscovery/httpx](https://github.com/projectdiscovery/httpx) | [LICENSE](https://github.com/projectdiscovery/httpx/blob/master/LICENSE) | Used for endpoint discovery and technology detection |
| **Katana** | Fast web crawler for URL discovery | MIT | [github.com/projectdiscovery/katana](https://github.com/projectdiscovery/katana) | [LICENSE](https://github.com/projectdiscovery/katana/blob/master/LICENSE) | Used in Advanced scans for asset enumeration |
| **GAU (Get All URLs)** | Discovers URLs from Wayback Machine, CommonCrawl, and other sources | MIT | [github.com/lc/gau](https://github.com/lc/gau) | [LICENSE](https://github.com/lc/gau/blob/master/LICENSE) | Used in Advanced scans for historical URL discovery |
| **Dalfox** | XSS (Cross-Site Scripting) vulnerability scanner | MIT | [github.com/hahwul/dalfox](https://github.com/hahwul/dalfox) | [LICENSE](https://github.com/hahwul/dalfox/blob/master/LICENSE) | Used in Pro and Advanced scans for XSS detection |
| **OWASP ZAP** | Web application security scanner | Apache-2.0 | [www.zaproxy.org](https://www.zaproxy.org/) | [LICENSE](https://github.com/zaproxy/zaproxy/blob/main/LICENSE) | Used for passive and active web application security testing |
| **SQLMap** | SQL injection vulnerability testing | GPL-2.0-or-later | [github.com/sqlmapproject/sqlmap](https://github.com/sqlmapproject/sqlmap) | [LICENSE](https://github.com/sqlmapproject/sqlmap/blob/master/LICENSE) | Used in Advanced scans only. Redistribution triggers GPL obligations. |
| **Arjun** | HTTP parameter discovery and fuzzing | AGPL-3.0 | [github.com/s0md3v/Arjun](https://github.com/s0md3v/Arjun) | [LICENSE](https://github.com/s0md3v/Arjun/blob/master/LICENSE) | Used in Advanced scans. Modifications used over a network may trigger source-offer obligations. |
| **Nmap** | Network port scanner and service detection | Nmap Public Source License (NPSL) | [nmap.org](https://nmap.org/) | [NPSL License](https://nmap.org/npsl/) | Used in Pro and Advanced scans. Hosted server-side use differs from redistribution. Redistribution in distributed products/VMs/containers may require [Nmap OEM license](https://nmap.org/oem/). |
| **SSLScan** | SSL/TLS configuration analysis | GPL-3.0 | [github.com/rbsec/sslscan](https://github.com/rbsec/sslscan) | [LICENSE](https://github.com/rbsec/sslscan/blob/master/LICENSE) | Used in Pro and Advanced scans. GPL-3.0-or-later (OpenSSL exception). Redistribution triggers GPL obligations. |
| **retire.js** | JavaScript vulnerability scanner | Apache-2.0 | [github.com/RetireJS/retire.js](https://github.com/RetireJS/retire.js) | [LICENSE.md](https://github.com/RetireJS/retire.js/blob/master/LICENSE.md) | Used for client-side JavaScript dependency vulnerability scanning |
| **Chromium** | Headless browser for JavaScript rendering | BSD-3-Clause | [chromium.org](https://www.chromium.org/) | [LICENSE](https://chromium.googlesource.com/chromium/src/+/main/LICENSE) | Used by Katana for headless JavaScript crawling in Advanced scans |

### License Highlights

**GPL-2.0 and GPL-3.0 Tools**: SQLMap (GPL-2.0-or-later) and SSLScan (GPL-3.0) require that any redistribution of the tool or modifications must also be licensed under the same GPL license. See the respective license files for full terms.

**AGPL-3.0 Tools**: Arjun is licensed under AGPL-3.0, which requires that if you modify the tool and use it over a network, you must offer the source code to users. See the [AGPL-3.0 license text](https://www.gnu.org/licenses/agpl-3.0.html) for details.

**Nmap Public Source License (NPSL)**: Nmap uses the Nmap Public Source License (NPSL). Hosted server-side use (as in Thandev's SaaS offering) is permitted under NPSL. However, redistribution of Nmap in customer-delivered products, containers, or VMs may require an OEM license. See [Nmap's licensing page](https://nmap.org/npsl/) for details.

**MIT and Apache-2.0 Tools**: Most tools (Nuclei, httpx, Katana, GAU, Dalfox) are licensed under MIT, and OWASP ZAP and retire.js are licensed under Apache-2.0. These are permissive licenses that allow commercial use, modification, and distribution with minimal restrictions.

For a complete list with additional details, see [THIRD_PARTY_NOTICES.md](https://github.com/Ashwaaahere/thandev/blob/main/THIRD_PARTY_NOTICES.md) in the repository.

---

**Last updated**: 2025-01-29`;

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


