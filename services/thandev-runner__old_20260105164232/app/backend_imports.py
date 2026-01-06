"""
Utility for importing modules from the backend service.

This module handles the complexity of importing from backend/app when
the runner service also has an 'app' module that might be cached first.
"""
import sys
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Cache the backend path calculation
_backend_path: Optional[Path] = None
_runner_path: Optional[Path] = None


def _ensure_backend_path() -> Path:
    """Ensure backend path is calculated and cached."""
    global _backend_path, _runner_path
    
    if _backend_path is None:
        # Calculate paths relative to this file
        # This file is at: services/thandev-runner/app/backend_imports.py
        # Backend is at: backend/ (sibling of services/)
        current_file = Path(__file__).resolve()
        # current_file.parent = services/thandev-runner/app
        # current_file.parent.parent = services/thandev-runner
        # current_file.parent.parent.parent = services
        # current_file.parent.parent.parent.parent = project root (thandev/)
        try:
            project_root = current_file.parent.parent.parent.parent
            _runner_path = current_file.parent.parent.parent  # services/thandev-runner
            _backend_path = project_root / "backend"  # thandev/backend/
        except (IndexError, AttributeError):
            # Fallback if path structure is different (e.g., in Docker)
            # Try alternative paths
            try:
                project_root = current_file.parent.parent.parent
                _backend_path = project_root / "backend"
            except (IndexError, AttributeError):
                # Last resort: use /app/backend if it exists, otherwise None
                _backend_path = Path("/app/backend")
        
        # If backend path doesn't exist, try alternative locations
        if not _backend_path.exists():
            # Try common alternative paths
            alternatives = [
                Path("/app/backend"),  # Docker container
                Path("/backend"),  # Absolute path
                current_file.parent.parent.parent.parent / "backend" if current_file.parent.parent.parent.parent.exists() else None,
            ]
            for alt_path in alternatives:
                if alt_path and alt_path.exists():
                    _backend_path = alt_path
                    logger.info(f"Using alternative backend path: {_backend_path}")
                    break
            else:
                # If no backend path exists, log warning but don't raise error
                # The code will handle missing backend gracefully
                logger.warning(f"Backend path does not exist: {_backend_path}. Backend imports will be disabled.")
                _backend_path = None
    
    if _backend_path is None:
        raise ImportError("Backend path not found. Cannot import backend modules.")
    
    return _backend_path


def _clear_cached_app_module():
    """
    Clear cached 'app.services.*' modules that conflict with backend.
    
    IMPORTANT: We DON'T clear local app modules like app.database, app.config, etc.
    We only clear app.services.* modules to allow backend's version to load.
    """
    global _runner_path, _backend_path
    
    if _backend_path is None:
        _ensure_backend_path()
    
    # Only clear app.services.* modules that might conflict with backend
    # Preserve local app modules like app.database, app.config, app.executor, etc.
    modules_to_remove = [name for name in list(sys.modules.keys()) 
                       if name.startswith("app.services")]
    for module_name in modules_to_remove:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            module_file = getattr(module, "__file__", None)
            if module_file:
                module_path = Path(module_file).resolve()
                # Only remove if it's from runner, not from backend
                if str(_runner_path) in str(module_path) and str(_backend_path) not in str(module_path):
                    logger.debug(f"Clearing cached module from wrong location: {module_name} ({module_file})")
                    del sys.modules[module_name]
            else:
                # No file attribute, likely a namespace package - remove it
                logger.debug(f"Clearing cached namespace module: {module_name}")
                del sys.modules[module_name]


def ensure_backend_in_path():
    """
    Ensure backend path is first in sys.path and clear conflicting cached modules.
    
    Call this before importing any modules from backend/app.
    """
    import types
    
    backend_path = _ensure_backend_path()
    backend_path_str = str(backend_path)
    backend_app_path = backend_path / "app"
    backend_services_path = backend_app_path / "services"
    
    # Ensure backend path is first
    if backend_path_str in sys.path:
        sys.path.remove(backend_path_str)
    sys.path.insert(0, backend_path_str)
    
    # Clear cached app.services.* modules
    _clear_cached_app_module()
    
    # Ensure app.services namespace package exists and points to backend
    # This is critical: after clearing app.services.*, we need to recreate the namespace
    if "app.services" not in sys.modules:
        services_module = types.ModuleType("app.services")
        services_module.__path__ = [str(backend_services_path)]
        sys.modules["app.services"] = services_module
    else:
        # If it exists, ensure it has the correct path
        services_module = sys.modules["app.services"]
        if not hasattr(services_module, "__path__") or services_module.__path__ is None:
            services_module.__path__ = []
        # Ensure backend services path is first
        backend_services_path_str = str(backend_services_path)
        if backend_services_path_str not in services_module.__path__:
            # Remove any existing paths from runner
            services_module.__path__ = [p for p in services_module.__path__ 
                                      if str(_runner_path) not in p]
            services_module.__path__.insert(0, backend_services_path_str)
    
    # Also ensure app module can find backend modules
    if "app" in sys.modules:
        app_module = sys.modules["app"]
        if not hasattr(app_module, "__path__") or app_module.__path__ is None:
            app_module.__path__ = []
        # Add backend app path if not already there
        backend_app_path_str = str(backend_app_path)
        if backend_app_path_str not in app_module.__path__:
            # Remove any existing backend paths first (avoid duplicates)
            app_module.__path__ = [p for p in app_module.__path__ 
                                 if p != backend_app_path_str]
            app_module.__path__.insert(0, backend_app_path_str)


def import_from_backend(module_path: str) -> Any:
    """
    Import a module from backend/app.
    
    Args:
        module_path: Module path relative to backend/app, e.g., "services.tools"
                    or "services.findings_ingestor"
    
    Returns:
        The imported module
    
    Example:
        tools_module = import_from_backend("services.tools")
        ToolExecutor = tools_module.ToolExecutor
    """
    ensure_backend_in_path()
    
    full_path = f"app.{module_path}"
    try:
        module = __import__(full_path, fromlist=[""])
        return module
    except ImportError as e:
        logger.error(f"Failed to import {full_path}: {e}")
        logger.error(f"Python path (first 5): {sys.path[:5]}")
        raise


def get_backend_path() -> Path:
    """Get the backend path."""
    return _ensure_backend_path()

