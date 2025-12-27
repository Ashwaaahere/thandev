#!/usr/bin/env python3
"""
System health check script for Thandev
Checks Python interpreter, imports, and configuration
"""
import sys
import os
from pathlib import Path

def check_python():
    """Check Python interpreter path and version"""
    print("=" * 60)
    print("Python Interpreter")
    print("=" * 60)
    print(f"Path: {sys.executable}")
    print(f"Version: {sys.version}")
    print(f"Is venv: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
    print()

def check_imports(module_name, description):
    """Check if a module can be imported"""
    try:
        __import__(module_name)
        print(f"  ✅ {description}")
        return True
    except ImportError as e:
        print(f"  ❌ {description}: {e}")
        return False

def check_backend():
    """Check backend configuration"""
    print("=" * 60)
    print("Backend Service")
    print("=" * 60)
    
    repo_root = Path(__file__).parent.parent
    backend_dir = repo_root / "backend"
    
    # Add backend to path
    sys.path.insert(0, str(backend_dir))
    
    try:
        from app.core.config import settings
        print(f"  DATABASE_URL: {settings.DATABASE_URL}")
        print(f"  REDIS_URL: {settings.REDIS_URL}")
        print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
        print(f"  BRAIN_SERVICE_ENABLED: {settings.BRAIN_SERVICE_ENABLED}")
        
        # Check key imports
        print("\n  Key imports:")
        check_imports("dotenv", "python-dotenv")
        check_imports("pydantic_settings", "pydantic-settings")
        check_imports("alembic", "alembic")
        check_imports("sqlalchemy", "sqlalchemy")
        check_imports("redis", "redis")
        check_imports("fastapi", "fastapi")
        check_imports("uvicorn", "uvicorn")
        
    except Exception as e:
        print(f"  ❌ Error loading backend config: {e}")
    
    print()

def check_runner():
    """Check runner configuration"""
    print("=" * 60)
    print("Runner Service")
    print("=" * 60)
    
    repo_root = Path(__file__).parent.parent
    runner_dir = repo_root / "services" / "thandev-runner"
    
    # Check if runner directory exists
    if not runner_dir.exists():
        print(f"  ⚠️  Runner directory not found: {runner_dir}")
        print()
        return
    
    # Add runner to path
    sys.path.insert(0, str(runner_dir))
    
    try:
        # Change to runner directory to load config properly
        original_cwd = os.getcwd()
        os.chdir(str(runner_dir))
        from app.config import settings
        os.chdir(original_cwd)
        
        print(f"  DATABASE_URL: {settings.DATABASE_URL}")
        print(f"  REDIS_URL: {settings.REDIS_URL}")
        print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
        
        # Check key imports
        print("\n  Key imports:")
        check_imports("pydantic_settings", "pydantic-settings")
        check_imports("sqlalchemy", "sqlalchemy")
        check_imports("redis", "redis")
        check_imports("httpx", "httpx")
        
    except Exception as e:
        print(f"  ⚠️  Error loading runner config: {e}")
        print(f"     (This is OK if runner venv is not set up yet)")
    
    print()

def check_brain():
    """Check brain configuration"""
    print("=" * 60)
    print("Brain Service")
    print("=" * 60)
    
    repo_root = Path(__file__).parent.parent
    brain_dir = repo_root / "services" / "thandev-brain"
    
    # Check if brain directory exists
    if not brain_dir.exists():
        print(f"  ⚠️  Brain directory not found: {brain_dir}")
        print()
        return
    
    # Add brain to path
    sys.path.insert(0, str(brain_dir))
    
    try:
        # Change to brain directory to load config properly
        original_cwd = os.getcwd()
        os.chdir(str(brain_dir))
        from app.core.config import settings
        os.chdir(original_cwd)
        
        print(f"  REDIS_URL: {settings.REDIS_URL}")
        if hasattr(settings, 'QDRANT_URL'):
            print(f"  QDRANT_URL: {settings.QDRANT_URL}")
        if hasattr(settings, 'RAG_STORE_TYPE'):
            print(f"  RAG_STORE_TYPE: {settings.RAG_STORE_TYPE}")
        print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
        
        # Check key imports
        print("\n  Key imports:")
        check_imports("pydantic_settings", "pydantic-settings")
        check_imports("fastapi", "fastapi")
        check_imports("uvicorn", "uvicorn")
        check_imports("redis", "redis")
        
    except Exception as e:
        print(f"  ⚠️  Error loading brain config: {e}")
        print(f"     (This is OK if brain venv is not set up yet)")
    
    print()

def check_database_urls_match():
    """Check if backend and runner use the same DATABASE_URL"""
    print("=" * 60)
    print("Database URL Consistency")
    print("=" * 60)
    
    repo_root = Path(__file__).parent.parent
    backend_dir = repo_root / "backend"
    runner_dir = repo_root / "services" / "thandev-runner"
    
    try:
        sys.path.insert(0, str(backend_dir))
        from app.core.config import settings as backend_settings
        backend_db = backend_settings.DATABASE_URL
        
        sys.path.insert(0, str(runner_dir))
        from app.config import settings as runner_settings
        runner_db = runner_settings.DATABASE_URL
        
        if backend_db == runner_db:
            print(f"  ✅ Backend and Runner use the same DATABASE_URL")
            print(f"     {backend_db}")
        else:
            print(f"  ❌ DATABASE_URL mismatch!")
            print(f"     Backend: {backend_db}")
            print(f"     Runner:  {runner_db}")
            print(f"     This will cause 'Scan job not found' errors!")
    except Exception as e:
        print(f"  ⚠️  Could not compare DATABASE_URLs: {e}")
    
    print()

def main():
    """Run all health checks"""
    print("\n" + "=" * 60)
    print("Thandev System Health Check")
    print("=" * 60 + "\n")
    
    check_python()
    check_backend()
    check_runner()
    check_brain()
    check_database_urls_match()
    
    print("=" * 60)
    print("Health check complete!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()

