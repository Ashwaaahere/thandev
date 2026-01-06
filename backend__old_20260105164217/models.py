# backend/models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, JSON, text, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

class Exploit(Base):
    __tablename__ = "exploits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cve_id = Column(String(64), index=True, nullable=True, unique=True)
    title = Column(String(512), nullable=False)
    description = Column(String, nullable=True)  # safe, short description from NVD
    cvss_v3 = Column(Float, nullable=True)
    severity = Column(String(32), nullable=True)  # critical/high/medium/low/none
    published_at = Column(DateTime, nullable=True)
    references = Column(JSONB, nullable=True)    # list of {url, source, note}
    source_tags = Column(JSONB, nullable=True)   # e.g., ["nvd", "mitre"]
    provenance = Column(JSONB, nullable=True)    # raw metadata about source/snapshots
    created_at = Column(DateTime, default=datetime.utcnow, server_default=text("now()"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=text("now()"))

# useful index for queries
Index('ix_exploits_cve_severity', Exploit.cve_id, Exploit.severity)
