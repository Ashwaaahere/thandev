"""
WebSocket endpoint for real-time scan progress updates
"""
import logging
import asyncio
import json
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scan import ScanJob
from app.models.scan_tool_state import ScanToolState

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ws",
    tags=["websocket"],
)

# Connection manager for WebSocket connections
class ConnectionManager:
    def __init__(self):
        # Map of scan_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, scan_id: str):
        """Accept WebSocket connection and add to scan subscribers"""
        await websocket.accept()
        if scan_id not in self.active_connections:
            self.active_connections[scan_id] = set()
        self.active_connections[scan_id].add(websocket)
        logger.info(f"WebSocket connected for scan {scan_id}, total connections: {len(self.active_connections[scan_id])}")
    
    def disconnect(self, websocket: WebSocket, scan_id: str):
        """Remove WebSocket connection from scan subscribers"""
        if scan_id in self.active_connections:
            self.active_connections[scan_id].discard(websocket)
            if not self.active_connections[scan_id]:
                del self.active_connections[scan_id]
        logger.info(f"WebSocket disconnected for scan {scan_id}")
    
    async def broadcast_to_scan(self, scan_id: str, message: dict):
        """Broadcast message to all subscribers of a scan"""
        if scan_id not in self.active_connections:
            return
        
        # Remove dead connections
        dead_connections = set()
        for connection in self.active_connections[scan_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.active_connections[scan_id].discard(connection)

manager = ConnectionManager()


@router.websocket("/scans/{scan_id}")
async def websocket_scan_progress(
    websocket: WebSocket,
    scan_id: str,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time scan progress updates.
    
    Clients connect to this endpoint to receive real-time events for a specific scan.
    
    Message format:
    {
        "type": "tool_state",
        "data": {
            "tool": "katana",
            "phase": "enumerate",
            "stage": "completed",
            "message": "Found 150 URLs",
            "progress": 1.0,
            "meta": {"urls_found": 150}
        }
    }
    """
    # Verify scan exists
    scan_job = db.query(ScanJob).filter(ScanJob.id == scan_id).first()
    if not scan_job:
        await websocket.close(code=1008, reason="Scan not found")
        return
    
    # Accept connection
    await manager.connect(websocket, scan_id)
    
    try:
        # Send initial state
        tool_states = db.query(ScanToolState).filter(
            ScanToolState.scan_id == scan_id
        ).order_by(
            ScanToolState.updated_at.desc()
        ).all()
        
        logger.info(f"[WS] Scan {scan_id}: Found {len(tool_states)} tool states to send")
        for ts in tool_states:
            logger.info(f"[WS] Tool state: {ts.tool} - {ts.phase} - {ts.stage}")
        
        # Send initial tool states
        tool_states_data = [
            {
                "tool": ts.tool,
                "phase": ts.phase,
                "stage": ts.stage,
                "progress": ts.progress,
                "last_message": ts.message,
                "meta": ts.meta,
                "updated_at": ts.updated_at.isoformat() if ts.updated_at else None,
            }
            for ts in tool_states
        ]
        logger.info(f"[WS] Sending initial_tool_states: {tool_states_data}")
        await websocket.send_json({
            "type": "initial_tool_states",
            "tool_states": tool_states_data
        })
        
        # Keep connection alive and listen for messages
        while True:
            try:
                # Wait for client messages (ping/pong for keepalive)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WebSocket error for scan {scan_id}: {e}")
                break
    
    finally:
        manager.disconnect(websocket, scan_id)


async def broadcast_tool_state_to_scan(scan_id: str, tool_state_data: dict):
    """
    Broadcast tool state update to all WebSocket subscribers of a scan.
    
    Args:
        scan_id: Scan job ID
        tool_state_data: Tool state data to broadcast
    """
    await manager.broadcast_to_scan(scan_id, {
        "type": "tool_state",
        "tool_state": tool_state_data
    })

