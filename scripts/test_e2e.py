#!/usr/bin/env python3
"""
End-to-end Thandev system testing script
Tests all components and integration points
"""

import sys
import os
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Add backend to path
repo_root = Path(__file__).parent.parent
backend_path = repo_root / "backend"
sys.path.insert(0, str(backend_path))

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.issues = []

def print_header(text: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}\n")

def print_test(result: TestResult):
    if result.passed:
        print(f"{Colors.GREEN}✓{Colors.NC} {result.name}")
        if result.message:
            print(f"  {result.message}")
    else:
        print(f"{Colors.RED}✗{Colors.NC} {result.name}")
        if result.message:
            print(f"  {result.message}")
        if result.issues:
            for issue in result.issues:
                print(f"    - {issue}")

def test_database() -> TestResult:
    """Test database connection"""
    result = TestResult("Database Connection")
    try:
        from app.core.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result.passed = True
        result.message = "Database connection successful"
    except ImportError as e:
        result.message = f"Import error: {e}"
        result.issues.append("SQLAlchemy or database dependencies not installed")
        result.issues.append("Run: cd backend && pip install -r requirements.txt")
    except Exception as e:
        result.message = f"Connection failed: {e}"
        result.issues.append("Check DATABASE_URL in backend/.env")
        result.issues.append("Run: cd backend && alembic upgrade head")
    return result

def test_redis() -> TestResult:
    """Test Redis connection"""
    result = TestResult("Redis Connection")
    try:
        import redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        result.passed = True
        result.message = "Redis connection successful"
        
        # Check streams (may not exist yet)
        try:
            if r.exists("scan_step_requests") or r.exists("scan_step_results"):
                result.message += " (streams exist)"
        except:
            pass
    except ImportError:
        result.message = "redis-py not installed"
        result.issues.append("Run: pip install redis")
    except Exception as e:
        result.message = f"Connection failed: {e}"
        result.issues.append("Start Redis: redis-server")
        result.issues.append("Or check REDIS_URL in backend/.env")
    return result

def test_backend_service() -> TestResult:
    """Test backend service"""
    result = TestResult("Backend Service")
    try:
        import requests
        # Health endpoint is at /health, not /api/health
        resp = requests.get("http://localhost:8000/health", timeout=2)
        if resp.status_code == 200:
            result.passed = True
            data = resp.json()
            result.message = f"Backend service running on port 8000 (version: {data.get('version', 'unknown')})"
        else:
            result.message = f"Backend returned status {resp.status_code}"
    except requests.exceptions.ConnectionError:
        result.message = "Backend not running"
        result.issues.append("Start: cd backend && uvicorn app.main:app --reload")
    except ImportError:
        result.message = "requests library not installed"
        result.issues.append("Run: pip install requests")
    except Exception as e:
        result.message = f"Error: {e}"
    return result

def test_brain_service() -> TestResult:
    """Test brain service"""
    result = TestResult("Brain Service")
    try:
        import requests
        resp = requests.get("http://localhost:8001/v1/health", timeout=2)
        if resp.status_code == 200:
            result.passed = True
            result.message = "Brain service running on port 8001"
            
            # Test catalog
            try:
                catalog_resp = requests.get("http://localhost:8001/v1/catalog", timeout=2)
                if catalog_resp.status_code == 200:
                    result.message += " (catalog accessible)"
            except:
                pass
        else:
            result.message = f"Brain returned status {resp.status_code}"
    except requests.exceptions.ConnectionError:
        result.message = "Brain service not running"
        result.issues.append("Start: cd services/thandev-brain && uvicorn app.main:app --port 8001")
    except Exception as e:
        result.message = f"Error: {e}"
    return result

def test_tools() -> List[TestResult]:
    """Test tool availability"""
    results = []
    tools = [
        ("nuclei", "nuclei -version", "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"),
        ("nmap", "nmap --version", "sudo apt-get install nmap"),
        ("ffuf", "ffuf -V", "go install -v github.com/ffuf/ffuf/v2@latest"),
        ("dalfox", "dalfox version", "go install github.com/hahwul/dalfox/v2@latest"),
    ]
    
    for tool_name, check_cmd, install_hint in tools:
        result = TestResult(f"Tool: {tool_name}")
        try:
            proc = subprocess.run(
                check_cmd.split(),
                capture_output=True,
                timeout=5
            )
            if proc.returncode == 0:
                result.passed = True
                result.message = f"{tool_name} available"
            else:
                result.message = f"{tool_name} not found"
                result.issues.append(f"Install: {install_hint}")
        except FileNotFoundError:
            result.message = f"{tool_name} not found in PATH"
            result.issues.append(f"Install: {install_hint}")
        except Exception as e:
            result.message = f"Error checking {tool_name}: {e}"
        results.append(result)
    
    # Test httpx (special check)
    result = TestResult("Tool: httpx (ProjectDiscovery)")
    try:
        proc = subprocess.run(
            ["httpx", "-version"],
            capture_output=True,
            timeout=5
        )
        if proc.returncode == 0:
            # Verify it's ProjectDiscovery httpx
            test_proc = subprocess.run(
                ["httpx", "-u", "https://example.com", "-silent", "-json"],
                capture_output=True,
                timeout=5
            )
            if "no such option" not in test_proc.stderr.decode().lower():
                result.passed = True
                result.message = "httpx (ProjectDiscovery) available"
            else:
                result.message = "httpx found but is Python httpx (not ProjectDiscovery)"
                result.issues.append("Install: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest")
        else:
            result.message = "httpx not found"
            result.issues.append("Install: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest")
    except FileNotFoundError:
        result.message = "httpx not found"
        result.issues.append("Install: go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest")
    except Exception as e:
        result.message = f"Error: {e}"
    results.append(result)
    
    # Test sqlmap (in venv)
    result = TestResult("Tool: sqlmap (in venv)")
    venv_sqlmap = backend_path / "venv" / "bin" / "sqlmap"
    if venv_sqlmap.exists():
        try:
            proc = subprocess.run(
                [str(venv_sqlmap), "--version"],
                capture_output=True,
                timeout=5
            )
            if proc.returncode == 0:
                result.passed = True
                result.message = "sqlmap available in venv"
            else:
                result.message = "sqlmap in venv but not executable"
        except Exception as e:
            result.message = f"Error: {e}"
    else:
        result.message = "sqlmap not found in venv"
        result.issues.append("Install: cd backend && source venv/bin/activate && pip install sqlmap")
    results.append(result)
    
    return results

