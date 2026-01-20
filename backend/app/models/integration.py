"""
Integration model for storing third-party integrations (GitHub App, OAuth, etc.)
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
import uuid
import os

from app.core.database import Base

# Detect if we're using PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
is_postgresql = DATABASE_URL.startswith("postgresql")

# Use JSONB for PostgreSQL, JSON for SQLite
if is_postgresql:
    JSONType = JSONB
else:
    JSONType = JSON


class Integration(Base):
    """Integration model for third-party service connections"""
    
    __tablename__ = "integrations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(Text, nullable=False)  # 'github'
    installation_id = Column(Text, nullable=True)  # GitHub App installation ID
    access_meta = Column(JSONType, nullable=False, server_default="{}")  # Additional metadata
    token_encrypted = Column(Text, nullable=True)  # Encrypted token (if OAuth used, avoid storing long-lived tokens)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index("idx_integrations_user_provider", "user_id", "provider"),
    )
