import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Thread-safe WebSocket connection manager with async/sync broadcast support."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected. Total clients: %d", len(self.active_connections)
        )

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                "WebSocket client disconnected. Total clients: %d",
                len(self.active_connections),
            )

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast JSON payload to all connected clients."""
        dead_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    def broadcast_sync(self, data: dict[str, Any]) -> None:
        """Thread-safe sync dispatch callable from background inference threads."""
        if not self.active_connections:
            return
        if self._loop is not None and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(data), self._loop)
        else:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.broadcast(data), loop)
                else:
                    loop.run_until_complete(self.broadcast(data))
            except Exception:
                pass


ws_manager = ConnectionManager()


@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket) -> None:
    """Real-time push channel for footfall, dwell-map coordinates, queues, and alerts."""
    ws_manager.set_loop(asyncio.get_running_loop())
    await ws_manager.connect(websocket)
    try:
        # Send initial handshake
        await websocket.send_json({"type": "handshake", "status": "connected"})
        while True:
            # Keep alive and receive client heartbeats/pings
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket connection exception: %s", e)
        ws_manager.disconnect(websocket)
