"""
WebSocket endpoint for real-time error notifications
Streams errors to connected frontend clients
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
import asyncio
import json
from datetime import datetime
from app.services.observer_agent import get_observer, SystemError

router = APIRouter(tags=["monitoring"])


class ConnectionManager:
    """Manages WebSocket connections for error notifications"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"✅ WebSocket client connected. Total connections: {len(self.active_connections)}")
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"❌ WebSocket client disconnected. Total connections: {len(self.active_connections)}")
        
    async def broadcast_error(self, error: SystemError):
        """Broadcast error to all connected clients"""
        if not self.active_connections:
            return
            
        error_data = {
            "type": "error",
            "data": error.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(error_data)
            except Exception as e:
                print(f"Error broadcasting to client: {e}")
                disconnected.add(connection)
                
        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_heartbeat(self):
        """Send periodic heartbeat to keep connections alive"""
        heartbeat_data = {
            "type": "heartbeat",
            "timestamp": datetime.utcnow().isoformat(),
            "active_connections": len(self.active_connections)
        }
        
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(heartbeat_data)
            except Exception:
                disconnected.add(connection)
                
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/monitoring/errors")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time error streaming
    Clients connect here to receive live error notifications
    """
    await manager.connect(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to Observer Agent error stream",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and listen for client messages
        while True:
            try:
                # Wait for messages with timeout to allow heartbeat
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle client commands
                if data == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                elif data == "get_recent":
                    # Send recent errors from buffer
                    observer = get_observer()
                    recent_errors = observer.error_buffer[-10:]
                    await websocket.send_json({
                        "type": "recent_errors",
                        "data": [e.to_dict() for e in recent_errors],
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
            except asyncio.TimeoutError:
                # Send heartbeat if no messages received
                await manager.send_heartbeat()
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


def get_connection_manager():
    """Get the global connection manager for broadcasting errors"""
    return manager