def test_wordlists() -> TestResult:
    """Test wordlist availability"""
    result = TestResult("FFuF Wordlist")
    wordlist_path = backend_path / "wordlists" / "ffuf-small.txt"
    if wordlist_path.exists():
        if wordlist_path.stat().st_size > 0:
            result.passed = True
            line_count = sum(1 for _ in wordlist_path.open())
            result.message = f"Wordlist exists ({line_count} lines)"
        else:
            result.message = "Wordlist file is empty"
            result.issues.append("Create or download wordlist content")
    else:
        result.message = "Wordlist not found"
        result.issues.append("Create: backend/wordlists/ffuf-small.txt")
        result.issues.append("Or set THANDEV_FFUF_WORDLIST environment variable")
    return result

def test_tool_detection() -> TestResult:
    """Test Python tool detection"""
    result = TestResult("Python Tool Detection")
    try:
        from app.services.tools import ToolExecutor
        executor = ToolExecutor()
        tool_ids = ['nuclei', 'nmap', 'httpx', 'ffuf', 'dalfox', 'sqlmap']
        all_available, missing = executor.check_tool_dependencies(tool_ids)
        if all_available:
            result.passed = True
            result.message = "All tools detected by Python ToolExecutor"
        else:
            result.message = f"Missing tools: {', '.join(missing)}"
            result.issues.append("Some tools not in PATH or wrong locations")
            result.issues.append("Check tool installation and PATH configuration")
    except Exception as e:
        result.message = f"Error: {e}"
        result.issues.append("Check tool detection logic")
    return result

def test_config() -> List[TestResult]:
    """Test configuration"""
    results = []
    
    # Test backend config
    result = TestResult("Backend Configuration")
    try:
        from app.core.config import settings
        result.passed = True
        result.message = "Backend config loaded"
        
        # Check critical settings
        if not settings.DATABASE_URL:
            result.issues.append("DATABASE_URL not set")
        if not settings.REDIS_URL:
            result.issues.append("REDIS_URL not set")
        if settings.BRAIN_SERVICE_ENABLED:
            result.message += f" (Brain enabled: {settings.BRAIN_SERVICE_URL})"
        else:
            result.message += " (Brain disabled)"
    except Exception as e:
        result.message = f"Config error: {e}"
        result.issues.append("Check backend/.env file")
    results.append(result)
    
    return results

def main():
    """Run all tests"""
    print_header("Thandev End-to-End System Tests")
    
    all_results: List[TestResult] = []
    all_issues: List[str] = []
    
    # Phase 1: Infrastructure
    print_header("Phase 1: Infrastructure Tests")
    all_results.append(test_database())
    all_results.append(test_redis())
    all_results.append(test_backend_service())
    all_results.append(test_brain_service())
    
    # Phase 2: Tools
    print_header("Phase 2: Tool Availability Tests")
    all_results.extend(test_tools())
    all_results.append(test_wordlists())
    all_results.append(test_tool_detection())
    
    # Phase 3: Configuration
    print_header("Phase 3: Configuration Tests")
    all_results.extend(test_config())
    
    # Print results
    print_header("Test Results Summary")
    passed = sum(1 for r in all_results if r.passed)
    failed = len(all_results) - passed
    
    for result in all_results:
        print_test(result)
        if not result.passed:
            all_issues.extend([f"{result.name}: {issue}" for issue in result.issues])
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.NC}")
    print(f"Summary: {Colors.GREEN}{passed} passed{Colors.NC}, {Colors.RED}{failed} failed{Colors.NC}")
    print(f"{Colors.BLUE}{'='*60}{Colors.NC}\n")
    
    # Print issues
    if all_issues:
        print_header("Issues Found")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
        print()
    
    # Save results to file
    results_file = repo_root / "TEST_RESULTS_E2E.json"
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": time.time(),
            "passed": passed,
            "failed": failed,
            "total": len(all_results),
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "issues": r.issues
                }
                for r in all_results
            ],
            "all_issues": all_issues
        }, f, indent=2)
    
    print(f"Results saved to: {results_file}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())

