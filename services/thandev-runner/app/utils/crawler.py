import logging
import re
import asyncio
import httpx
from urllib.parse import urljoin, urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from typing import Set, List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class SmartCrawler:
    """
    Intelligent crawler to discover endpoints, forms, and parameters for security scanning.
    """
    
    def __init__(self, start_url: str, depth: int = 3, limit: int = 50, timeout: int = 10):
        self.start_url = start_url
        self.base_domain = urlparse(start_url).netloc
        self.depth = depth
        self.limit = limit
        self.timeout = timeout
        
        self.visited: Set[str] = set()
        self.urls_to_visit: List[Tuple[str, int]] = [(start_url, 0)]
        self.discovered_urls: Set[str] = set()
        self.parameterized_urls: Set[str] = set()
        
        # Regex to find potential URLs in text/scripts (aggressive)
        # Matches any string in quotes starting with http, https, or /
        self.url_pattern = re.compile(r'["\']((?:https?://|/)[^"\']+)["\']')

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and within scope."""
        try:
            parsed = urlparse(url)
            # Must be http/https
            if parsed.scheme not in ('http', 'https'):
                return False
            
            # Must be in same domain (or subdomain)
            if parsed.netloc != self.base_domain:
                return False
                
            # Skip static files (images, css, fonts, etc.)
            skip_exts = {
                '.css', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', 
                '.woff', '.woff2', '.ttf', '.eot', '.pdf', '.zip', '.tar', '.gz'
            }
            if any(parsed.path.lower().endswith(ext) for ext in skip_exts):
                return False
                
            return True
        except Exception:
            return False

    def _extract_links_and_forms(self, html: str, current_url: str):
        """Extract links and forms from HTML."""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # 1. Extract standard links (a, link, script, img)
            for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe']):
                attr = 'href' if tag.name in ['a', 'link'] else 'src'
                val = tag.get(attr)
                if val:
                    full_url = urljoin(current_url, val)
                    # Remove fragment
                    full_url = full_url.split('#')[0]
                    if self._is_valid_url(full_url):
                        self.discovered_urls.add(full_url)
                        if full_url not in self.visited:
                             # Add to visit queue if depth allows (handled in run loop)
                             pass

            # 2. Extract forms
            for form in soup.find_all('form'):
                action = form.get('action')
                method = form.get('method', 'get').lower()
                
                if not action:
                    action_url = current_url
                else:
                    action_url = urljoin(current_url, action)
                
                # If GET form, construct query string URL
                if method == 'get':
                    inputs = form.find_all(['input', 'textarea', 'select'])
                    params = {}
                    for inp in inputs:
                        name = inp.get('name')
                        if name:
                            # Use a default test value
                            params[name] = 'test'
                    
                    if params:
                        query_string = urlencode(params)
                        if '?' in action_url:
                             full_form_url = f"{action_url}&{query_string}"
                        else:
                             full_form_url = f"{action_url}?{query_string}"
                        
                        if self._is_valid_url(full_form_url):
                            self.discovered_urls.add(full_form_url)
                            self.parameterized_urls.add(full_form_url)

        except Exception as e:
            logger.debug(f"Error parsing HTML from {current_url}: {e}")

    async def crawl(self) -> Tuple[List[str], List[str]]:
        """
        Execute the crawl.
        Returns: (all_urls, parameterized_urls)
        """
        logger.info(f"Starting crawl of {self.start_url} (depth={self.depth}, limit={self.limit})")
        
        async with httpx.AsyncClient(verify=False, timeout=self.timeout, follow_redirects=True) as client:
            while self.urls_to_visit and len(self.visited) < self.limit:
                current_url, current_depth = self.urls_to_visit.pop(0)
                
                if current_url in self.visited:
                    continue
                
                self.visited.add(current_url)
                self.discovered_urls.add(current_url)
                
                # Check parameters
                if '?' in current_url:
                    self.parameterized_urls.add(current_url)
                
                if current_depth >= self.depth:
                    continue
                
                try:
                    logger.debug(f"Crawling: {current_url}")
                    response = await client.get(current_url)
                    
                    # Only parse HTML or JS
                    content_type = response.headers.get('content-type', '').lower()
                    if 'text/html' in content_type or 'javascript' in content_type:
                        # Extract and process new links
                        initial_count = len(self.discovered_urls)
                        
                        # 1. Regex-based discovery (finds URLs in JS, attributes, etc.)
                        # This catches things like location.href="...", var url = "...", etc.
                        matches = self.url_pattern.findall(response.text)
                        new_urls = []
                        for match in matches:
                             full_url = urljoin(current_url, match).split('#')[0]
                             if self._is_valid_url(full_url) and full_url not in self.visited:
                                 new_urls.append(full_url)
                        
                        # 2. BeautifulSoup parsing (for structured elements)
                        try:
                            soup = BeautifulSoup(response.text, 'lxml')
                            
                            # Expand tag search: a, link, script, img, iframe, area, base, form
                            for tag in soup.find_all(['a', 'link', 'script', 'img', 'iframe', 'area', 'base']):
                                for attr in ['href', 'src', 'action', 'data', 'content']:
                                    val = tag.get(attr)
                                    if val:
                                        full_url = urljoin(current_url, val).split('#')[0]
                                        if self._is_valid_url(full_url) and full_url not in self.visited:
                                            new_urls.append(full_url)
                            
                            # Forms (Handle GET forms -> parameterized URLs)
                            for form in soup.find_all('form'):
                                action = form.get('action') or ''
                                method = form.get('method', 'get').lower()
                                if method == 'get':
                                    action_url = urljoin(current_url, action).split('#')[0]
                                    inputs = form.find_all(['input', 'textarea', 'select'])
                                    params = {i.get('name'): 'test' for i in inputs if i.get('name')}
                                    if params:
                                        # Enforce limit on discovered URLs
                                        if len(self.discovered_urls) >= self.limit:
                                            break
                                        qs = urlencode(params)
                                        full_form_url = f"{action_url}?{qs}" if '?' not in action_url else f"{action_url}&{qs}"
                                        if self._is_valid_url(full_form_url):
                                            self.discovered_urls.add(full_form_url)
                                            self.parameterized_urls.add(full_form_url)
                        except Exception as parse_err:
                            logger.debug(f"BeautifulSoup parsing error for {current_url}: {parse_err}")

                        # Add new unique URLs to queue (but respect the limit)
                        for url in new_urls:
                            # Enforce limit on discovered URLs, not just visited
                            if len(self.discovered_urls) >= self.limit:
                                break
                            if url not in self.visited and url not in [u[0] for u in self.urls_to_visit]:
                                self.discovered_urls.add(url) # Add to discovered set immediately
                                self.urls_to_visit.append((url, current_depth + 1))
                        
                except Exception as e:
                    logger.debug(f"Failed to crawl {current_url}: {e}")

        # Ensure we don't return more URLs than the limit
        all_urls = list(self.discovered_urls)[:self.limit]
        parameterized_urls = [url for url in list(self.parameterized_urls) if url in all_urls]
        
        logger.info(f"Crawl finished. Visited: {len(self.visited)}, Discovered: {len(all_urls)} (limit: {self.limit}), Parameterized: {len(parameterized_urls)}")
        return all_urls, parameterized_urls
