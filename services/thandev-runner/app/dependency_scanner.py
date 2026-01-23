"""
Dependency scanning jobs: url_sca and repo_sca
"""
import logging
import subprocess
import json
import tempfile
import shutil
import os
import time
import httpx
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


async def run_url_sca_job(
    scan_id: str,
    target_url: str,
    callback_url: str,
    backend_url: str,
    runner_callback_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run URL-based dependency scanning (PRO scan).
    
    Steps:
    1. Use httpx to fetch headers + status + title
    2. Run Wappalyzer CLI to identify technologies + versions
    3. Run retire.js against the target (fetch HTML, discover scripts, run signatures)
    4. Normalize output into JSON payload
    5. Post results to callback URL
    
    Args:
        scan_id: Scan job ID
        target_url: Target URL to scan
        callback_url: Backend callback URL
        backend_url: Backend base URL for progress updates
        runner_callback_secret: Secret for HMAC signature
    
    Returns:
        Normalized JSON payload
    """
    start_time = time.time()
    meta = {
        "tool_versions": {},
        "duration_ms": 0,
    }
    
    fingerprint = {
        "status": 0,
        "title": "",
        "server": "",
        "cdn": "",
        "technologies": [],
        "confidence": 0.0,
    }
    technologies = []
    client_deps = []
    findings = []
    tools_missing = []
    
    try:
        # Step 1: HTTP probe with httpx
        await send_progress(backend_url, scan_id, "httpx", "running", "Fetching target URL...")
        try:
            fingerprint = await http_probe(target_url)
        except Exception as e:
            logger.warning(f"HTTP probe failed: {e}")
            fingerprint = {
                "status": 0,
                "title": "",
                "server": "",
                "cdn": "",
            }
        
        # Step 2: Wappalyzer
        await send_progress(backend_url, scan_id, "wappalyzer", "running", "Identifying technologies...")
        wappalyzer_start = time.time()
        wappalyzer_success = False
        wappalyzer_error = None
        try:
            technologies = await run_wappalyzer(target_url)
            fingerprint["technologies"] = technologies
            wappalyzer_success = True
        except FileNotFoundError as e:
            logger.warning(f"Technology detection failed: {e}")
            tools_missing.append("wappalyzer")
            wappalyzer_error = str(e)
        except Exception as e:
            logger.warning(f"Wappalyzer failed: {e}")
            wappalyzer_error = str(e)
        
        # Create ToolResult entry for wappalyzer
        wappalyzer_duration = time.time() - wappalyzer_start
        wappalyzer_count = len(technologies) if technologies else 0
        # Log what we're sending
        meta_to_send = {"technologies": technologies} if technologies else None
        logger.warning(f"[WAPPALYZER-DEBUG] Sending wappalyzer result: technologies={len(technologies) if technologies else 0}, meta_data={meta_to_send}")
        
        await create_dependency_tool_result(
            backend_url=backend_url,
            scan_id=scan_id,
            tool_name="wappalyzer",
            tool_id="wappalyzer",
            success=wappalyzer_success,
            execution_time=wappalyzer_duration,
            findings_count=wappalyzer_count,
            error_message=wappalyzer_error,
            meta_data=meta_to_send,
        )
        
        # Step 3: Retire.js
        await send_progress(backend_url, scan_id, "retire", "running", "Scanning client-side JavaScript...")
        retire_start = time.time()
        retire_success = False
        retire_error = None
        try:
            client_deps, findings = await run_retire_js(target_url)
            retire_success = True
        except FileNotFoundError:
            logger.warning("retire.js not found, skipping client-side dependency scanning")
            tools_missing.append("retire")
            retire_error = "retire.js not found"
        except Exception as e:
            logger.warning(f"Retire.js failed: {e}")
            retire_error = str(e)
        
        # Create ToolResult entry for retire.js
        retire_duration = time.time() - retire_start
        retire_findings_count = len(findings) if findings else 0
        retire_meta = {}
        if client_deps:
            retire_meta["client_dependencies"] = client_deps
        if findings:
            retire_meta["findings"] = findings
        await create_dependency_tool_result(
            backend_url=backend_url,
            scan_id=scan_id,
            tool_name="retire",
            tool_id="retire",
            success=retire_success,
            execution_time=retire_duration,
            findings_count=retire_findings_count,
            error_message=retire_error,
            meta_data=retire_meta if retire_meta else None,
        )
        
        # Calculate confidence
        confidence = calculate_confidence(fingerprint, technologies, client_deps)
        fingerprint["confidence"] = confidence
        
        duration_ms = int((time.time() - start_time) * 1000)
        meta["duration_ms"] = duration_ms
        if tools_missing:
            meta["tools_missing"] = tools_missing
        
        # Build payload - ALWAYS create payload even if tools are missing
        payload = {
            "mode": "url_sca",
            "target": target_url,
            "fingerprint": fingerprint,
            "client_dependencies": client_deps or [],
            "findings": findings or [],
            "meta": meta,
        }
        
        # Post to callback - ALWAYS post, even with partial results
        await post_callback(callback_url, scan_id, "url_sca", payload, runner_callback_secret)
        await send_progress(backend_url, scan_id, "url_sca", "done", "URL dependency scan completed")
        
        return payload
        
    except Exception as e:
        logger.error(f"URL-SCA job failed: {e}", exc_info=True)
        
        # Create error payload - ALWAYS send something
        duration_ms = int((time.time() - start_time) * 1000)
        error_payload = {
            "mode": "url_sca",
            "target": target_url,
            "fingerprint": fingerprint,
            "client_dependencies": [],
            "findings": [],
            "meta": {
                "tool_versions": {},
                "duration_ms": duration_ms,
                "error": str(e),
                "tools_missing": tools_missing,
            },
        }
        
        # Try to post error payload
        try:
            await post_callback(callback_url, scan_id, "url_sca", error_payload, runner_callback_secret)
            await send_progress(backend_url, scan_id, "url_sca", "error", f"Error: {str(e)}")
        except Exception as callback_error:
            logger.error(f"Failed to post error callback: {callback_error}", exc_info=True)
        
        # Re-raise to mark job as failed in logs, but payload was sent
        raise


async def run_repo_sca_job(
    scan_id: str,
    repo_info: Dict[str, Any],
    callback_url: str,
    backend_url: str,
    runner_callback_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run repository-based dependency scanning (ADVANCED scan).
    
    Steps:
    1. Request installation token from backend
    2. Download repo ZIP archive
    3. Extract to temp directory
    4. Run osv-scanner
    5. Normalize output into JSON payload
    6. Post results to callback URL
    
    Args:
        scan_id: Scan job ID
        repo_info: Repository information (provider, installation_id, provider_repo_id, full_name, default_branch)
        callback_url: Backend callback URL
        backend_url: Backend base URL
        runner_callback_secret: Secret for HMAC signature
    
    Returns:
        Normalized JSON payload
    """
    start_time = time.time()
    meta = {
        "tool_versions": {},
        "duration_ms": 0,
    }
    
    temp_dir = None
    try:
        # Step 1: Get installation token
        await send_progress(backend_url, scan_id, "github_token", "running", "Requesting GitHub installation token...")
        installation_token = await get_github_installation_token(
            backend_url,
            repo_info["installation_id"],
        )
        
        # Step 2: Download repo ZIP
        await send_progress(backend_url, scan_id, "download", "running", f"Downloading repository {repo_info['full_name']}...")
        temp_dir = Path(tempfile.mkdtemp(prefix=f"repo_sca_{scan_id}_"))
        repo_zip_path = await download_repo_zip(
            repo_info["full_name"],
            repo_info["default_branch"],
            installation_token,
            temp_dir,
        )
        
        # Step 3: Extract ZIP
        await send_progress(backend_url, scan_id, "extract", "running", "Extracting repository...")
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()
        await extract_zip(repo_zip_path, extract_dir)
        
        # Step 4: Run osv-scanner
        await send_progress(backend_url, scan_id, "osv_scanner", "running", "Scanning dependencies with OSV-Scanner...")
        packages, findings = await run_osv_scanner(extract_dir)
        
        duration_ms = int((time.time() - start_time) * 1000)
        meta["duration_ms"] = duration_ms
        
        # Build payload
        payload = {
            "mode": "repo_sca",
            "repo": {
                "provider": repo_info["provider"],
                "full_name": repo_info["full_name"],
                "commit": None,
                "branch": repo_info["default_branch"],
            },
            "packages": packages,
            "findings": findings,
            "meta": meta,
        }
        
        # Post to callback
        await post_callback(callback_url, scan_id, "repo_sca", payload, runner_callback_secret)
        await send_progress(backend_url, scan_id, "repo_sca", "done", "Repository dependency scan completed")
        
        return payload
        
    except Exception as e:
        logger.error(f"Repo-SCA job failed: {e}", exc_info=True)
        await send_progress(backend_url, scan_id, "repo_sca", "error", f"Error: {str(e)}")
        raise
    finally:
        # Cleanup temp directory
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


async def http_probe(target_url: str) -> Dict[str, Any]:
    """Probe target URL with httpx to get basic info."""
    try:
        # Use httpx CLI if available, otherwise use Python httpx
        result = subprocess.run(
            ["httpx", "-u", target_url, "-sc", "-title", "-server", "-cdn", "-json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout.strip())
            return {
                "status": data.get("status_code", 0),
                "title": data.get("title", ""),
                "server": data.get("server", ""),
                "cdn": data.get("cdn", ""),
            }
    except Exception as e:
        logger.warning(f"httpx probe failed: {e}")
    
    # Fallback: use Python httpx
    try:
        import httpx as httpx_lib
        async with httpx_lib.AsyncClient(timeout=30.0) as client:
            response = await client.get(target_url, follow_redirects=True)
            return {
                "status": response.status_code,
                "title": extract_title(response.text),
                "server": response.headers.get("server", ""),
                "cdn": response.headers.get("cf-ray", "") or response.headers.get("x-cache", ""),
            }
    except Exception as e:
        logger.error(f"HTTP probe failed: {e}")
        return {
            "status": 0,
            "title": "",
            "server": "",
            "cdn": "",
        }


def extract_title(html: str) -> str:
    """Extract title from HTML."""
    import re
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    return match.group(1).strip() if match else ""


async def run_wappalyzer(target_url: str) -> List[Dict[str, Any]]:
    """
    Detect technologies on target URL.
    
    Note: Wappalyzer npm packages are deprecated as of 2024. Using httpx tech-detect instead.
    """
    technologies = []
    
    # Use httpx tech-detect as primary method (wappalyzer npm packages are all deprecated)
    logger.info("Using httpx tech-detect for technology detection (wappalyzer is deprecated)")
    try:
        result = subprocess.run(
            ["httpx", "-u", target_url, "-tech-detect", "-json", "-silent"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            if not result.stdout or not result.stdout.strip():
                # Exit code 0 but no output - might be no technologies detected, which is valid
                logger.info("httpx tech-detect completed with no technologies detected (exit code 0, empty output)")
                return technologies  # Return empty list, not an error
            try:
                data = json.loads(result.stdout.strip())
                tech_detected = data.get("tech", [])
                if isinstance(tech_detected, list):
                    for tech_item in tech_detected:
                        if isinstance(tech_item, str):
                            technologies.append({
                                "name": tech_item,
                                "version": None,
                                "confidence": 0.8,
                            })
                        elif isinstance(tech_item, dict):
                            technologies.append({
                                "name": tech_item.get("name", tech_item.get("value", "")),
                                "version": tech_item.get("version"),
                                "confidence": 0.8,
                            })
                    logger.info(f"httpx tech-detect found {len(technologies)} technologies")
                else:
                    logger.info("httpx tech-detect returned no technologies (tech field is not a list)")
            except json.JSONDecodeError as e:
                logger.warning(f"httpx returned invalid JSON: {e}, stdout: {result.stdout[:200]}")
                # Don't fail completely - return empty list instead
                logger.info("Returning empty technologies list due to JSON parse error")
                return technologies
        else:
            stderr = result.stderr.strip() if result.stderr else ""
            stdout_preview = result.stdout[:200] if result.stdout else ""
            logger.warning(f"httpx tech-detect failed (exit {result.returncode}): {stderr}, stdout: {stdout_preview}")
            raise FileNotFoundError(f"httpx tech-detect failed with exit code {result.returncode}: {stderr or 'unknown error'}")
    except subprocess.TimeoutExpired:
        logger.warning("httpx tech-detect timed out after 30 seconds")
        raise FileNotFoundError("httpx tech-detect timed out")
    except FileNotFoundError:
        raise  # Re-raise if httpx binary not found
    except Exception as e:
        logger.error(f"httpx tech-detect error: {e}")
        raise FileNotFoundError(f"Technology detection failed: {e}")
    
    return technologies



async def run_retire_js(target_url: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Run retire.js to find vulnerable JavaScript libraries."""
    client_deps = []
    findings = []
    
    # Check if retire.js is installed - try multiple locations
    retire_commands = [
        ["retire"],  # Try PATH first
        ["/usr/bin/retire"],  # NodeSource installs here
        ["/usr/local/bin/retire"],  # Alternative location
        ["node", "/usr/lib/node_modules/retire/bin/retire"],  # Direct node module
    ]
    
    retire_found = False
    retire_cmd_base = None
    for cmd in retire_commands:
        try:
            check_result = subprocess.run(
                cmd + ["--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if check_result.returncode == 0:
                retire_found = True
                retire_cmd_base = cmd  # Store the full command array
                logger.debug(f"Found retire with command: {' '.join(cmd)}")
                break
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.debug(f"retire check failed for {' '.join(cmd)}: {e}")
            continue
    
    if not retire_found:
        logger.warning("retire.js not found in any expected location, skipping client-side dependency scanning")
        raise FileNotFoundError("retire.js not found or not working")
    
    if not retire_cmd_base:
        raise FileNotFoundError("retire.js not available")
    
    try:
        # Fetch HTML
        import httpx as httpx_lib
        async with httpx_lib.AsyncClient(timeout=30.0) as client:
            response = await client.get(target_url, follow_redirects=True)
            html = response.text
        
        # Extract script URLs (both src and inline scripts)
        import re
        script_urls = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        
        # Also check for inline scripts that might reference external libraries
        # This is a basic check - retire.js can't scan inline scripts directly
        logger.info(f"Found {len(script_urls)} external script URLs to scan")
        
        if not script_urls:
            logger.info(f"No external JavaScript files found on {target_url}")
            return client_deps, findings
        
        # Create temporary directory for downloaded JS files
        temp_dir = Path(tempfile.mkdtemp(prefix="retire_scan_"))
        downloaded_files = []
        
        try:
            # Download JavaScript files first (retire.js --path only works with local files)
            async with httpx_lib.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for i, script_url in enumerate(script_urls[:10]):  # Limit to first 10 scripts
                    # Handle protocol-relative URLs (//example.com/path.js)
                    if script_url.startswith('//'):
                        # Protocol-relative URL - use https by default
                        script_url = 'https:' + script_url
                    elif not script_url.startswith(('http://', 'https://')):
                        # Resolve relative URLs
                        from urllib.parse import urljoin
                        script_url = urljoin(target_url, script_url)
                    
                    try:
                        # Download the script
                        logger.debug(f"Downloading {script_url} for retire.js scanning")
                        script_response = await client.get(script_url, timeout=30.0)
                        
                        if script_response.status_code == 200:
                            # Save to temp file
                            # Use filename from URL or generate one
                            from urllib.parse import urlparse
                            parsed = urlparse(script_url)
                            filename = os.path.basename(parsed.path) or f"script_{i}.js"
                            # Sanitize filename
                            filename = "".join(c for c in filename if c.isalnum() or c in "._-")[:50]
                            if not filename.endswith('.js'):
                                filename += '.js'
                            
                            temp_file = temp_dir / filename
                            temp_file.write_bytes(script_response.content)
                            downloaded_files.append((temp_file, script_url))
                            logger.debug(f"Downloaded {script_url} to {temp_file}")
                        else:
                            logger.debug(f"Failed to download {script_url}: HTTP {script_response.status_code}")
                    except Exception as e:
                        logger.debug(f"Failed to download {script_url}: {e}")
                        continue
            
            # Now scan downloaded files with retire.js
            if not downloaded_files:
                logger.info("No JavaScript files were successfully downloaded for scanning")
                return client_deps, findings
            
            logger.info(f"Scanning {len(downloaded_files)} downloaded JavaScript files with retire.js")
            
            for temp_file, script_url in downloaded_files:
                try:
                    logger.debug(f"Scanning {temp_file} (from {script_url}) with retire.js")
                    # Use the retire command that was found during verification
                    # retire.js --path works with local files
                    # Note: retire.js uses --outputformat json, not --json
                    result = subprocess.run(
                        retire_cmd_base + ["--path", str(temp_file), "--outputformat", "json"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=str(temp_dir),  # Set working directory
                    )
                    
                    # retire.js returns exit code 13 when vulnerabilities are found, 0 when none found
                    # JSON output is always in stdout (even on exit 13)
                    # Check stdout first (JSON is always there), then stderr for errors
                    output = result.stdout.strip() if result.stdout else (result.stderr.strip() if result.stderr else "")
                    
                    # Log what retire.js returned for debugging
                    if result.stderr:
                        logger.debug(f"retire.js stderr for {script_url}: {result.stderr[:200]}")
                    
                    # Log stdout for debugging (first 500 chars)
                    if result.stdout:
                        logger.info(f"retire.js stdout for {script_url} (first 500 chars): {result.stdout[:500]}")
                    
                    if output:
                        try:
                            data = json.loads(output)
                            logger.info(f"retire.js returned data for {script_url}: type={type(data).__name__}, keys={list(data.keys()) if isinstance(data, dict) else 'list'}")
                            
                            # retire.js JSON format: {"data": [{"file": "...", "results": [{"component": "...", "version": "...", "vulnerabilities": [...]}]}]}
                            # OR old format: [{"component": "...", "version": "...", "vulnerabilities": [...]}]
                            
                            results = []
                            
                            if isinstance(data, dict) and "data" in data:
                                # New JSON format: extract from data array
                                for file_entry in data.get("data", []):
                                    for result in file_entry.get("results", []):
                                        results.append(result)
                            elif isinstance(data, list):
                                # Old format: direct list of results
                                results = data
                            elif isinstance(data, dict) and data.get("component"):
                                # Single result as dict
                                results = [data]
                            
                            logger.info(f"retire.js extracted {len(results)} result(s) from {script_url}")
                            
                            # Process all results
                            for result in results:
                                component = result.get("component", "")
                                version = result.get("version", "")
                                vulnerabilities = result.get("vulnerabilities", [])
                                
                                logger.info(f"retire.js processing: component={component}, version={version}, vulnerabilities={len(vulnerabilities)}")
                                
                                if component:
                                    # Check if we already added this dependency
                                    existing = next((d for d in client_deps if d["name"] == component and d.get("evidence") == script_url), None)
                                    if not existing:
                                        client_deps.append({
                                            "name": component,
                                            "version": version,
                                            "evidence": script_url,
                                            "confidence": 0.9,
                                        })
                                    
                                    # Create finding for each vulnerability
                                    for vuln in vulnerabilities:
                                        # Extract CVE IDs from identifiers
                                        cve_ids = []
                                        identifiers = vuln.get("identifiers", {})
                                        if isinstance(identifiers, dict):
                                            cve_list = identifiers.get("CVE", [])
                                            if isinstance(cve_list, list):
                                                cve_ids = cve_list
                                            elif isinstance(cve_list, str):
                                                cve_ids = [cve_list]
                                        
                                        findings.append({
                                            "type": "client_dependency_vuln",
                                            "package": component,
                                            "version": version,
                                            "severity": vuln.get("severity", "medium").lower(),
                                            "evidence": script_url,
                                            "references": cve_ids,
                                            "confidence": 0.9,
                                        })
                                    
                                    logger.info(f"retire.js found {len(vulnerabilities)} vulnerabilities in {component} {version} from {script_url}")
                        except json.JSONDecodeError as e:
                            # retire.js might output non-JSON warnings/errors
                            logger.warning(f"retire.js returned non-JSON output for {script_url}: {output[:500]}")
                            logger.warning(f"JSON decode error: {e}")
                            # Check if output contains vulnerability info in text format
                            if "vulnerabilities" in output.lower() or "vulnerable" in output.lower():
                                logger.info(f"retire.js found potential issues in {script_url} (non-JSON format)")
                    else:
                        # No output means no vulnerabilities found, but the file was scanned successfully
                        logger.info(f"retire.js scanned {script_url} successfully but found no vulnerabilities (exit_code={result.returncode}, stdout_len={len(result.stdout) if result.stdout else 0}, stderr_len={len(result.stderr) if result.stderr else 0})")
                except Exception as e:
                    logger.warning(f"retire.js failed for {temp_file} (from {script_url}): {e}")
                    continue
            
            logger.info(f"retire.js scan completed: found {len(client_deps)} dependencies and {len(findings)} vulnerabilities")
        finally:
            # Cleanup temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
    except FileNotFoundError:
        raise  # Re-raise if tool not found
    except Exception as e:
        logger.warning(f"retire.js scan failed: {e}")
    
    logger.info(f"retire.js found {len(client_deps)} client dependencies and {len(findings)} vulnerabilities")
    return client_deps, findings


def calculate_confidence(fingerprint: Dict, technologies: List, client_deps: List) -> float:
    """Calculate overall confidence score."""
    confidence = 0.0
    
    if fingerprint.get("status", 0) == 200:
        confidence += 0.2
    
    if fingerprint.get("title"):
        confidence += 0.1
    
    if technologies:
        confidence += min(0.3, len(technologies) * 0.1)
    
    if client_deps:
        confidence += min(0.4, len(client_deps) * 0.2)
    
    return min(1.0, confidence)


async def get_github_installation_token(backend_url: str, installation_id: str) -> str:
    """Get GitHub installation token from backend."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{backend_url}/api/integrations/github/installation-token",
            params={"installation_id": installation_id},
        )
        response.raise_for_status()
        data = response.json()
        return data["token"]


async def download_repo_zip(
    full_name: str,
    branch: str,
    token: str,
    output_dir: Path,
) -> Path:
    """Download repository ZIP archive."""
    url = f"https://api.github.com/repos/{full_name}/zipball/{branch}"
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.get(
            url,
            headers={"Authorization": f"token {token}"},
        )
        response.raise_for_status()
        
        zip_path = output_dir / "repo.zip"
        zip_path.write_bytes(response.content)
        
        # Check size limit (200MB)
        if zip_path.stat().st_size > 200 * 1024 * 1024:
            raise ValueError("Repository ZIP exceeds 200MB limit")
        
        return zip_path


async def extract_zip(zip_path: Path, extract_dir: Path) -> None:
    """Extract ZIP archive."""
    import zipfile
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Check extracted size limit (600MB)
        total_size = sum(info.file_size for info in zip_ref.infolist())
        if total_size > 600 * 1024 * 1024:
            raise ValueError("Extracted repository exceeds 600MB limit")
        
        # Check file count limit (200k)
        if len(zip_ref.namelist()) > 200000:
            raise ValueError("Repository exceeds 200k file limit")
        
        zip_ref.extractall(extract_dir)


async def run_osv_scanner(scan_dir: Path) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Run osv-scanner on extracted repository."""
    packages = []
    findings = []
    
    try:
        result = subprocess.run(
            ["osv-scanner", "--format", "json", "--lockfile=auto", str(scan_dir)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        if result.returncode == 0 and result.stdout:
            data = json.loads(result.stdout)
            
            # Extract packages and findings
            for result_item in data.get("results", []):
                source = result_item.get("source", {})
                for package in result_item.get("packages", []):
                    pkg_info = {
                        "ecosystem": package.get("package", {}).get("ecosystem", ""),
                        "name": package.get("package", {}).get("name", ""),
                        "version": package.get("package", {}).get("version", ""),
                        "paths": [source.get("path", "")],
                    }
                    packages.append(pkg_info)
                    
                    # Extract vulnerabilities
                    for vuln in package.get("vulnerabilities", []):
                        findings.append({
                            "type": "dependency_vuln",
                            "ecosystem": pkg_info["ecosystem"],
                            "package": pkg_info["name"],
                            "version": pkg_info["version"],
                            "vuln_id": vuln.get("id", ""),
                            "severity": map_severity(vuln),
                            "fixed": vuln.get("database_specific", {}).get("fixed_version"),
                            "paths": [source.get("path", "")],
                            "references": [ref.get("url", "") for ref in vuln.get("references", [])],
                        })
    except FileNotFoundError:
        logger.warning("osv-scanner not found, skipping repository scan")
    except Exception as e:
        logger.error(f"osv-scanner failed: {e}", exc_info=True)
    
    return packages, findings


def map_severity(vuln: Dict) -> str:
    """Map OSV severity to our severity levels."""
    severity = vuln.get("database_specific", {}).get("severity", "")
    if not severity:
        # Try CVSS score
        cvss = vuln.get("severity", [{}])[0].get("score", "")
        if cvss:
            score = float(cvss)
            if score >= 9.0:
                return "critical"
            elif score >= 7.0:
                return "high"
            elif score >= 4.0:
                return "medium"
            else:
                return "low"
        return "unknown"
    
    severity_lower = severity.lower()
    if "critical" in severity_lower:
        return "critical"
    elif "high" in severity_lower:
        return "high"
    elif "medium" in severity_lower:
        return "medium"
    elif "low" in severity_lower:
        return "low"
    else:
        return "unknown"


async def send_progress(
    backend_url: str,
    scan_id: str,
    step: str,
    status: str,
    message: str,
) -> None:
    """Send progress update to backend."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{backend_url}/api/runner/progress",
                json={
                    "scan_id": scan_id,
                    "step": step,
                    "status": status,
                    "message": message,
                },
            )
    except Exception as e:
        logger.debug(f"Failed to send progress update: {e}")


async def create_dependency_tool_result(
    backend_url: str,
    scan_id: str,
    tool_name: str,
    tool_id: str,
    success: bool,
    execution_time: float,
    findings_count: int = 0,
    error_message: Optional[str] = None,
    meta_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Create a ToolResult entry for dependency scanning tools (wappalyzer, retire.js).
    
    This makes them appear in the "Tools Executed" section like regular security tools.
    """
    try:
        from app.config import settings
        
        # Generate unique tool_run_id for idempotency
        tool_run_id = str(uuid.uuid4())
        
        # Build meta dict with dependency scan flag and any additional data
        meta_dict = {
            "dependency_scan_tool": True,
            "findings_count": findings_count,  # Store actual count in meta
        }
        if meta_data:
            meta_dict.update(meta_data)
        
        logger.warning(f"[DEPENDENCY-TOOL-DEBUG] Creating {tool_name} tool result: meta_dict={meta_dict}")
        
        # Build execution result payload
        execution_result = {
            "success": success,
            "exit_code": 0 if success else 1,
            "execution_time": execution_time,
            "error": error_message,
            "error_message": error_message,
            "timed_out": False,
            "meta": meta_dict,
        }
        
        logger.warning(f"[DEPENDENCY-TOOL-DEBUG] execution_result.meta={execution_result.get('meta')}")
        
        # Use the same post_tool_result function that regular tools use
        from app.backend_client import post_tool_result
        
        # Create dummy findings to set findings_count correctly
        # The actual data is in artifacts, but we want the count to show in UI
        dummy_findings = [{"type": "dependency_scan_result"}] * findings_count if findings_count > 0 else []
        
        await post_tool_result(
            scan_job_id=scan_id,
            step_id=f"dependency-{tool_name}-{tool_run_id[:8]}",  # Unique step ID
            tool_name=tool_name,
            tool_id=tool_id,
            findings=dummy_findings,  # Use dummy findings to set count, actual data in artifacts
            execution_result=execution_result,
            tool_run_id=tool_run_id,
        )
        
        logger.info(
            f"Created ToolResult entry for {tool_name} (scan_id={scan_id}, "
            f"findings={findings_count}, success={success})"
        )
    except Exception as e:
        logger.warning(f"Failed to create ToolResult entry for {tool_name}: {e}")
        # Don't fail the whole job if tool result creation fails


async def post_callback(
    callback_url: str,
    scan_id: str,
    artifact_type: str,
    payload: Dict[str, Any],
    secret: Optional[str] = None,
) -> None:
    """Post scan artifact to backend callback."""
    import hmac
    import hashlib
    from app.config import settings
    
    body = json.dumps({
        "scan_id": scan_id,
        "artifact_type": artifact_type,
        "payload": payload,
    }).encode('utf-8')
    
    headers = {}
    # Add Bearer token authentication (required by callback endpoint)
    if settings.RUNNER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.RUNNER_API_TOKEN}"
    
    # Also include signature if secret provided (for additional verification)
    if secret:
        signature = hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        headers["X-Runner-Signature"] = signature
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                callback_url,
                content=body,
                headers=headers,
            )
            response.raise_for_status()
            logger.info(f"Posted scan artifact {artifact_type} to backend callback (status code {response.status_code})")
    except Exception as e:
        logger.error(f"Failed to post callback for {artifact_type} (scan {scan_id}): {e}", exc_info=True)
        raise  # Re-raise to let caller handle it
