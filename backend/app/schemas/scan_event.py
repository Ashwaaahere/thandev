"""
Pydantic schemas for ScanEvent and ScanToolState
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class ScanEventCreate(BaseModel):
    """Schema for creating a scan event"""
    phase: str = Field(..., description="Scan phase (prepare, enumerate, scan, correlate, finalize)")
    tool: Optional[str] = Field(None, description="Tool name (httpx, nuclei, zap, katana, etc.)")
    stage: str = Field(..., description="Stage (queued, starting, running, parsing, uploading, completed, failed)")
    message: str = Field(..., description="Human-readable status message")
    progress: Optional[float] = Field(None, description="Progress percentage (0.0 to 1.0)", ge=0.0, le=1.0)
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ScanEventBatchCreate(BaseModel):
    """Schema for batch creating scan events"""
    events: List[ScanEventCreate] = Field(..., description="List of events to create")


class ScanEventResponse(BaseModel):
    """Schema for scan event response"""
    id: str
    scan_id: str
    phase: str
    tool: Optional[str]
    stage: str
    message: str
    progress: Optional[float]
    meta: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScanToolStateResponse(BaseModel):
    """Schema for scan tool state response"""
    id: str
    scan_id: str
    tool: str
    phase: str
    stage: str
    message: str
    progress: Optional[float]
    meta: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ScanInventoryCreate(BaseModel):
    """Schema for creating scan asset inventory"""
    inventory: Dict[str, Any] = Field(..., description="Asset inventory JSON")
    
    class Config:
        json_schema_extra = {
            "example": {
                "inventory": {
                    "target": "https://example.com",
                    "scope": {
                        "allowed_hosts": ["example.com", "www.example.com"],
                        "start_url": "https://example.com",
                        "final_url": "https://www.example.com/"
                    },
                    "discovery": {
                        "httpx": {
                            "status": 200,
                            "title": "Example Domain",
                            "tech": ["Nginx"],
                            "tls": {}
                        },
                        "katana": {
                            "urls_count": 150,
                            "urls": []
                        },
                        "gau": {
                            "urls_count": 200,
                            "urls": []
                        },
                        "merged": {
                            "all_urls_count": 300,
                            "all_urls": [],
                            "param_urls": [],
                            "unique_paths": [],
                            "interesting": {
                                "auth": [],
                                "admin": [],
                                "api": [],
                                "docs": [],
                                "uploads": [],
                                "graphql": [],
                                "swagger": []
                            }
                        },
                        "arjun": {
                            "tested_urls": [],
                            "params_by_url": {}
                        }
                    },
                    "timestamps": {
                        "started_at": "2026-01-25T10:00:00Z",
                        "ended_at": "2026-01-25T10:05:00Z"
                    }
                }
            }
        }


class ScanInventoryResponse(BaseModel):
    """Schema for scan inventory response"""
    scan_id: str
    inventory: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

