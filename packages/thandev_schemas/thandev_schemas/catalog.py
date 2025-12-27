"""
Tool catalog schemas
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any


class ModeDefinition(BaseModel):
    """Definition of a tool mode"""
    mode_id: str = Field(..., description="Mode identifier")
    name: str = Field(..., description="Human-readable mode name")
    description: str = Field(..., description="Mode description")
    params_schema: Dict[str, Any] = Field(..., description="JSON Schema for mode parameters")
    constraints: Dict[str, Any] = Field(default_factory=dict, description="Mode constraints")
    
    model_config = ConfigDict(extra="forbid")


class ToolDefinition(BaseModel):
    """Definition of a tool"""
    tool_id: str = Field(..., description="Tool identifier")
    name: str = Field(..., description="Human-readable tool name")
    description: str = Field(..., description="Tool description")
    allowed_target_types: List[str] = Field(..., description="Target types this tool can scan")
    modes: List[ModeDefinition] = Field(..., description="Available modes for this tool")
    
    model_config = ConfigDict(extra="forbid")


class ToolCatalog(BaseModel):
    """Complete tool catalog"""
    tools: List[ToolDefinition] = Field(..., description="List of available tools")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Catalog metadata")
    
    model_config = ConfigDict(extra="forbid")




