#!/usr/bin/env python3
"""
WebSocket Manager for Synap-Forge
Handles WebSocket connections and message broadcasting
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manage WebSocket connections and message broadcasting"""
    
    def __init__(self, max_connections: int = 100):
        self.active_connections: Dict[str, WebSocket] = {}
        self.max_connections = max_connections
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str) -> bool:
        """Connect a new WebSocket client"""
        async with self._lock:
            if len(self.active_connections) >= self.max_connections:
                logger.warning(f"Max connections reached, rejecting {client_id}")
                return False
            
            await websocket.accept()
            self.active_connections[client_id] = websocket
            logger.info(f"Client {client_id} connected ({len(self.active_connections)} active)")
            return True
    
    async def disconnect(self, client_id: str):
        """Disconnect a WebSocket client"""
        async with self._lock:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
                logger.info(f"Client {client_id} disconnected ({len(self.active_connections)} active)")
    
    async def send_message(self, client_id: str, message: dict):
        """Send a message to a specific client"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except WebSocketDisconnect:
                await self.disconnect(client_id)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
    
    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients"""
        disconnected = []
        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except WebSocketDisconnect:
                disconnected.append(client_id)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
        
        for client_id in disconnected:
            await self.disconnect(client_id)
    
    async def broadcast_state(self, state: dict):
        """Broadcast system state to all clients"""
        message = {
            "type": "state",
            "data": state
        }
        await self.broadcast(message)
    
    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "active": len(self.active_connections),
            "max": self.max_connections,
            "utilization": len(self.active_connections) / self.max_connections if self.max_connections > 0 else 0
        }


# Singleton instance
ws_manager = WebSocketManager()
