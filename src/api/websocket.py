"""WebSocket handlers for real-time alerts."""

import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages WebSocket connections for real-time alerts."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and track new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)
        logger.info(f"New WebSocket connection. Total: {len(self._connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove disconnected WebSocket."""
        self._connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self._connections:
            return

        message_json = json.dumps(message)
        disconnected = set()

        for websocket in self._connections:
            try:
                await websocket.send_text(message_json)
            except Exception:
                disconnected.add(websocket)

        # Clean up disconnected sockets
        self._connections -= disconnected

    async def send_alert(
        self,
        alert_type: str,
        identity_id: str,
        details: dict,
    ):
        """Send fraud alert to all connected clients."""
        await self.broadcast({
            "type": "alert",
            "alert_type": alert_type,
            "identity_id": identity_id,
            "details": details,
        })


# Global alert manager instance
alert_manager = AlertManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time alerts."""
    await alert_manager.connect(websocket)

    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle ping/pong
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        alert_manager.disconnect(websocket)
