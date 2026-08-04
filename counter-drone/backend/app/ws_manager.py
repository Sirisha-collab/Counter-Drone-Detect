
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)
        log.info("Client connected (%d total)", len(self.connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)
        log.info("Client disconnected (%d remaining)", len(self.connections))

    async def send_to(self, websocket: WebSocket, payload: str) -> None:
        await websocket.send_text(payload)

    async def broadcast(self, payload: str) -> None:
        dead: list[WebSocket] = []
        for connection in list(self.connections):
            try:
                await connection.send_text(payload)
            except Exception:
                dead.append(connection)
        for connection in dead:
            self.disconnect(connection)

    @property
    def count(self) -> int:
        return len(self.connections)


manager = ConnectionManager()
