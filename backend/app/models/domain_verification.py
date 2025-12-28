"""
Domain verification model
"""
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    Text,
    Index,
    TypeDecorator,
)
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class DomainVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class DomainVerificationStatusType(TypeDecorator):
    """Custom type that ensures enum values (lowercase strings) are stored"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def process_bind_param(self, value, dialect):
        """Convert enum to lowercase string value when inserting - CRITICAL: always return lowercase"""
        import logging
        logger = logging.getLogger(__name__)
        
        if value is None:
            return None
        
        # CRITICAL: Always convert to lowercase string
        # Handle enum object - extract the value (which is already lowercase)
        if isinstance(value, DomainVerificationStatus):
            result = value.value  # This is "pending", "verified", etc. (lowercase)
            logger.info(f"TypeDecorator: converted enum {value.name} to value '{result}'")
            return result
        
        # Handle string - FORCE lowercase (in case somehow uppercase got through)
        if isinstance(value, str):
            result = value.lower().strip()
            if result != value:
                logger.warning(f"TypeDecorator: converted uppercase string '{value}' to lowercase '{result}'")
            else:
                logger.debug(f"TypeDecorator: string '{value}' is already lowercase")
            return result
        
        # Fallback: convert to string and FORCE lowercase
        result = str(value).lower().strip()
        logger.warning(f"TypeDecorator: converted {type(value)} '{value}' to lowercase string '{result}'")
        return result
    
    def process_result_value(self, value, dialect):
        """Convert string back when reading"""
        if value is None:
            return None
        # Return as string - comparisons will handle both enum and string
        return value


class DomainVerification(Base):
    __tablename__ = "domain_verifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)  # registrable domain (eTLD+1)
    # Use custom TypeDecorator to ensure lowercase strings are stored
    # This works with PostgreSQL enum columns by inserting the lowercase value
    status = Column(DomainVerificationStatusType(), nullable=False)
    token = Column(String(255), nullable=False)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# Composite index for quick lookup by project+domain
Index("ix_domain_verifications_project_domain", DomainVerification.project_id, DomainVerification.domain)

