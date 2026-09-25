import asyncio
import contextlib
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.sse import EventSourceResponse, ServerSentEvent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telemetry"])


class ConnectionManager:
    """Thread-safe WebSocket and SSE connection manager with broadcast support."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []
        self.active_sse_queues: list[asyncio.Queue[dict[str, Any]]] = []
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

    def register_sse(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self.active_sse_queues.append(queue)
        logger.info(
            "SSE client subscribed. Total SSE subscribers: %d", len(self.active_sse_queues)
        )

    def unregister_sse(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self.active_sse_queues:
            self.active_sse_queues.remove(queue)
            logger.info(
                "SSE client unsubscribed. Total SSE subscribers: %d",
                len(self.active_sse_queues),
            )

    async def broadcast(self, data: dict[str, Any]) -> None:
        """Broadcast JSON payload to all connected WebSocket clients and SSE subscribers."""
        dead_connections: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

        for sse_queue in list(self.active_sse_queues):
            with contextlib.suppress(asyncio.QueueFull):
                sse_queue.put_nowait(data)

    def broadcast_sync(self, data: dict[str, Any]) -> None:
        """Thread-safe sync dispatch callable from background inference threads."""
        if not self.active_connections and not self.active_sse_queues:
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


async def sse_telemetry_generator(
    request: Request | None = None,
) -> AsyncGenerator[ServerSentEvent, None]:
    """Asynchronous generator yielding ServerSentEvent objects for telemetry subscribers."""
    ws_manager.set_loop(asyncio.get_running_loop())
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    ws_manager.register_sse(queue)

    try:
        yield ServerSentEvent(
            data={"type": "handshake", "status": "connected"}, event="telemetry"
        )
        while not (request is not None and await request.is_disconnected()):
            try:
                data = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield ServerSentEvent(data=data, event="telemetry")
            except TimeoutError:
                if request is not None and await request.is_disconnected():
                    break
                yield ServerSentEvent(comment="keepalive")
    finally:
        ws_manager.unregister_sse(queue)


@router.get("/events/telemetry", response_class=EventSourceResponse)
async def sse_telemetry_endpoint(request: Request) -> AsyncGenerator[ServerSentEvent, None]:
    """Server-Sent Events (SSE) stream for real-time telemetry (footfall, dwell, queues, alerts)."""
    async for event in sse_telemetry_generator(request):
        yield event


