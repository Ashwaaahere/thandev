from sqlalchemy import Column, Text, DateTime, Boolean, Numeric, Integer, String, Index, CheckConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from .db import Base

# Detect if we're using PostgreSQL
import os
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./thandev.db")
is_postgresql = DATABASE_URL.startswith("postgresql")

# Use JSONB for PostgreSQL, JSON/Text for SQLite
if is_postgresql:
    JSONType = JSONB
else:
    JSONType = Text  # SQLite stores JSON as text

class ThreatItem(Base):
    __tablename__ = "threat_item"
    id = Column(String(36), primary_key=True)
    source = Column(Text, nullable=False)
    source_id = Column(Text)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    published_at = Column(DateTime(timezone=True))
    discovered_at = Column(DateTime(timezone=True))
    url = Column(Text)
    cve_id = Column(Text, index=True)  # Indexed for faster lookups
    cwe_id = Column(Text)
    vendor = Column(Text)
    product = Column(Text)
    version_range = Column(Text)
    cvss_v2 = Column(Numeric)
    cvss_v3 = Column(Numeric)
    epss_score = Column(Numeric)
    is_kev = Column(Boolean, default=False, index=True)  # Indexed for filtering
    has_exploit = Column(Boolean, default=False, index=True)  # Indexed for filtering
    tags = Column(JSONType)  # JSONB for PostgreSQL, Text for SQLite
    raw = Column(JSONType)  # JSONB for PostgreSQL, Text for SQLite
    
    # Indexes for frequently queried fields
    __table_args__ = (
        Index('idx_threat_item_published_at', 'published_at'),
        Index('idx_threat_item_cve_id', 'cve_id'),
        Index('idx_threat_item_is_kev', 'is_kev'),
        Index('idx_threat_item_has_exploit', 'has_exploit'),
        Index('idx_threat_item_source', 'source'),
    )

class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id = Column(String(36), primary_key=True)
    user_id = Column(Text, nullable=False, index=True)  # Indexed for user queries
    url = Column(Text, nullable=False)
    domain = Column(Text)
    tier = Column(String(10), nullable=False)  # level0, level1, level2
    status = Column(String(20), default='pending', index=True)  # Indexed for status queries
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)  # Indexed for sorting
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    artifact_urls = Column(JSONType)  # JSONB for PostgreSQL, Text for SQLite
    summary = Column(JSONType)  # JSONB for PostgreSQL, Text for SQLite
    preset_version = Column(String(20), default='1.0')
    execution_id = Column(Text)  # Cloud Run execution ID
    
    # Constraints
    __table_args__ = (
        CheckConstraint("tier IN ('level0', 'level1', 'level2')", name='check_tier'),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'error')", name='check_status'),
        # Composite index for rate limiting queries
        Index('idx_scan_jobs_user_status', 'user_id', 'status'),
        Index('idx_scan_jobs_created_at', 'created_at'),
        Index('idx_scan_jobs_status', 'status'),
    )

class PerformanceScanJob(Base):
    __tablename__ = "performance_scan_jobs"
    id = Column(String(36), primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    url = Column(Text, nullable=False)
    device = Column(String(20), default='desktop')  # desktop, mobile
    status = Column(String(20), default='pending', index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
    result = Column(JSONType)  # JSONB for PostgreSQL, Text for SQLite
    error = Column(Text)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'running', 'completed', 'error')", name='check_perf_status'),
        CheckConstraint("device IN ('desktop', 'mobile')", name='check_device'),
        Index('idx_perf_scan_jobs_user_status', 'user_id', 'status'),
        Index('idx_perf_scan_jobs_created_at', 'created_at'),
    )
