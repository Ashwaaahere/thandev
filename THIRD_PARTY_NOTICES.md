# Third-Party Tools & Licenses

**Last Updated:** 2025-01-29

This document lists all third-party open-source tools used by Thandev and their respective licenses. Tool names and trademarks belong to their respective owners. Tools are used under their respective open-source licenses.

**For the authoritative license terms, see each upstream license file linked below.**

## Tools Used by Thandev

| Tool | Purpose | License | Upstream Repository | License URL | Notes |
|------|---------|---------|---------------------|-------------|-------|
| **Nuclei** | Fast vulnerability scanner with template-based detection | MIT | [github.com/projectdiscovery/nuclei](https://github.com/projectdiscovery/nuclei) | [LICENSE](https://github.com/projectdiscovery/nuclei/blob/master/LICENSE) | Used for vulnerability scanning across all scan levels |
| **httpx** | HTTP surface discovery and probing tool | MIT | [github.com/projectdiscovery/httpx](https://github.com/projectdiscovery/httpx) | [LICENSE](https://github.com/projectdiscovery/httpx/blob/master/LICENSE) | Used for endpoint discovery and technology detection |
| **Katana** | Fast web crawler for URL discovery | MIT | [github.com/projectdiscovery/katana](https://github.com/projectdiscovery/katana) | [LICENSE](https://github.com/projectdiscovery/katana/blob/master/LICENSE) | Used in Advanced scans for asset enumeration |
| **GAU (Get All URLs)** | Discovers URLs from Wayback Machine, CommonCrawl, and other sources | MIT | [github.com/lc/gau](https://github.com/lc/gau) | [LICENSE](https://github.com/lc/gau/blob/master/LICENSE) | Used in Advanced scans for historical URL discovery |
| **Dalfox** | XSS (Cross-Site Scripting) vulnerability scanner | MIT | [github.com/hahwul/dalfox](https://github.com/hahwul/dalfox) | [LICENSE](https://github.com/hahwul/dalfox/blob/master/LICENSE) | Used in Pro and Advanced scans for XSS detection |
| **OWASP ZAP** | Web application security scanner | Apache-2.0 | [www.zaproxy.org](https://www.zaproxy.org/) | [LICENSE](https://github.com/zaproxy/zaproxy/blob/main/LICENSE) | Used for passive and active web application security testing |
| **SQLMap** | SQL injection vulnerability testing tool | GPL-2.0-or-later | [github.com/sqlmapproject/sqlmap](https://github.com/sqlmapproject/sqlmap) | [LICENSE](https://github.com/sqlmapproject/sqlmap/blob/master/LICENSE) | Used in Advanced scans only. Redistribution triggers GPL obligations. |
| **Arjun** | HTTP parameter discovery and fuzzing tool | AGPL-3.0 | [github.com/s0md3v/Arjun](https://github.com/s0md3v/Arjun) | [LICENSE](https://github.com/s0md3v/Arjun/blob/master/LICENSE) | Used in Advanced scans. Modifications used over a network may trigger source-offer obligations. |
| **Nmap** | Network port scanner and service detection | Nmap Public Source License (NPSL) | [nmap.org](https://nmap.org/) | [NPSL License](https://nmap.org/npsl/) | Used in Pro and Advanced scans. Hosted server-side use differs from redistribution. For redistribution in customer-delivered products/containers/VMs, see [Nmap OEM Licensing](https://nmap.org/oem/). |
| **SSLScan** | SSL/TLS configuration analysis tool | GPL-3.0 | [github.com/rbsec/sslscan](https://github.com/rbsec/sslscan) | [LICENSE](https://github.com/rbsec/sslscan/blob/master/LICENSE) | Used in Pro and Advanced scans. Redistribution triggers GPL obligations. |
| **retire.js** | JavaScript vulnerability scanner | MIT | [github.com/RetireJS/retire.js](https://github.com/RetireJS/retire.js) | [LICENSE](https://github.com/RetireJS/retire.js/blob/master/LICENSE) | Used for client-side JavaScript dependency vulnerability scanning |
| **Chromium** | Headless browser for JavaScript rendering | BSD-3-Clause | [chromium.org](https://www.chromium.org/) | [LICENSE](https://chromium.googlesource.com/chromium/src/+/main/LICENSE) | Used by Katana for headless JavaScript crawling in Advanced scans |

## License Notes

### GPL-2.0 and GPL-3.0 Tools
Tools licensed under GPL-2.0 (SQLMap) and GPL-3.0 (SSLScan) require that any redistribution of the tool or modifications must also be licensed under the same GPL license. See the respective license files for full terms.

### AGPL-3.0 Tools
Arjun is licensed under AGPL-3.0, which requires that if you modify the tool and use it over a network, you must offer the source code to users. See the [AGPL-3.0 license text](https://www.gnu.org/licenses/agpl-3.0.html) for details.

### Nmap Public Source License (NPSL)
Nmap uses the Nmap Public Source License (NPSL). Hosted server-side use (as in Thandev's SaaS offering) is permitted under NPSL. However, redistribution of Nmap in customer-delivered products, containers, or VMs may require an OEM license. See [Nmap's licensing page](https://nmap.org/npsl/) for details.

### MIT and Apache-2.0 Tools
Most tools (Nuclei, httpx, Katana, GAU, Dalfox, retire.js) are licensed under MIT, and OWASP ZAP is licensed under Apache-2.0. These are permissive licenses that allow commercial use, modification, and distribution with minimal restrictions.

## Contact

For questions about tool usage or licensing, contact: [Your Contact Information]

---

**Note:** This document is maintained for compliance purposes. Tool versions and licenses may change. Always refer to the upstream repository for the most current license information.

