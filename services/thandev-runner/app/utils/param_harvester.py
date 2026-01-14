"""
Parameter harvester for collecting parameterized endpoints from various sources.
Used to feed dalfox, sqlmap, and other injection-testing tools with proper targets.
"""
import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParameterizedRequest:
    """Represents a request with parameters suitable for injection testing"""
    url: str
    method: str = "GET"
    params: Dict[str, str] = None  # Query params or POST data
    headers: Dict[str, str] = None
    cookies: Dict[str, str] = None
    content_type: str = None
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.headers is None:
            self.headers = {}
        if self.cookies is None:
            self.cookies = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        return {
            "url": self.url,
            "method": self.method,
            "params": self.params,
            "headers": self.headers,
            "cookies": self.cookies,
            "content_type": self.content_type,
        }
    
    def get_full_url(self) -> str:
        """Get full URL with query params included (for GET requests)"""
        if self.method.upper() == "GET" and self.params:
            parsed = urlparse(self.url)
            query_string = urlencode(self.params)
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                query_string,
                ""  # No fragment
            ))
        return self.url
    
    def get_param_names(self) -> List[str]:
        """Get list of parameter names"""
        return list(self.params.keys())


class ParamHarvester:
    """
    Harvests parameterized endpoints from various sources:
    - ZAP Ajax Spider results
    - ZAP passive/active scan results
    - Custom crawler output
    - Manual URL lists
    """
    
    def __init__(self, job_dir: Optional[Path] = None):
        """
        Initialize param harvester.
        
        Args:
            job_dir: Job directory where tool outputs are stored
        """
        self.job_dir = job_dir
        self.harvested_requests: List[ParameterizedRequest] = []
        self.seen_urls: Set[str] = set()
    
    def harvest_from_zap_output(self, zap_output_file: Path) -> int:
        """
        Harvest parameterized requests from ZAP output file.
        
        ZAP output contains findings with URL information, including parameters.
        We extract URLs and their parameters from the findings.
        
        Args:
            zap_output_file: Path to ZAP JSON output file
            
        Returns:
            Number of new parameterized requests harvested
        """
        if not zap_output_file or not zap_output_file.exists():
            logger.debug(f"ZAP output file not found: {zap_output_file}")
            return 0
        
        try:
            content = zap_output_file.read_text(encoding="utf-8")
            if not content or not content.strip():
                logger.debug(f"ZAP output file is empty: {zap_output_file}")
                return 0
            
            # Parse ZAP output (JSON array of findings)
            zap_findings = json.loads(content)
            if not isinstance(zap_findings, list):
                logger.warning(f"ZAP output is not a list: {type(zap_findings)}")
                return 0
            
            initial_count = len(self.harvested_requests)
            
            for finding in zap_findings:
                if not isinstance(finding, dict):
                    continue
                
                # Extract URL and method from finding
                url = finding.get("url") or finding.get("uri")
                method = finding.get("method") or finding.get("http_method") or "GET"
                
                if not url:
                    continue
                
                # Parse URL to extract query params
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                
                # Flatten query params (parse_qs returns lists)
                params = {k: v[0] if isinstance(v, list) and v else str(v) 
                         for k, v in query_params.items()}
                
                # Extract POST data if present (ZAP may include this)
                post_data = finding.get("data") or finding.get("postData")
                if post_data and method.upper() == "POST":
                    # Try to parse as JSON or form data
                    try:
                        post_params = json.loads(post_data)
                        if isinstance(post_params, dict):
                            params.update(post_params)
                    except json.JSONDecodeError:
                        # Try to parse as form data
                        try:
                            post_params = parse_qs(post_data)
                            params.update({k: v[0] if isinstance(v, list) and v else str(v) 
                                         for k, v in post_params.items()})
                        except Exception:
                            pass
                
                # Only add if we have parameters
                if params:
                    # Create base URL without query string for deduplication
                    base_url = urlunparse((
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        "",  # No query
                        ""   # No fragment
                    ))
                    
                    dedup_key = f"{method.upper()}:{base_url}:{':'.join(sorted(params.keys()))}"
                    if dedup_key not in self.seen_urls:
                        self.seen_urls.add(dedup_key)
                        self.harvested_requests.append(ParameterizedRequest(
                            url=base_url,
                            method=method.upper(),
                            params=params,
                        ))
            
            harvested_count = len(self.harvested_requests) - initial_count
            logger.info(f"Harvested {harvested_count} parameterized requests from ZAP output")
            return harvested_count
            
        except Exception as e:
            logger.error(f"Failed to harvest from ZAP output: {e}", exc_info=True)
            return 0
    
    def harvest_from_crawler_output(self, crawler_urls: List[str]) -> int:
        """
        Harvest parameterized requests from crawler URL list.
        
        Args:
            crawler_urls: List of URLs discovered by crawler
            
        Returns:
            Number of new parameterized requests harvested
        """
        if not crawler_urls:
            return 0
        
        initial_count = len(self.harvested_requests)
        
        for url in crawler_urls:
            if not url:
                continue
            
            try:
                parsed = urlparse(url)
                query_params = parse_qs(parsed.query)
                
                if not query_params:
                    continue
                
                # Flatten query params
                params = {k: v[0] if isinstance(v, list) and v else str(v) 
                         for k, v in query_params.items()}
                
                # Create base URL without query string for deduplication
                base_url = urlunparse((
                    parsed.scheme,
                    parsed.netloc,
                    parsed.path,
                    parsed.params,
                    "",  # No query
                    ""   # No fragment
                ))
                
                dedup_key = f"GET:{base_url}:{':'.join(sorted(params.keys()))}"
                if dedup_key not in self.seen_urls:
                    self.seen_urls.add(dedup_key)
                    self.harvested_requests.append(ParameterizedRequest(
                        url=base_url,
                        method="GET",
                        params=params,
                    ))
            except Exception as e:
                logger.debug(f"Failed to parse URL {url}: {e}")
                continue
        
        harvested_count = len(self.harvested_requests) - initial_count
        logger.info(f"Harvested {harvested_count} parameterized requests from crawler URLs")
        return harvested_count
    
    def harvest_from_job_dir(self) -> int:
        """
        Harvest parameterized requests from all available sources in job_dir.
        
        Looks for:
        - zap_output.json
        - crawler_output.json (if exists)
        
        Returns:
            Total number of parameterized requests harvested
        """
        if not self.job_dir or not self.job_dir.exists():
            logger.debug(f"Job directory not found: {self.job_dir}")
            return 0
        
        total_harvested = 0
        
        # Try to harvest from ZAP output
        zap_output = self.job_dir / "zap_output.json"
        if zap_output.exists():
            total_harvested += self.harvest_from_zap_output(zap_output)
        
        # Try to harvest from crawler output (if saved)
        crawler_output = self.job_dir / "crawler_output.json"
        if crawler_output.exists():
            try:
                content = crawler_output.read_text(encoding="utf-8")
                crawler_data = json.loads(content)
                if isinstance(crawler_data, dict):
                    parameterized_urls = crawler_data.get("parameterized_urls", [])
                    total_harvested += self.harvest_from_crawler_output(parameterized_urls)
            except Exception as e:
                logger.debug(f"Failed to load crawler output: {e}")
        
        return total_harvested
    
    def add_manual_url(self, url: str, method: str = "GET") -> bool:
        """
        Manually add a parameterized URL.
        
        Args:
            url: URL with query parameters
            method: HTTP method (GET/POST)
            
        Returns:
            True if added, False if already exists or invalid
        """
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            
            if not query_params:
                logger.debug(f"URL has no parameters: {url}")
                return False
            
            # Flatten query params
            params = {k: v[0] if isinstance(v, list) and v else str(v) 
                     for k, v in query_params.items()}
            
            # Create base URL without query string for deduplication
            base_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                "",  # No query
                ""   # No fragment
            ))
            
            dedup_key = f"{method.upper()}:{base_url}:{':'.join(sorted(params.keys()))}"
            if dedup_key in self.seen_urls:
                return False
            
            self.seen_urls.add(dedup_key)
            self.harvested_requests.append(ParameterizedRequest(
                url=base_url,
                method=method.upper(),
                params=params,
            ))
            return True
        except Exception as e:
            logger.error(f"Failed to add manual URL {url}: {e}")
            return False
    
    def get_all_requests(self) -> List[ParameterizedRequest]:
        """Get all harvested parameterized requests"""
        return self.harvested_requests
    
    def get_parameterized_urls(self) -> List[str]:
        """
        Get list of full URLs with parameters (for tools like dalfox).
        
        Returns:
            List of URLs with query params included
        """
        return [req.get_full_url() for req in self.harvested_requests]
    
    def get_requests_for_sqlmap(self) -> List[Dict[str, Any]]:
        """
        Get requests formatted for sqlmap.
        
        Returns:
            List of request dicts with url, method, params, etc.
        """
        return [req.to_dict() for req in self.harvested_requests]
    
    def get_stats(self) -> Dict[str, int]:
        """Get harvesting statistics"""
        get_count = sum(1 for req in self.harvested_requests if req.method == "GET")
        post_count = sum(1 for req in self.harvested_requests if req.method == "POST")
        total_params = sum(len(req.params) for req in self.harvested_requests)
        
        return {
            "total_requests": len(self.harvested_requests),
            "get_requests": get_count,
            "post_requests": post_count,
            "total_parameters": total_params,
            "unique_urls": len(self.seen_urls),
        }
    
    def save_to_file(self, output_path: Path) -> bool:
        """
        Save harvested requests to JSON file.
        
        Args:
            output_path: Path to output file
            
        Returns:
            True if successful
        """
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "stats": self.get_stats(),
                "requests": [req.to_dict() for req in self.harvested_requests],
            }
            output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.info(f"Saved harvested requests to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save harvested requests: {e}")
            return False


def create_fallback_targets(base_url: str) -> List[str]:
    """
    Create fallback parameterized URLs for common parameter names.
    Used when no params are harvested from crawlers/ZAP.
    
    Args:
        base_url: Base target URL
        
    Returns:
        List of URLs with common test parameters
    """
    parsed = urlparse(base_url)
    base_path = parsed.path.rstrip("/") + "/"
    base = urlunparse((parsed.scheme, parsed.netloc, base_path, "", "", ""))
    
    # Common parameter names to test
    common_params = [
        "id",
        "page",
        "query", "q", "search",
        "user", "username",
        "email",
        "name",
        "category", "cat",
        "item",
        "product",
        "action",
        "callback",
        "url",
        "redirect",
        "next",
        "file",
        "path",
        "data",
    ]
    
    fallback_urls = []
    for param in common_params:
        url = f"{base}?{param}=test"
        fallback_urls.append(url)
    
    # Also try root with a parameter
    root = urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))
    fallback_urls.append(f"{root}?id=1")
    
    return fallback_urls
