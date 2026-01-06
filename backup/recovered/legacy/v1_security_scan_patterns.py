"""
LEGACY - v1 Security Scan Patterns

⚠️ LEGACY CODE - NOT USED IN v2 ARCHITECTURE ⚠️

This file documents the old v1 security scan patterns that were removed.
These patterns should NOT be used in the new v2 architecture.

All actual scanning now happens in cloud-run/security-scanner/scanner.py
"""

# ============================================================================
# OLD v1 PATTERNS (REMOVED - DO NOT USE)
# ============================================================================

"""
OLD v1 Pattern: Direct subprocess calls from API router

Example of what was removed:
    
    async def run_nuclei_scan(url: str, templates: list):
        # BAD: Direct subprocess in router
        result = subprocess.run(
            ["nuclei", "-u", url, "-t", ",".join(templates)],
            capture_output=True, timeout=1800
        )
        return result.stdout

This pattern had problems:
- Blocked API request threads
- No separation of concerns
- Hard to scale
- Mixed scanning logic with API logic
"""

"""
OLD v1 Pattern: Synchronous local scan execution

Example of what was removed:
    
    def run_local_scan_sync(job_id: str, url: str, tier: str):
        # BAD: Synchronous blocking execution
        results = {}
        results['nuclei'] = run_nuclei_scan(url, ["info", "technologies"])
        results['nmap'] = run_nmap_scan(url)
        results['ssl'] = run_ssl_scan(url)
        return results

This pattern had problems:
- Blocked the entire process
- Could not handle concurrent scans
- No timeout management
- Resource exhaustion on server
"""

"""
OLD v1 Pattern: PDF report generation (if it existed)

Example pattern that would have been removed:
    
    def generate_pdf_report(scan_results: dict) -> bytes:
        # BAD: Heavy PDF generation in API process
        from reportlab import ...
        pdf = generate_pdf(scan_results)
        return pdf

This pattern had problems:
- CPU/memory intensive
- Blocked API requests
- Should be done asynchronously or in separate service
"""

# ============================================================================
# v2 ARCHITECTURE (CURRENT - USE THIS)
# ============================================================================

"""
v2 Pattern: Cloud Run Service orchestration

Current implementation in app/routers/security.py:
    
    async def run_security_scan(job_id: str, url: str, tier: str):
        # GOOD: Orchestrates via HTTP to Cloud Run Service
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{cloud_run_url}/run",
                json={"url": url, "tier": tier, "jobId": job_id}
            )
        # Poll for results asynchronously

Benefits:
- Non-blocking
- Scalable
- Separation of concerns
- Can handle many concurrent scans
"""

"""
v2 Pattern: Scanning logic in separate service

Current implementation in cloud-run/security-scanner/scanner.py:
    
    class SecurityScanner:
        async def run_level0_scan(self, url: str, hostname: str, port: int):
            # GOOD: Scanning logic in dedicated service
            await self.run_nuclei_scan(url, ["info", "technologies"])
            await self.run_ssl_scan(hostname, port)
            await self.run_nmap_scan(hostname, ["--top-ports", "100"])

Benefits:
- Isolated execution environment
- Can scale independently
- Better resource management
- Easier to test and maintain
"""

# ============================================================================
# MIGRATION CHECKLIST
# ============================================================================

"""
If you see any of these patterns in the codebase, they should be moved to legacy:

[ ] Direct subprocess.run() calls in app/routers/security.py
[ ] Synchronous scan execution functions
[ ] PDF generation in API routers
[ ] Local tool execution (nuclei, nmap, etc.) in backend routers
[ ] Blocking scan operations
[ ] Mixed scanning and API logic

All scanning should now:
✓ Happen in cloud-run/security-scanner/
✓ Be orchestrated via HTTP from backend
✓ Use async/await patterns
✓ Be non-blocking
"""



