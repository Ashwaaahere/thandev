"""
Request Recorder Utility
Builds raw HTTP requests for SQLMap to test POST forms (especially login forms)
"""
import logging
import re
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin, parse_qs
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def build_raw_request_for_login(
    login_url: str,
    username_placeholder: str = "test",
    password_placeholder: str = "test",
    timeout: int = 10,
) -> Tuple[str, Optional[str]]:
    """
    Build a raw HTTP request file for SQLMap to test login forms.
    
    This function:
    1. Fetches the login page (GET)
    2. Parses the HTML form to extract form fields
    3. Captures cookies from the GET response
    4. Builds a POST request with all form fields
    5. Returns the raw request string and cookie string
    
    Args:
        login_url: URL of the login page (e.g., "http://testphp.vulnweb.com/login.php")
        username_placeholder: Placeholder value for username field (SQLMap will inject here)
        password_placeholder: Placeholder value for password field (SQLMap will inject here)
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (raw_request_string, cookie_string)
        raw_request_string: Raw HTTP request that can be saved to a file for sqlmap -r
        cookie_string: Cookie string for sqlmap --cookie (if cookies were captured)
        
    Example raw request format:
        POST /login.php HTTP/1.1
        Host: testphp.vulnweb.com
        User-Agent: Mozilla/5.0...
        Content-Type: application/x-www-form-urlencoded
        Content-Length: 25
        
        uname=test&pass=test
    """
    try:
        # Step 1: Fetch the login page
        logger.info(f"Fetching login page: {login_url}")
        response = requests.get(login_url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Step 2: Capture cookies
        cookies = response.cookies
        cookie_string = None
        if cookies:
            cookie_parts = [f"{name}={value}" for name, value in cookies.items()]
            cookie_string = "; ".join(cookie_parts)
            logger.info(f"Captured {len(cookies)} cookies")
        
        # Step 3: Parse HTML to find the login form
        soup = BeautifulSoup(response.text, 'html.parser')
        form = soup.find('form')
        
        if not form:
            logger.warning(f"No form found on {login_url}, falling back to basic POST")
            # Fallback: build a basic POST request assuming common field names
            return _build_basic_post_request(login_url, cookie_string)
        
        # Step 4: Extract form attributes
        form_action = form.get('action', '')
        form_method = form.get('method', 'GET').upper()
        
        # Resolve form action URL (may be relative)
        if form_action:
            form_url = urljoin(login_url, form_action)
        else:
            form_url = login_url
        
        parsed_url = urlparse(form_url)
        path = parsed_url.path or '/'
        host = parsed_url.netloc
        
        # Step 5: Extract all input fields
        inputs = form.find_all(['input', 'textarea', 'select'])
        form_data = {}
        
        username_field = None
        password_field = None
        
        for input_elem in inputs:
            input_type = input_elem.get('type', 'text').lower()
            input_name = input_elem.get('name')
            
            if not input_name:
                continue
            
            # Identify username and password fields
            if input_type == 'password':
                password_field = input_name
                form_data[input_name] = password_placeholder
            elif input_type in ['text', 'email'] and any(keyword in input_name.lower() for keyword in ['user', 'name', 'email', 'login', 'account']):
                if not username_field:
                    username_field = input_name
                form_data[input_name] = username_placeholder
            elif input_type == 'hidden':
                # Include hidden fields (may contain CSRF tokens)
                form_data[input_name] = input_elem.get('value', '')
            elif input_type in ['text', 'email']:
                # Other text fields
                form_data[input_name] = username_placeholder
            elif input_type == 'submit':
                # Skip submit buttons
                continue
            elif input_type == 'checkbox' and input_elem.get('checked'):
                form_data[input_name] = 'on'
            elif input_type == 'radio' and input_elem.get('checked'):
                form_data[input_name] = input_elem.get('value', '')
        
        # If we didn't find username/password fields, use common names
        if not username_field:
            # Try common username field names
            for name in ['uname', 'username', 'user', 'email', 'login', 'account']:
                if name in form_data:
                    username_field = name
                    break
            if not username_field:
                # Use first text field
                for name, value in form_data.items():
                    if value == username_placeholder:
                        username_field = name
                        break
        
        if not password_field:
            # Try common password field names
            for name in ['pass', 'password', 'pwd', 'passwd']:
                if name in form_data:
                    password_field = name
                    break
        
        logger.info(f"Form fields detected: username={username_field}, password={password_field}, total_fields={len(form_data)}")
        
        # Step 6: Build POST data string
        post_data = "&".join([f"{k}={v}" for k, v in form_data.items()])
        
        # Step 7: Build raw HTTP request
        raw_request = _build_raw_http_request(
            method=form_method,
            path=path,
            host=host,
            post_data=post_data,
            cookie_string=cookie_string,
            referer=login_url,
        )
        
        logger.info(f"Built raw request for {form_url} with {len(form_data)} form fields")
        return raw_request, cookie_string
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch login page {login_url}: {e}")
        # Fallback to basic POST
        return _build_basic_post_request(login_url, None)
    except Exception as e:
        logger.error(f"Error building raw request for {login_url}: {e}", exc_info=True)
        # Fallback to basic POST
        return _build_basic_post_request(login_url, None)


def _build_basic_post_request(login_url: str, cookie_string: Optional[str]) -> Tuple[str, Optional[str]]:
    """
    Build a basic POST request when form parsing fails.
    
    Uses common field names: uname, username, user, email for username
    and pass, password, pwd for password.
    """
    parsed_url = urlparse(login_url)
    path = parsed_url.path or '/'
    host = parsed_url.netloc
    
    # Try common field name combinations
    post_data = "uname=test&pass=test"
    
    raw_request = _build_raw_http_request(
        method="POST",
        path=path,
        host=host,
        post_data=post_data,
        cookie_string=cookie_string,
        referer=login_url,
    )
    
    logger.info(f"Built basic POST request for {login_url} with fallback field names")
    return raw_request, cookie_string


def _build_raw_http_request(
    method: str,
    path: str,
    host: str,
    post_data: str,
    cookie_string: Optional[str] = None,
    referer: Optional[str] = None,
) -> str:
    """
    Build a raw HTTP request string.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        host: Host header value
        post_data: POST body data (for POST requests)
        cookie_string: Cookie header value (optional)
        referer: Referer header value (optional)
        
    Returns:
        Raw HTTP request string
    """
    lines = []
    
    # Request line
    lines.append(f"{method} {path} HTTP/1.1")
    
    # Headers
    lines.append(f"Host: {host}")
    lines.append("User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    if referer:
        lines.append(f"Referer: {referer}")
    
    if cookie_string:
        lines.append(f"Cookie: {cookie_string}")
    
    if method == "POST" and post_data:
        lines.append("Content-Type: application/x-www-form-urlencoded")
        lines.append(f"Content-Length: {len(post_data.encode('utf-8'))}")
        lines.append("")  # Empty line before body
        lines.append(post_data)
    else:
        lines.append("")  # Empty line after headers
    
    return "\r\n".join(lines)


def save_raw_request(raw_request: str, output_file: str) -> None:
    """
    Save raw HTTP request to a file.
    
    Args:
        raw_request: Raw HTTP request string
        output_file: Path to output file
    """
    from pathlib import Path
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(raw_request)
    
    logger.info(f"Saved raw request to {output_file}")

