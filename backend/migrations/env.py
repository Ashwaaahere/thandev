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

# Import models and database
from app.core.database import Base
from app.core.config import settings
from app.models import *  # noqa: F401, F403

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from settings
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

            # Use autocommit mode for PostgreSQL to avoid transaction abort issues
            # when indexes/tables already exist
            if connectable.dialect.name == 'postgresql':
                # For PostgreSQL, use autocommit to allow individual operations to succeed/fail independently
                connection = connectable.connect()
                connection.execution_options(autocommit=True)
                context.configure(
                    connection=connection, target_metadata=target_metadata
                )
                context.run_migrations()
                connection.close()
            else:
                # For SQLite and others, use transaction as before
                with context.begin_transaction():
                    context.run_migrations()
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        # Provide user-friendly error message
        error_msg = str(e)
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            raise RuntimeError(
                f"Failed to connect to database: {error_msg}. "
                f"Please check your DATABASE_URL setting and ensure the database is running."
            ) from e
        elif "table" in error_msg.lower() or "column" in error_msg.lower():
            raise RuntimeError(
                f"Database schema error: {error_msg}. "
                f"This may indicate a migration conflict. Try running 'alembic downgrade -1' first."
            ) from e
        else:
            raise RuntimeError(
                f"Migration error: {error_msg}. "
                f"Check the logs for more details."
            ) from e


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
