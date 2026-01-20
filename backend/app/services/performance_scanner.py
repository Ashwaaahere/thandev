"""
Performance scanner service
Handles execution of Lighthouse performance scans
"""
import logging
import subprocess
import tempfile
import json
import os
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def process_lighthouse_results(lighthouse_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process Lighthouse results into our PerformanceScan metrics format.
    
    Returns a dict with:
    - overall_score: Performance score (0-100)
    - first_contentful_paint_ms: FCP in milliseconds
    - largest_contentful_paint_ms: LCP in milliseconds
    - time_to_interactive_ms: TTI in milliseconds
    - total_requests: Number of network requests
    - total_kb: Total page size in KB
    - cumulative_layout_shift: CLS score
    - first_input_delay_ms: FID in milliseconds
    - speed_index: Speed Index in milliseconds
    """
    try:
        # Extract performance score
        categories = lighthouse_data.get("categories", {})
        performance_category = categories.get("performance", {})
        overall_score = int(performance_category.get("score", 0) * 100) if performance_category.get("score") else 0
        
        # Extract metrics from audits
        audits = lighthouse_data.get("audits", {})
        
        # Core Web Vitals and other metrics
        first_contentful_paint_ms = audits.get("first-contentful-paint", {}).get("numericValue", 0)
        largest_contentful_paint_ms = audits.get("largest-contentful-paint", {}).get("numericValue", 0)
        time_to_interactive_ms = audits.get("interactive", {}).get("numericValue", 0)
        cumulative_layout_shift = audits.get("cumulative-layout-shift", {}).get("numericValue", 0)
        first_input_delay_ms = audits.get("max-potential-fid", {}).get("numericValue", 0)
        speed_index = audits.get("speed-index", {}).get("numericValue", 0)
        
        # Network metrics
        total_requests = 0
        total_kb = 0
        
        # Try to get network requests from network-requests audit
        network_requests_audit = audits.get("network-requests", {})
        if network_requests_audit:
            details = network_requests_audit.get("details", {})
            items = details.get("items", [])
            total_requests = len(items)
            # Sum up transfer sizes
            for item in items:
                transfer_size = item.get("transferSize", 0)
                total_kb += transfer_size / 1024  # Convert bytes to KB
        
        # Fallback: try to get from networkRecords
        if total_requests == 0:
            network_records = lighthouse_data.get("networkRecords", [])
            if network_records:
                total_requests = len(network_records)
                for record in network_records:
                    transfer_size = record.get("transferSize", 0)
                    total_kb += transfer_size / 1024
        
        # If still no data, try to estimate from resource summary
        if total_kb == 0:
            resource_summary = lighthouse_data.get("audits", {}).get("network-requests", {}).get("details", {})
            if resource_summary:
                # Try to extract from resource summary
                pass
        
        return {
            "overall_score": overall_score,
            "first_contentful_paint_ms": round(first_contentful_paint_ms, 2),
            "largest_contentful_paint_ms": round(largest_contentful_paint_ms, 2),
            "time_to_interactive_ms": round(time_to_interactive_ms, 2),
            "total_requests": total_requests,
            "total_kb": round(total_kb, 2),
            "cumulative_layout_shift": round(cumulative_layout_shift, 3),
            "first_input_delay_ms": round(first_input_delay_ms, 2),
            "speed_index": round(speed_index, 2),
        }
    except Exception as e:
        logger.error(f"Error processing Lighthouse results: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return default values on error
        return {
            "overall_score": 0,
            "first_contentful_paint_ms": 0,
            "largest_contentful_paint_ms": 0,
            "time_to_interactive_ms": 0,
            "total_requests": 0,
            "total_kb": 0,
            "cumulative_layout_shift": 0,
            "first_input_delay_ms": 0,
            "speed_index": 0,
        }


async def run_lighthouse_scan(url: str, device: str = "desktop") -> Dict[str, Any]:
    """
    Run Lighthouse scan and return processed metrics.
    
    Args:
        url: Target URL to scan
        device: Device type ("desktop" or "mobile")
        
    Returns:
        Dict with processed metrics (see process_lighthouse_results)
        
    Raises:
        Exception: If Lighthouse scan fails
    """
    logger.info(f"Starting Lighthouse scan for {url} (device: {device})")
    try:
        return await run_local_lighthouse_scan(url, device)
    except Exception as e:
        logger.error(f"Lighthouse scan failed: {e}")
        raise


async def run_local_lighthouse_scan(url: str, device: str = "desktop") -> Dict[str, Any]:
    """Run Lighthouse scan locally using subprocess"""
    
    try:
        # Create temporary directory for Lighthouse output
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "report.json")
            
            # Get Chrome path from environment or use default
            chrome_path = os.getenv("CHROME_PATH", "/usr/bin/google-chrome-stable")
            
            # Build Lighthouse command
            cmd = [
                "lighthouse",
                url,
                "--output=json",
                f"--output-path={output_path}",
                "--chrome-flags=--headless --no-sandbox --disable-gpu",
                "--only-categories=performance",
                "--quiet"
            ]
            
            # Add device-specific flags
            if device == "mobile":
                cmd.extend([
                    "--chrome-flags=--headless --window-size=375,667",
                    "--preset=desktop"  # Use mobile preset
                ])
            else:
                cmd.extend([
                    "--chrome-flags=--headless --window-size=1280,720",
                    "--preset=desktop"
                ])
            
            # Set environment
            env = os.environ.copy()
            env["CHROME_PATH"] = chrome_path
            
            # Run Lighthouse (with timeout)
            logger.info(f"Running Lighthouse command: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            except asyncio.TimeoutError:
                process.kill()
                raise Exception("Lighthouse scan timed out after 5 minutes")
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise Exception(f"Lighthouse failed: {error_msg}")
            
            # Read results
            if not os.path.exists(output_path):
                raise Exception("Lighthouse did not generate output file")
            
            with open(output_path, "r") as f:
                lighthouse_data = json.load(f)
            
            # Process results
            return process_lighthouse_results(lighthouse_data)
            
    except Exception as e:
        logger.error(f"Local Lighthouse scan failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
