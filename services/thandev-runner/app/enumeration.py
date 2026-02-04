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
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Set, Optional, Tuple
from urllib.parse import urlparse, urljoin
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
        
        # Prefer plain mode first (more reliable in containerized envs)
        base_cmd = [
            "katana",
            "-u", target_url,
            "-d", str(depth),
            "-kf", "all",            # Known files
            "-silent",
            "-no-color",
        ]
        
        # Try plain mode; if it yields zero URLs, fallback to headless/system-chrome
        def run_cmd(cmd):
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes max
            )
        
        logger.debug(f"[KATANA] CMD(primary): {' '.join(base_cmd)}")
        result = run_cmd(base_cmd)
        
        if result.returncode != 0 and not urls:
            stdout_preview = (result.stdout or "").strip()[:400]
            stderr_preview = (result.stderr or "").strip()[:400]
            msg = f"exit={result.returncode}; stdout='{stdout_preview}' stderr='{stderr_preview}'"
            logger.warning(f"[KATANA] Failed: {msg}")
            return [], msg
        
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
        
        # Fallback to headless if no URLs found
        if result.returncode == 0 and urls:
            logger.info(f"[KATANA] Found {len(urls)} URLs (plain mode)")
            return urls, None
        
        logger.info(f"[KATANA] Plain mode yielded {len(urls)} URLs (exit={result.returncode}); trying headless fallback")
        headless_cmd = base_cmd + ["-headless", "-system-chrome", "-no-sandbox"]
        logger.debug(f"[KATANA] CMD(fallback): {' '.join(headless_cmd)}")
        result_fallback = run_cmd(headless_cmd)
        urls = parse_urls(result_fallback.stdout or "")
        
        if result_fallback.returncode != 0:
            stdout_preview = (result_fallback.stdout or "").strip()[:400]
            stderr_preview = (result_fallback.stderr or "").strip()[:400]
            msg = f"exit={result_fallback.returncode}; stdout='{stdout_preview}' stderr='{stderr_preview}'"
            logger.warning(f"[KATANA] Fallback failed: {msg}")
            return urls, msg if not urls else None
        
        logger.info(f"[KATANA] Found {len(urls)} URLs (headless fallback)")
        return urls, None
        
    except subprocess.TimeoutExpired:
        msg = "[KATANA] Timeout after 120s"
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
        
    except subprocess.TimeoutExpired:
        logger.warning(f"[GAU] Timeout after 120s - GAU may need more time for some targets")
        # Try to parse any URLs we got before timeout
        if hasattr(result, 'stdout') and result.stdout:
            urls = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and line.startswith('http'):
                    urls.append(line)
                    if len(urls) >= max_urls:
                        break
            if urls:
                logger.info(f"[GAU] Found {len(urls)} URLs before timeout")
                return urls
        return []
    except Exception as e:
        logger.error(f"[GAU] Error: {e}", exc_info=True)
        return []


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
    
    # Combine and deduplicate
    all_urls = set(katana_urls + gau_urls)
    
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
    Run full enumeration phase for Pro/Advanced scans
    
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
    
    # Step 1: HTTPX - Get canonical URL and tech
    await emit_event("httpx", "running", "Detecting technologies and canonical URL...")
    httpx_result = await run_httpx(target_url)
    # Ensure tech is always a list and merge with existing structure
    if "tech" not in httpx_result or not isinstance(httpx_result.get("tech"), list):
        httpx_result["tech"] = []
    # Merge result into existing httpx structure (preserves initialized structure)
    inventory.discovery["httpx"].update(httpx_result)
    
    # Update scope with final URL
    final_url = httpx_result.get("final_url", target_url)
    inventory.scope["final_url"] = final_url
    
    # Extract hostname for scope
    parsed = urlparse(final_url)
    hostname = parsed.hostname or parsed.netloc
    inventory.scope["allowed_hosts"] = [hostname]
    
    await emit_event("httpx", "completed", f"Detected {len(httpx_result.get('tech', []))} technologies", progress=1.0)
    
    # Step 2: Katana - Crawl for URLs
    depth = 3 if scan_level == "pro" else 4
    max_urls = 300 if scan_level == "pro" else 500
    
    await emit_event("katana", "running", f"Crawling URLs (depth={depth})...")
    katana_urls, katana_error = await run_katana(final_url, depth=depth, max_urls=max_urls)
    inventory.discovery["katana"]["urls_count"] = len(katana_urls)
    inventory.discovery["katana"]["urls"] = katana_urls[:100]  # Store sample
    if katana_error:
        inventory.discovery["katana"]["error"] = katana_error
        await emit_event("katana", "failed", f"No URLs (Katana error)", progress=1.0, meta={"error": katana_error})
    else:
        await emit_event("katana", "completed", f"Found {len(katana_urls)} URLs", progress=1.0, meta={"urls_found": len(katana_urls)})
    
    # Step 3: GAU - Get archived URLs
    await emit_event("gau", "running", "Fetching archived URLs...")
    gau_urls = await run_gau(hostname, max_urls=max_urls)
    inventory.discovery["gau"]["urls_count"] = len(gau_urls)
    inventory.discovery["gau"]["urls"] = gau_urls[:100]  # Store sample
    
    await emit_event("gau", "completed", f"Found {len(gau_urls)} archived URLs", progress=1.0, meta={"urls_found": len(gau_urls)})
    
    # Step 4: Merge and categorize URLs
    await emit_event("merge", "running", "Normalizing and categorizing URLs...")
    merged = normalize_and_merge_urls(katana_urls, gau_urls, inventory.scope["allowed_hosts"])
    inventory.discovery["merged"] = merged
    
    await emit_event("merge", "completed", f"Merged to {merged['all_urls_count']} unique URLs", progress=1.0)
    
    # Step 5: Arjun - Parameter discovery
    max_arjun_targets = 30 if scan_level == "pro" else 60
    
    # Select targets for Arjun: param URLs + interesting endpoints
    arjun_targets = []
    arjun_targets.extend(merged["param_urls"][:max_arjun_targets // 2])
    
    # Add interesting endpoints
    for category in ["auth", "api", "admin"]:
        arjun_targets.extend(merged["interesting"][category][:10])
    
    # Deduplicate and limit
    arjun_targets = list(set(arjun_targets))[:max_arjun_targets]
    
    if arjun_targets:
        await emit_event("arjun", "running", f"Discovering parameters on {len(arjun_targets)} URLs...")
        arjun_result = await run_arjun(arjun_targets, max_targets=max_arjun_targets, scan_level=scan_level)
        inventory.discovery["arjun"] = arjun_result
        
        params_found = len(arjun_result["params_by_url"])
        await emit_event("arjun", "completed", f"Found parameters on {params_found} URLs", progress=1.0, meta={"params_found": params_found})
    else:
        await emit_event("arjun", "skipped", "No suitable targets for parameter discovery")
    
    # Finalize
    inventory.timestamps["ended_at"] = datetime.now(timezone.utc).isoformat()
    
    logger.info(
        f"[ENUMERATION] Completed: {merged['all_urls_count']} URLs, "
        f"{len(merged['param_urls'])} with params, "
        f"{len(inventory.discovery['arjun']['params_by_url'])} with discovered params"
    )
    
    return inventory.to_dict()
