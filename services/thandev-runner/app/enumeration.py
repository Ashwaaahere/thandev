"""
Enumeration module for pentester-grade asset discovery

This module implements the enumeration phase for Pro and Advanced scans:
- HTTPX: Canonical URL and technology detection
- Katana: Web crawling for URL discovery
- GAU: Historical URL discovery from archives
- Arjun: Parameter discovery on interesting endpoints

The output is a structured asset inventory that feeds into scanners.
"""
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from urllib.parse import urlparse, urljoin, urlunparse, parse_qs, urlencode
from datetime import datetime, timezone
import re

logger = logging.getLogger(__name__)


class AssetInventory:
    """Structured asset inventory for a target"""
    
    def __init__(self, target_url: str):
        self.target_url = target_url
        self.scope = {
            "allowed_hosts": [],
            "start_url": target_url,
            "final_url": None,
        }
        self.discovery = {
            "httpx": {"tech": [], "status": 0, "final_url": None},
            "katana": {"urls_count": 0, "urls": []},
            "gau": {"urls_count": 0, "urls": []},
            "merged": {
                "all_urls_count": 0,
                "all_urls": [],
                "param_urls": [],
                "unique_paths": [],
                "interesting": {
                    "auth": [],
                    "admin": [],
                    "api": [],
                    "docs": [],
                    "uploads": [],
                    "graphql": [],
                    "swagger": [],
                }
            },
            "arjun": {
                "tested_urls": [],
                "params_by_url": {}
            }
        }
        self.timestamps = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert inventory to dictionary"""
        return {
            "target": self.target_url,
            "scope": self.scope,
            "discovery": self.discovery,
            "timestamps": self.timestamps,
        }


async def run_httpx(target_url: str) -> Dict[str, Any]:
    """
    Run HTTPX to get canonical URL and technology detection
    
    Returns:
        Dict with status, title, tech, tls info, and final URL
    """
    logger.info(f"[HTTPX] Running against {target_url}")
    
    try:
        # Run httpx with tech detection
        cmd = [
            "httpx",
            "-u", target_url,
            "-silent",
            "-json",
            "-tech-detect",
            "-status-code",
            "-title",
            "-follow-redirects",
            "-max-redirects", "5",
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        # Parse JSON output (httpx may return non-zero exit code but still have valid output)
        output = result.stdout.strip()
        stderr_output = result.stderr.strip()
        
        if not output:
            logger.warning(f"[HTTPX] No output from httpx (exit={result.returncode}, stderr={stderr_output[:200]})")
            # Try to extract error from stderr
            error_msg = stderr_output if stderr_output else "No output from httpx"
            return {"status": 0, "error": error_msg, "tech": [], "final_url": target_url}
        
        try:
            data = json.loads(output)
        except json.JSONDecodeError as e:
            logger.warning(f"[HTTPX] Failed to parse JSON output: {e}, output={output[:200]}")
            return {"status": 0, "error": f"Invalid JSON output: {str(e)}", "tech": [], "final_url": target_url}
        
        # If exit code is non-zero but we have data, log warning but continue
        if result.returncode != 0:
            logger.warning(f"[HTTPX] Non-zero exit code {result.returncode} but got output, continuing anyway")
        
        # Ensure tech is always a list (httpx may return None or missing field)
        tech_list = data.get("tech", [])
        if not isinstance(tech_list, list):
            tech_list = []
        
        return {
            "status": data.get("status_code", 0),
            "title": data.get("title", ""),
            "tech": tech_list,
            "tls": data.get("tls", {}),
            "final_url": data.get("url", target_url),
        }
        
    except subprocess.TimeoutExpired:
        logger.warning(f"[HTTPX] Timeout after 30s")
        return {"status": 0, "error": "Timeout"}
    except Exception as e:
        logger.error(f"[HTTPX] Error: {e}", exc_info=True)
        return {"status": 0, "error": str(e)}


async def run_katana(target_url: str, depth: int = 3, max_urls: int = 500) -> Tuple[List[str], Optional[str]]:
    """
    Run Katana web crawler to discover URLs
    
    Args:
        target_url: Target URL to crawl
        depth: Crawl depth (Pro=2-3, Advanced=3-4)
        max_urls: Maximum URLs to collect
        
    Returns:
        List of discovered URLs
    """
    logger.info(f"[KATANA] Crawling {target_url} with depth={depth}")
    
    try:
        # Extract hostname for scope limiting
        parsed = urlparse(target_url)
        hostname = parsed.hostname or parsed.netloc
        
        # CLOUD OPTIMIZATION: Skip headless mode entirely in containerized/cloud environments
        # Headless mode requires Chrome and is resource-intensive, causing timeouts on Fly.io
        # Non-headless mode is faster and more reliable in containers
        import os
        is_cloud = os.getenv("FLY_APP_NAME") or os.getenv("KUBERNETES_SERVICE_HOST") or os.getenv("ENVIRONMENT") == "production"
        
        # Non-headless command (fast, reliable, works in containers)
        base_cmd_fast = [
            "katana",
            "-u", target_url,
            "-d", str(depth),
            "-kf", "all",            # Known files
            "-silent",
            "-no-color",
            "-c", "50",               # Concurrency for faster crawling
            "-rate-limit", "15",      # Rate limit: 15 requests per second
        ]
        
        # Headless command (only used locally for JS-heavy sites)
        base_cmd_headless = [
            "katana",
            "-u", target_url,
            "-d", str(depth),
            "-kf", "all",            # Known files
            "-headless",              # Use headless mode for better results
            "-no-sandbox",            # Required in containers
            "-silent",
            "-no-color",
            "-c", "30",               # Lower concurrency for headless
            "-rate-limit", "10",      # Rate limit: 10 requests per second
        ]
        
        def run_cmd(cmd, timeout_sec=180):
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        
        # In cloud environments, use fast non-headless mode only
        if is_cloud:
            logger.info(f"[KATANA] Cloud environment detected, using fast non-headless mode")
            result = run_cmd(base_cmd_fast, timeout_sec=120)  # 2 minutes in cloud
        else:
            # Local: Try headless mode first, fallback to non-headless
            logger.debug(f"[KATANA] Trying headless mode: {' '.join(base_cmd_headless)}")
            result = run_cmd(base_cmd_headless)
            
            # If headless fails with Chrome error, try fallback mode
            if result.returncode != 0 and result.stderr and ("chrome" in result.stderr.lower() or "chromium" in result.stderr.lower() or "browser" in result.stderr.lower()):
                logger.warning(f"[KATANA] Headless mode failed (likely Chrome unavailable), trying fallback mode. Error: {result.stderr[:200]}")
                result = run_cmd(base_cmd_fast)
                if result.returncode == 0:
                    logger.info(f"[KATANA] Fallback mode succeeded (non-headless)")
        
        # Initialize urls before parsing
        urls = []
        def parse_urls(text):
            out = []
            for line in text.strip().split('\n'):
                line = line.strip()
                if line and line.startswith('http'):
                    out.append(line)
                    if len(out) >= max_urls:
                        break
            return out
        
        urls = parse_urls(result.stdout or "")
        
        # Log detailed results
        if result.returncode == 0:
            logger.info(f"[KATANA] Found {len(urls)} URLs (exit={result.returncode})")
            if len(urls) == 0:
                logger.warning(f"[KATANA] No URLs found. stdout preview: {(result.stdout or '')[:200]}")
            return urls, None
        else:
            stdout_preview = (result.stdout or "").strip()[:400]
            stderr_preview = (result.stderr or "").strip()[:400]
            logger.warning(f"[KATANA] Exit code {result.returncode}, found {len(urls)} URLs. stdout='{stdout_preview}' stderr='{stderr_preview}'")
            # Return URLs even if exit code is non-zero (Katana may find URLs but exit with warning)
            return urls, None if urls else f"exit={result.returncode}; stderr='{stderr_preview[:200]}'"
        
    except subprocess.TimeoutExpired:
        msg = "[KATANA] Timeout after 180s"
        logger.warning(msg)
        return [], msg
    except Exception as e:
        logger.error(f"[KATANA] Error: {e}", exc_info=True)
        return [], str(e)


async def run_gau(hostname: str, max_urls: int = 500) -> List[str]:
    """
    Run GAU to discover historical URLs from web archives
    
    Args:
        hostname: Target hostname
        max_urls: Maximum URLs to collect
        
    Returns:
        List of discovered URLs
    """
    logger.info(f"[GAU] Fetching archived URLs for {hostname}")
    
    try:
        # Run gau
        cmd = [
            "gau",
            "--threads", "5",
            "--subs",  # Include subdomains
            hostname,
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes max (GAU can take longer for some targets)
        )
        
        if result.returncode != 0:
            logger.warning(f"[GAU] Failed with exit code {result.returncode}, stderr: {result.stderr[:200] if result.stderr else 'None'}")
            # Even if exit code is non-zero, try to parse any URLs we got
            if result.stdout:
                urls = []
                for line in result.stdout.strip().split('\n'):
                    line = line.strip()
                    if line and line.startswith('http'):
                        urls.append(line)
                        if len(urls) >= max_urls:
                            break
                if urls:
                    logger.info(f"[GAU] Found {len(urls)} URLs despite non-zero exit code")
                    return urls
            return []
        
        # Parse URLs from output
        urls = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line and line.startswith('http'):
                urls.append(line)
                if len(urls) >= max_urls:
                    break
        
        logger.info(f"[GAU] Found {len(urls)} URLs")
        return urls
        
    except subprocess.TimeoutExpired as e:
        logger.warning(f"[GAU] Timeout after 120s - GAU may need more time for some targets")
        # TimeoutExpired doesn't have stdout, so we can't recover partial results
        # Return empty list - this is expected for some targets
        return []
    except Exception as e:
        logger.error(f"[GAU] Error: {e}", exc_info=True)
        return []


def _normalize_url(url: str) -> str:
    """Normalize a single URL: remove fragments, collapse double slashes, normalize trailing slash."""
    try:
        parsed = urlparse(url)
        # Remove fragment
        path = parsed.path or '/'
        # Collapse double slashes in path
        while '//' in path:
            path = path.replace('//', '/')
        # Normalize trailing slash: keep / for root, remove for others unless path has extension
        if path != '/' and path.endswith('/') and '.' not in path.split('/')[-1]:
            path = path.rstrip('/')
        # Sort query params for consistent dedup
        query = ''
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            sorted_params = sorted(params.items())
            query = urlencode(sorted_params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, ''))
    except Exception:
        return url


async def run_ffuf(
    target_url: str,
    scan_level: str = "pro",
    max_results: int = 200,
) -> Tuple[List[str], Optional[str]]:
    """
    Run ffuf for directory/path discovery during enumeration.
    Uses a curated wordlist to find hidden paths on the target.

    Args:
        target_url: Base URL to fuzz (e.g., https://example.com)
        scan_level: "pro" or "advanced" (controls timeout & wordlist)
        max_results: Maximum results to return

    Returns:
        (discovered_urls, error_message_or_None)
    """
    import shutil

    logger.info(f"[FFUF] Running path discovery on {target_url} (level={scan_level})")

    # Find ffuf binary
    ffuf_binary = shutil.which("ffuf")
    if not ffuf_binary:
        for p in ["/usr/local/bin/ffuf", os.path.expanduser("~/go/bin/ffuf")]:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                ffuf_binary = p
                break
    if not ffuf_binary:
        logger.warning("[FFUF] ffuf binary not found, skipping")
        return [], "ffuf binary not found"

    # Select wordlist – prefer a local curated list, fall back to common-wordlist paths
    wordlist = None
    wordlist_candidates = [
        "/opt/thandev/wordlists/ffuf-common.txt",
        "/opt/thandev/wordlists/common.txt",
        "/opt/thandev/wordlists/ffuf-pro.txt",
        "/opt/thandev/wordlists/ffuf-small.txt",
        "/usr/share/seclists/Discovery/Web-Content/common.txt",
        "/usr/share/wordlists/dirb/common.txt",
    ]
    for wl in wordlist_candidates:
        if os.path.isfile(wl):
            wordlist = wl
            break
    if not wordlist:
        logger.warning("[FFUF] No wordlist found, skipping")
        return [], "no wordlist found"

    timeout = 120 if scan_level == "pro" else 180

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        output_path = tmp.name

    # Ensure target URL ends with FUZZ placeholder
    fuzz_url = target_url.rstrip('/') + '/FUZZ'

    cmd = [
        ffuf_binary,
        "-u", fuzz_url,
        "-w", wordlist,
        "-mc", "200,301,302,307,401,403,405",
        "-t", "50",
        "-rate", "50",
        "-o", output_path,
        "-of", "json",
        "-s",  # Silent mode
        "-recursion-depth", "0",  # No recursion for enumeration
        "-timeout", "10",  # Per-request timeout
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )

        urls: List[str] = []
        if os.path.isfile(output_path):
            try:
                with open(output_path, 'r') as f:
                    data = json.load(f)
                results = data.get("results", [])
                base = target_url.rstrip('/')
                for r in results[:max_results]:
                    input_val = r.get("input", {}).get("FUZZ", "")
                    status = r.get("status", 0)
                    if input_val and status in (200, 301, 302, 307, 401, 403, 405):
                        urls.append(f"{base}/{input_val}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"[FFUF] Failed to parse output: {e}")

        logger.info(f"[FFUF] Found {len(urls)} paths (exit={result.returncode})")
        return urls, None

    except subprocess.TimeoutExpired:
        logger.warning(f"[FFUF] Timeout after {timeout}s")
        # Try to parse partial results
        urls = []
        if os.path.isfile(output_path):
            try:
                with open(output_path, 'r') as f:
                    data = json.load(f)
                base = target_url.rstrip('/')
                for r in data.get("results", [])[:max_results]:
                    input_val = r.get("input", {}).get("FUZZ", "")
                    if input_val:
                        urls.append(f"{base}/{input_val}")
            except Exception:
                pass
        return urls, f"Timeout after {timeout}s (partial: {len(urls)} paths)"
    except Exception as e:
        logger.error(f"[FFUF] Error: {e}", exc_info=True)
        return [], str(e)
    finally:
        Path(output_path).unlink(missing_ok=True)


async def run_liveness_check(
    urls: List[str],
    allowed_hosts: List[str],
    max_urls: int = 1000,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Run httpx liveness probe on URLs to filter out dead pages (404, 410, 5xx).

    Args:
        urls: URLs to check
        allowed_hosts: Allowed hostnames for scope filtering
        max_urls: Max URLs to probe

    Returns:
        (live_url_records, dead_urls)
        live_url_records: List of dicts with url, status_code, content_length, title, content_type, final_url
    """
    import shutil

    if not urls:
        return [], []

    httpx_binary = shutil.which("httpx")
    if not httpx_binary:
        logger.warning("[LIVENESS] httpx not found, skipping liveness check")
        # Return all URLs as live (no filtering)
        return [{"url": u, "status_code": 0, "content_length": 0, "title": "", "content_type": "", "final_url": u} for u in urls], []

    # Write URLs to temp file
    probe_urls = urls[:max_urls]
    logger.info(f"[LIVENESS] Probing {len(probe_urls)} URLs")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
        tmp.write('\n'.join(probe_urls))
        url_file = tmp.name

    cmd = [
        httpx_binary,
        "-l", url_file,
        "-silent",
        "-json",
        "-follow-redirects",
        "-max-redirects", "5",
        "-status-code",
        "-content-length",
        "-content-type",
        "-title",
        "-threads", "50",
        "-rate-limit", "100",
        "-timeout", "10",
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,  # 5 min overall
        )

        live_records: List[Dict[str, Any]] = []
        dead_urls: List[str] = []

        for line in (result.stdout or '').strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            status = rec.get("status_code", rec.get("status-code", 0))
            url = rec.get("url", rec.get("input", ""))
            content_length = rec.get("content_length", rec.get("content-length", 0)) or 0

            # Discard dead: 404, 410
            if status in (404, 410):
                dead_urls.append(url)
                continue
            # Discard 5xx (server errors)
            if 500 <= status < 600:
                dead_urls.append(url)
                continue
            # Discard empty placeholder pages (200 with tiny body)
            if status == 200 and content_length < 200:
                dead_urls.append(url)
                continue
            # Keep: 200, 301, 302, 307, 308, 401, 403, 405
            if status in (200, 301, 302, 307, 308, 401, 403, 405) or (200 <= status < 400):
                live_records.append({
                    "url": url,
                    "status_code": status,
                    "content_length": content_length,
                    "title": rec.get("title", ""),
                    "content_type": rec.get("content_type", rec.get("content-type", "")),
                    "final_url": rec.get("final_url", url),
                })
            else:
                # Unknown status, keep conservatively
                live_records.append({
                    "url": url,
                    "status_code": status,
                    "content_length": content_length,
                    "title": rec.get("title", ""),
                    "content_type": rec.get("content_type", rec.get("content-type", "")),
                    "final_url": rec.get("final_url", url),
                })

        logger.info(f"[LIVENESS] {len(live_records)} live, {len(dead_urls)} dead out of {len(probe_urls)} probed")
        return live_records, dead_urls

    except subprocess.TimeoutExpired:
        logger.warning("[LIVENESS] Timeout after 300s")
        return [{"url": u, "status_code": 0, "content_length": 0, "title": "", "content_type": "", "final_url": u} for u in probe_urls], []
    except Exception as e:
        logger.error(f"[LIVENESS] Error: {e}", exc_info=True)
        return [{"url": u, "status_code": 0, "content_length": 0, "title": "", "content_type": "", "final_url": u} for u in probe_urls], []
    finally:
        Path(url_file).unlink(missing_ok=True)


async def detect_soft_404s(
    live_records: List[Dict[str, Any]],
    allowed_hosts: List[str],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Detect soft-404 pages by comparing against per-host baselines.
    For each host, requests 2 random non-existent paths and builds a fingerprint
    (body length, title, body hash). Real URLs matching the fingerprint are marked as soft-404.

    Args:
        live_records: URL records from liveness check (must have url, status_code, content_length, title)
        allowed_hosts: Allowed hostnames

    Returns:
        (clean_records, soft_404_urls)
    """
    import shutil

    if not live_records:
        return [], []

    httpx_binary = shutil.which("httpx")
    if not httpx_binary:
        logger.warning("[SOFT404] httpx not found, skipping soft-404 detection")
        return live_records, []

    # Group URLs by host scheme pair
    host_map: Dict[str, List[Dict[str, Any]]] = {}
    for rec in live_records:
        parsed = urlparse(rec["url"])
        key = f"{parsed.scheme}://{parsed.netloc}"
        host_map.setdefault(key, []).append(rec)

    # For each host, build a baseline fingerprint
    baselines: Dict[str, Dict[str, Any]] = {}  # host_key -> {lengths: [...], titles: [...], hashes: [...]}

    for host_key in host_map:
        # Generate 2 random non-existent paths
        probe_paths = [
            f"/thandev-probe-{uuid.uuid4().hex[:8]}",
            f"/thandev-probe-{uuid.uuid4().hex[:8]}/index.html",
        ]
        probe_urls = [f"{host_key}{p}" for p in probe_paths]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            tmp.write('\n'.join(probe_urls))
            probe_file = tmp.name

        cmd = [
            httpx_binary,
            "-l", probe_file,
            "-silent", "-json",
            "-follow-redirects",
            "-status-code",
            "-content-length",
            "-title",
            "-timeout", "10",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            baseline = {"lengths": [], "titles": [], "hashes": []}

            for line in (result.stdout or '').strip().split('\n'):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cl = rec.get("content_length", rec.get("content-length", 0)) or 0
                title = (rec.get("title", "") or "").strip().lower()
                baseline["lengths"].append(cl)
                baseline["titles"].append(title)

            baselines[host_key] = baseline
        except Exception as e:
            logger.debug(f"[SOFT404] Failed to build baseline for {host_key}: {e}")
        finally:
            Path(probe_file).unlink(missing_ok=True)

    # Now filter live records against baselines
    not_found_titles = {'404', 'not found', 'page not found', 'error', '404 not found', 'page doesn\'t exist'}
    clean_records: List[Dict[str, Any]] = []
    soft_404_urls: List[str] = []

    for rec in live_records:
        parsed = urlparse(rec["url"])
        host_key = f"{parsed.scheme}://{parsed.netloc}"
        baseline = baselines.get(host_key)

        is_soft_404 = False

        if baseline and rec.get("status_code") == 200:
            cl = rec.get("content_length", 0) or 0
            title = (rec.get("title", "") or "").strip().lower()

            # Check 1: Title matches 404-like pattern
            if title and any(nf in title for nf in not_found_titles):
                is_soft_404 = True

            # Check 2: Content length within ±10% of any baseline length
            if not is_soft_404 and baseline["lengths"]:
                for bl in baseline["lengths"]:
                    if bl > 0 and abs(cl - bl) / max(bl, 1) <= 0.10:
                        is_soft_404 = True
                        break

            # Check 3: Title matches baseline title (and baseline title is non-empty)
            if not is_soft_404 and baseline["titles"]:
                for bt in baseline["titles"]:
                    if bt and title == bt:
                        is_soft_404 = True
                        break

        if is_soft_404:
            soft_404_urls.append(rec["url"])
        else:
            clean_records.append(rec)

    logger.info(f"[SOFT404] {len(clean_records)} clean, {len(soft_404_urls)} soft-404s detected")
    return clean_records, soft_404_urls


def normalize_and_merge_urls(
    katana_urls: List[str],
    gau_urls: List[str],
    allowed_hosts: List[str]
) -> Dict[str, Any]:
    """
    Normalize, deduplicate, and categorize URLs
    
    Args:
        katana_urls: URLs from Katana
        gau_urls: URLs from GAU
        allowed_hosts: List of allowed hostnames
        
    Returns:
        Dict with merged URLs, param URLs, unique paths, and interesting endpoints
    """
    logger.info(f"[MERGE] Normalizing {len(katana_urls)} + {len(gau_urls)} URLs")
    
    # Combine, normalize, and deduplicate
    all_urls = set()
    for u in katana_urls + gau_urls:
        all_urls.add(_normalize_url(u))
    
    # Filter to allowed hosts
    filtered_urls = set()
    for url in all_urls:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or parsed.netloc
            if any(hostname == host or hostname.endswith(f".{host}") for host in allowed_hosts):
                filtered_urls.add(url)
        except:
            continue
    
    # Filter out static resources (images, fonts, css, js, media)
    static_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.webp',
        '.css', '.js', '.map',
        '.woff', '.woff2', '.ttf', '.eot',
        '.mp4', '.mp3', '.avi', '.mov', '.wmv',
        '.pdf', '.zip', '.tar', '.gz',
    }
    
    non_static_urls = set()
    for url in filtered_urls:
        parsed = urlparse(url)
        path = parsed.path.lower()
        if not any(path.endswith(ext) for ext in static_extensions):
            non_static_urls.add(url)
    
    # Extract URLs with parameters
    param_urls = []
    for url in non_static_urls:
        parsed = urlparse(url)
        if parsed.query:
            param_urls.append(url)
    
    # Extract unique paths (without query strings)
    unique_paths = set()
    for url in non_static_urls:
        parsed = urlparse(url)
        path = parsed.path
        if path:
            unique_paths.add(path)
    
    # Categorize interesting endpoints
    interesting = {
        "auth": [],
        "admin": [],
        "api": [],
        "docs": [],
        "uploads": [],
        "graphql": [],
        "swagger": [],
    }
    
    auth_patterns = ['/login', '/signin', '/auth', '/register', '/signup', '/logout']
    admin_patterns = ['/admin', '/dashboard', '/panel', '/manage', '/console']
    api_patterns = ['/api/', '/v1/', '/v2/', '/rest/', '/graphql']
    docs_patterns = ['/docs', '/swagger', '/api-docs', '/openapi', '/redoc']
    upload_patterns = ['/upload', '/file', '/media', '/assets']
    graphql_patterns = ['/graphql', '/gql']
    swagger_patterns = ['/swagger', '/swagger-ui', '/api-docs']
    
    for url in non_static_urls:
        url_lower = url.lower()
        
        if any(pattern in url_lower for pattern in auth_patterns):
            interesting["auth"].append(url)
        if any(pattern in url_lower for pattern in admin_patterns):
            interesting["admin"].append(url)
        if any(pattern in url_lower for pattern in api_patterns):
            interesting["api"].append(url)
        if any(pattern in url_lower for pattern in docs_patterns):
            interesting["docs"].append(url)
        if any(pattern in url_lower for pattern in upload_patterns):
            interesting["uploads"].append(url)
        if any(pattern in url_lower for pattern in graphql_patterns):
            interesting["graphql"].append(url)
        if any(pattern in url_lower for pattern in swagger_patterns):
            interesting["swagger"].append(url)
    
    logger.info(
        f"[MERGE] Filtered to {len(non_static_urls)} URLs, "
        f"{len(param_urls)} with params, {len(unique_paths)} unique paths"
    )
    
    all_urls_list = list(non_static_urls)[:1000]  # Cap at 1000 for storage
    return {
        "all_urls_count": len(non_static_urls),
        "all_urls": all_urls_list,
        "unique_urls_count": len(non_static_urls),  # Same as all_urls (already deduped)
        "unique_urls": all_urls_list,  # Alias for frontend display
        "param_urls_count": len(param_urls),
        "param_urls": param_urls[:500],  # Cap at 500
        "unique_paths": list(unique_paths)[:500],  # Cap at 500
        "interesting": {
            k: v[:50] for k, v in interesting.items()  # Cap each category at 50
        }
    }


def build_tool_target_lists(merged_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build typed target lists for each downstream tool from the merged inventory.
    Each tool gets only the URL types it needs.

    Returns:
        Dict with keys: nuclei, dalfox, sqlmap, zap_start, zap_seeds
    """
    all_urls = merged_data.get("all_urls", [])
    param_urls = merged_data.get("param_urls", [])
    interesting = merged_data.get("interesting", {})

    # -- Static extensions to penalise --
    _static_exts = {'.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico',
                    '.webp', '.woff', '.woff2', '.ttf', '.eot', '.map'}

    def _score_url(url: str) -> int:
        """Priority score – higher is more interesting."""
        score = 0
        url_lower = url.lower()
        parsed = urlparse(url_lower)
        path = parsed.path

        # High-value path keywords
        for kw in ('admin', 'api', 'graphql', 'login', 'oauth', 'callback', 'auth',
                    'register', 'signup', 'dashboard', 'upload', 'webhook'):
            if kw in path:
                score += 3
                break

        # Has query parameters
        if parsed.query:
            score += 3

        # Static extension penalty
        ext = os.path.splitext(path)[1]
        if ext in _static_exts:
            score -= 5

        return score

    # ---- Nuclei targets ----
    # Unique hosts/base URLs + a curated set of high-value endpoints (capped at 100)
    host_set: Set[str] = set()
    nuclei_extras: List[str] = []
    for u in all_urls:
        parsed = urlparse(u)
        base = f"{parsed.scheme}://{parsed.netloc}"
        host_set.add(base)
    # Add interesting endpoints
    for cat in ('auth', 'admin', 'api', 'graphql', 'swagger'):
        nuclei_extras.extend(interesting.get(cat, [])[:10])
    nuclei_targets = list(host_set) + nuclei_extras
    nuclei_targets = list(dict.fromkeys(nuclei_targets))[:100]  # dedup & cap

    # ---- Dalfox targets ----
    # Only parameterized URLs (sorted by score, capped at 200)
    dalfox_scored = [(u, _score_url(u)) for u in param_urls]
    dalfox_scored.sort(key=lambda x: x[1], reverse=True)
    dalfox_targets = [u for u, _ in dalfox_scored[:200]]

    # ---- SQLMap targets ----
    # High-confidence param URLs scored for DB-likelihood (capped at 30)
    db_keywords = ('id', 'user', 'uid', 'item', 'product', 'order', 'page', 'cat',
                   'category', 'pid', 'search', 'query', 'sort', 'filter', 'type')

    def _sqlmap_score(url: str) -> int:
        s = _score_url(url)
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        for pname in params:
            if pname.lower() in db_keywords:
                s += 5
        return s

    sqlmap_scored = [(u, _sqlmap_score(u)) for u in param_urls]
    sqlmap_scored.sort(key=lambda x: x[1], reverse=True)
    sqlmap_targets = [u for u, _ in sqlmap_scored[:30]]

    # ---- ZAP targets ----
    # Start URL (first in all_urls or the base) + seed list from interesting endpoints
    zap_start = all_urls[0] if all_urls else ""
    zap_seeds: List[str] = []
    for cat in ('auth', 'admin', 'api'):
        zap_seeds.extend(interesting.get(cat, [])[:5])
    zap_seeds = list(dict.fromkeys(zap_seeds))[:20]

    tool_targets = {
        "nuclei": nuclei_targets,
        "dalfox": dalfox_targets,
        "sqlmap": sqlmap_targets,
        "zap_start": zap_start,
        "zap_seeds": zap_seeds,
    }

    logger.info(
        f"[ROUTING] Tool targets: nuclei={len(nuclei_targets)}, "
        f"dalfox={len(dalfox_targets)}, sqlmap={len(sqlmap_targets)}, "
        f"zap_seeds={len(zap_seeds)}"
    )
    return tool_targets


async def run_arjun_single_url(url: str, timeout_seconds: int = 15) -> Optional[Dict[str, Any]]:
    """
    Run Arjun on a single URL with timeout
    
    Args:
        url: URL to test
        timeout_seconds: Per-URL timeout
        
    Returns:
        Dict with url and params if found, None otherwise
    """
    try:
        # Create temp file for JSON output
        output_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        output_file.close()
        output_path = output_file.name
        
        cmd = [
            "arjun",
            "-u", url,
            "-o", output_path,
            "-t", "5",  # Lower threads per URL
            "--stable",
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        
        if result.returncode != 0:
            Path(output_path).unlink(missing_ok=True)
            return None
        
        # Parse JSON output
        params = []
        try:
            if Path(output_path).exists():
                with open(output_path, 'r') as f:
                    output = f.read().strip()
                if output:
                    data = json.loads(output)
                    if isinstance(data, dict) and url in data:
                        params = data[url]
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and item.get('url') == url:
                                params = item.get('params', [])
                                break
        except json.JSONDecodeError:
            pass
        finally:
            Path(output_path).unlink(missing_ok=True)
        
        if params:
            return {"url": url, "params": params}
        return None
        
    except subprocess.TimeoutExpired:
        logger.debug(f"[ARJUN] Per-URL timeout for {url}")
        return None
    except Exception as e:
        logger.debug(f"[ARJUN] Error for {url}: {e}")
        return None


async def run_arjun(urls: List[str], max_targets: int = 30, scan_level: str = "pro") -> Dict[str, Any]:
    """
    Run Arjun parameter discovery on curated URLs with per-URL timeout
    
    Args:
        urls: List of URLs to test
        max_targets: Maximum URLs to test (ignored, uses scan_level limits)
        scan_level: "pro" (10 URLs, 15s each) or "advanced" (20 URLs, 20s each)
        
    Returns:
        Dict with tested URLs and discovered parameters
    """
    # Scan level specific limits
    if scan_level == "advanced":
        url_limit = 20
        per_url_timeout = 25
    else:  # pro
        url_limit = 10
        per_url_timeout = 20
    
    target_urls = urls[:url_limit]
    
    if not target_urls:
        return {"tested_urls": [], "params_by_url": {}}
    
    logger.info(f"[ARJUN] Testing {len(target_urls)} URLs (limit={url_limit}, timeout={per_url_timeout}s per URL)")
    
    # Process URLs one by one to get partial results on timeout
    params_by_url = {}
    tested_urls = []
    
    for i, url in enumerate(target_urls):
        logger.debug(f"[ARJUN] Testing URL {i+1}/{len(target_urls)}: {url[:80]}...")
        
        result = await run_arjun_single_url(url, timeout_seconds=per_url_timeout)
        tested_urls.append(url)
        
        if result and result.get("params"):
            params_by_url[result["url"]] = result["params"]
            logger.info(f"[ARJUN] Found {len(result['params'])} params for {url[:60]}...")
    
    logger.info(f"[ARJUN] Completed: tested {len(tested_urls)} URLs, found params on {len(params_by_url)} URLs")
    return {
        "tested_urls": tested_urls,
        "params_by_url": params_by_url
    }


async def run_enumeration(
    target_url: str,
    scan_level: str,
    emit_event_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    Run full enumeration phase for Pro/Advanced scans.

    Pipeline: HTTPX → Katana → GAU → ffuf → Merge+Normalize → Liveness → Soft-404 → Arjun → Tool Routing

    Args:
        target_url: Target URL to enumerate
        scan_level: Scan level (pro or advanced)
        emit_event_callback: Optional callback to emit progress events

    Returns:
        Asset inventory dictionary
    """
    logger.info(f"[ENUMERATION] Starting for {target_url} (level={scan_level})")

    # Create inventory
    inventory = AssetInventory(target_url)

    # Helper to emit events
    async def emit_event(tool: str, stage: str, message: str, progress: float = None, meta: dict = None):
        if emit_event_callback:
            await emit_event_callback(
                phase="enumerate",
                tool=tool,
                stage=stage,
                message=message,
                progress=progress,
                meta=meta
            )

    # ── Step 1: HTTPX – canonical URL & tech detection ──
    await emit_event("httpx", "running", "Detecting technologies and canonical URL...")
    httpx_result = await run_httpx(target_url)
    if "tech" not in httpx_result or not isinstance(httpx_result.get("tech"), list):
        httpx_result["tech"] = []
    inventory.discovery["httpx"].update(httpx_result)

    final_url = httpx_result.get("final_url", target_url)
    inventory.scope["final_url"] = final_url

    parsed = urlparse(final_url)
    hostname = parsed.hostname or parsed.netloc
    inventory.scope["allowed_hosts"] = [hostname]

    await emit_event("httpx", "completed", f"Detected {len(httpx_result.get('tech', []))} technologies", progress=1.0)

    # ── Step 2: Katana – web crawling ──
    depth = 3 if scan_level == "pro" else 4
    max_urls = 300 if scan_level == "pro" else 500

    await emit_event("katana", "running", f"Crawling URLs (depth={depth})...")
    katana_urls, katana_error = await run_katana(final_url, depth=depth, max_urls=max_urls)
    inventory.discovery["katana"]["urls_count"] = len(katana_urls)
    inventory.discovery["katana"]["urls"] = katana_urls[:100]
    if katana_error:
        inventory.discovery["katana"]["error"] = katana_error
        await emit_event("katana", "failed", f"No URLs (Katana error)", progress=1.0, meta={"error": katana_error})
    else:
        await emit_event("katana", "completed", f"Found {len(katana_urls)} URLs", progress=1.0, meta={"urls_found": len(katana_urls)})

    # ── Step 3: GAU – historical URLs ──
    await emit_event("gau", "running", "Fetching archived URLs...")
    gau_urls = await run_gau(hostname, max_urls=max_urls)
    inventory.discovery["gau"]["urls_count"] = len(gau_urls)
    inventory.discovery["gau"]["urls"] = gau_urls[:100]

    await emit_event("gau", "completed", f"Found {len(gau_urls)} archived URLs", progress=1.0, meta={"urls_found": len(gau_urls)})

    # ── Step 4: ffuf – directory/path discovery ──
    await emit_event("ffuf", "running", "Discovering hidden paths...")
    ffuf_urls, ffuf_error = await run_ffuf(final_url, scan_level=scan_level)
    inventory.discovery.setdefault("ffuf", {})
    inventory.discovery["ffuf"]["urls_count"] = len(ffuf_urls)
    inventory.discovery["ffuf"]["urls"] = ffuf_urls[:100]
    if ffuf_error:
        inventory.discovery["ffuf"]["error"] = ffuf_error
        await emit_event("ffuf", "completed", f"ffuf: {ffuf_error} ({len(ffuf_urls)} paths)", progress=1.0)
    else:
        await emit_event("ffuf", "completed", f"Discovered {len(ffuf_urls)} hidden paths", progress=1.0, meta={"paths_found": len(ffuf_urls)})

    # ── Step 5: Merge & normalize all URLs ──
    await emit_event("merge", "running", "Normalizing and categorizing URLs...")
    # Combine katana + gau + ffuf URLs for merging
    all_raw_urls = katana_urls + gau_urls + ffuf_urls
    merged = normalize_and_merge_urls(all_raw_urls, [], inventory.scope["allowed_hosts"])
    # Note: we pass all URLs as first arg and empty list as second since we already combined them

    await emit_event("merge", "completed", f"Merged to {merged['all_urls_count']} unique URLs", progress=1.0)

    # ── Step 6: Liveness check – filter dead pages ──
    await emit_event("liveness", "running", f"Probing {merged['all_urls_count']} URLs for liveness...")
    live_records, dead_urls = await run_liveness_check(
        merged["all_urls"], inventory.scope["allowed_hosts"]
    )
    inventory.discovery.setdefault("liveness", {})
    inventory.discovery["liveness"]["live_count"] = len(live_records)
    inventory.discovery["liveness"]["dead_count"] = len(dead_urls)
    inventory.discovery["liveness"]["dead_urls"] = dead_urls[:50]  # Store sample

    await emit_event("liveness", "completed", f"{len(live_records)} live, {len(dead_urls)} dead", progress=1.0)

    # ── Step 7: Soft-404 detection ──
    await emit_event("soft404", "running", "Detecting soft-404 pages...")
    clean_records, soft_404_urls = await detect_soft_404s(
        live_records, inventory.scope["allowed_hosts"]
    )
    inventory.discovery.setdefault("soft404", {})
    inventory.discovery["soft404"]["clean_count"] = len(clean_records)
    inventory.discovery["soft404"]["soft_404_count"] = len(soft_404_urls)
    inventory.discovery["soft404"]["soft_404_urls"] = soft_404_urls[:50]

    await emit_event("soft404", "completed", f"{len(clean_records)} clean, {len(soft_404_urls)} soft-404s removed", progress=1.0)

    # Update merged data with verified live URLs only
    live_url_set = {r["url"] for r in clean_records}
    merged["all_urls"] = [u for u in merged["all_urls"] if u in live_url_set]
    merged["all_urls_count"] = len(merged["all_urls"])
    merged["unique_urls_count"] = merged["all_urls_count"]
    merged["unique_urls"] = merged["all_urls"]
    merged["param_urls"] = [u for u in merged["param_urls"] if u in live_url_set]
    merged["param_urls_count"] = len(merged["param_urls"])
    inventory.discovery["merged"] = merged

    # ── Step 8: Arjun – parameter discovery ──
    max_arjun_targets = 30 if scan_level == "pro" else 60

    arjun_targets = []
    arjun_targets.extend(merged["param_urls"][:max_arjun_targets // 2])

    for category in ["auth", "api", "admin"]:
        arjun_targets.extend(merged["interesting"][category][:10])

    if not arjun_targets and merged["all_urls"]:
        logger.info(f"[ARJUN] No param URLs or interesting endpoints found, using all URLs for parameter discovery")
        arjun_targets = merged["all_urls"][:max_arjun_targets]

    arjun_targets = list(set(arjun_targets))[:max_arjun_targets]

    if arjun_targets:
        await emit_event("arjun", "running", f"Discovering parameters on {len(arjun_targets)} URLs...")
        arjun_result = await run_arjun(arjun_targets, max_targets=max_arjun_targets, scan_level=scan_level)
        inventory.discovery["arjun"] = arjun_result

        params_found = len(arjun_result["params_by_url"])
        await emit_event("arjun", "completed", f"Found parameters on {params_found} URLs", progress=1.0, meta={"params_found": params_found})
    else:
        await emit_event("arjun", "skipped", "No URLs available for parameter discovery")

    # ── Step 9: Build tool target lists (smart routing) ──
    tool_targets = build_tool_target_lists(merged)
    inventory.discovery["merged"]["tool_targets"] = tool_targets

    await emit_event("routing", "completed",
        f"Routed: nuclei={len(tool_targets['nuclei'])}, dalfox={len(tool_targets['dalfox'])}, "
        f"sqlmap={len(tool_targets['sqlmap'])}, zap_seeds={len(tool_targets['zap_seeds'])}",
        progress=1.0)

    # Finalize
    inventory.timestamps["ended_at"] = datetime.now(timezone.utc).isoformat()

    logger.info(
        f"[ENUMERATION] Completed: {merged['all_urls_count']} live URLs (after filtering), "
        f"{len(merged['param_urls'])} with params, "
        f"{len(inventory.discovery['arjun']['params_by_url'])} with discovered params, "
        f"routed to nuclei={len(tool_targets['nuclei'])}/dalfox={len(tool_targets['dalfox'])}"
        f"/sqlmap={len(tool_targets['sqlmap'])}"
    )

    return inventory.to_dict()

