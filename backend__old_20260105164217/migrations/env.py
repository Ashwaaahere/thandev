"""
Alembic environment configuration for Thandev v2
"""
import sys
import pathlib
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add backend to Python path
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

# Import database Base first
from app.core.database import Base
from app.core.config import settings

# Import ALL models to ensure they're registered with Base.metadata
# This must happen before target_metadata = Base.metadata is set
# Import explicitly to ensure all models are loaded
from app.models.user import User  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.scan import ScanJob  # noqa: F401
from app.models.finding import Finding, ToolResult  # noqa: F401
from app.models.domain_verification import DomainVerification, DomainVerificationStatus  # noqa: F401
from app.models.entitlement import Entitlement  # noqa: F401
from app.models.performance_scan import PerformanceScan  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.allowed_domain import AllowedDomain  # noqa: F401

# Also import via __init__ to catch any models we might have missed
from app.models import *  # noqa: F401, F403

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from settings
# CANONICAL ENV VAR: DATABASE_URL (same as app.core.config.Settings.DATABASE_URL)
# This ensures migrations run against the same database as the application
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set target metadata
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with improved error handling."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()
    except Exception as e:
        # Log the original exception with full traceback
        import traceback
        logger.error("=" * 80)
        logger.error("MIGRATION FAILED - Original Exception:")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception message: {str(e)}")
        logger.error("Full traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        
        # If this is a chained exception (from another exception), log the original
        if e.__cause__:
            logger.error("Original cause:")
            logger.error(f"  Type: {type(e.__cause__).__name__}")
            logger.error(f"  Message: {str(e.__cause__)}")
            if hasattr(e.__cause__, 'orig'):
                logger.error(f"  SQLAlchemy orig: {e.__cause__.orig}")
        
        # Provide user-friendly error message
        error_msg = str(e)
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            raise RuntimeError(
                f"Failed to connect to database: {error_msg}. "
                f"Please check your DATABASE_URL setting and ensure the database is running."
            ) from e
        else:
            # For other errors (table/column), re-raise the original exception
            # This allows migrations to handle missing tables/columns themselves
            # (e.g., migration 0013 creates notifications without FKs if tenants/users don't exist)
            # Don't wrap it in RuntimeError - let the original exception propagate
            raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
