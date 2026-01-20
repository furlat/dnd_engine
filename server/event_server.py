"""
WebSocket server for broadcasting game events.

This server:
1. Hooks into EventQueue to capture all events
2. Broadcasts events to connected WebSocket clients
3. Supports filtering by event type

Usage:
    # Start server
    python -m server.event_server

    # Or import and run programmatically
    from server.event_server import run_server
    run_server(host="0.0.0.0", port=8000)
"""

import asyncio
import json
from typing import Set, Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

from dnd.core.events import Event, EventQueue, EventType, EventPhase


class EventMonitor:
    """
    Monitors EventQueue and broadcasts events to listeners.

    Uses EventQueue's on_event_callback system to receive ALL events
    regardless of phase, then broadcasts them to connected listeners.
    """

    def __init__(self):
        self._listeners: Set[asyncio.Queue] = set()
        self._running = False

    def add_listener(self, queue: asyncio.Queue) -> None:
        """Add a listener queue that will receive events."""
        self._listeners.add(queue)

    def remove_listener(self, queue: asyncio.Queue) -> None:
        """Remove a listener queue."""
        self._listeners.discard(queue)

    @property
    def listener_count(self) -> int:
        """Number of active listeners."""
        return len(self._listeners)

    def _on_event(self, event: Event) -> None:
        """Callback invoked for every event in EventQueue."""
        if not self._listeners:
            return

        # Serialize event to JSON-compatible dict
        try:
            event_data = event.model_dump(mode='json')
            for queue in self._listeners:
                try:
                    queue.put_nowait(event_data)
                except asyncio.QueueFull:
                    pass  # Drop event if queue is full
        except Exception as e:
            print(f"Error serializing event: {e}")

    def start(self) -> None:
        """Start monitoring events."""
        if self._running:
            return

        EventQueue.add_on_event_callback(self._on_event)
        self._running = True
        print("EventMonitor started")

    def stop(self) -> None:
        """Stop monitoring events."""
        if not self._running:
            return

        EventQueue.remove_on_event_callback(self._on_event)
        self._running = False
        print("EventMonitor stopped")


# Global event monitor instance
event_monitor = EventMonitor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for FastAPI app."""
    # Startup
    event_monitor.start()
    yield
    # Shutdown
    event_monitor.stop()


# Create FastAPI app
app = FastAPI(
    title="D&D Engine Event Server",
    description="WebSocket server for real-time game events",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "listeners": event_monitor.listener_count,
        "event_count": len(EventQueue._all_events)
    }


@app.get("/events")
async def get_events(
    limit: int = 50,
    event_type: Optional[str] = None,
    phase: Optional[str] = None
):
    """Get recent events from the queue."""
    events = EventQueue._all_events[-limit:]

    # Filter by type if specified
    if event_type:
        try:
            et = EventType(event_type)
            events = [e for e in events if e.event_type == et]
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown event_type: {event_type}"}
            )

    # Filter by phase if specified
    if phase:
        try:
            ep = EventPhase(phase)
            events = [e for e in events if e.phase == ep]
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown phase: {phase}"}
            )

    return {
        "count": len(events),
        "events": [e.model_dump(mode='json') for e in events]
    }


@app.get("/event-types")
async def get_event_types():
    """List all available event types."""
    return {
        "event_types": [et.value for et in EventType],
        "phases": [ep.value for ep in EventPhase]
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event streaming.

    Connect and receive events as JSON messages.
    Send {"type": "ping"} to check connection.
    Send {"type": "filter", "event_types": ["attack", "movement"]} to filter events.
    """
    await websocket.accept()

    # Create a queue for this connection
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    event_monitor.add_listener(queue)

    # Optional event type filter
    event_type_filter: Optional[Set[str]] = None

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to D&D Engine Event Server",
            "event_count": len(EventQueue._all_events)
        })

        # Handle both receiving commands and sending events
        async def receive_commands():
            nonlocal event_type_filter
            while True:
                try:
                    data = await websocket.receive_json()
                    msg_type = data.get("type", "")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif msg_type == "filter":
                        # Set event type filter
                        types = data.get("event_types")
                        if types:
                            event_type_filter = set(types)
                            await websocket.send_json({
                                "type": "filter_set",
                                "event_types": list(event_type_filter)
                            })
                        else:
                            event_type_filter = None
                            await websocket.send_json({
                                "type": "filter_cleared"
                            })

                    elif msg_type == "get_history":
                        # Send recent events
                        limit = data.get("limit", 50)
                        events = EventQueue._all_events[-limit:]
                        for event in events:
                            event_data = event.model_dump(mode='json')
                            if event_type_filter is None or event_data.get("event_type") in event_type_filter:
                                await websocket.send_json({
                                    "type": "event",
                                    "event": event_data
                                })

                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"Error receiving command: {e}")
                    break

        async def send_events():
            while True:
                try:
                    event_data = await queue.get()

                    # Apply filter if set
                    if event_type_filter is not None:
                        if event_data.get("event_type") not in event_type_filter:
                            continue

                    await websocket.send_json({
                        "type": "event",
                        "event": event_data
                    })
                except Exception as e:
                    print(f"Error sending event: {e}")
                    break

        # Run both tasks concurrently
        receive_task = asyncio.create_task(receive_commands())
        send_task = asyncio.create_task(send_events())

        # Wait for either task to complete (disconnect)
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

    except WebSocketDisconnect:
        pass
    finally:
        event_monitor.remove_listener(queue)
        print(f"WebSocket client disconnected. Active listeners: {event_monitor.listener_count}")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the event server."""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
