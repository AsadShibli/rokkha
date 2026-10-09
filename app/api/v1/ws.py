import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.api.deps import DbSession
from app.core.exceptions import InvalidTokenError
from app.core.security import decode_token
from app.models.enums import UserRole
from app.repositories.incident_repository import IncidentRepository
from app.repositories.officer_repository import OfficerRepository
from app.repositories.user_repository import UserRepository
from app.schemas.incident import IncidentOut
from app.services.realtime import incident_channel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

# Application close codes (4000-4999): mirror HTTP 401 / 404.
CLOSE_UNAUTHORIZED = 4401
CLOSE_NOT_FOUND = 4404


@router.websocket("/ws/incidents/{incident_id}")
async def incident_feed(
    websocket: WebSocket,
    incident_id: int,
    db: DbSession,
    token: Annotated[str, Query(description="Access token (browsers can't set WS headers)")],
) -> None:
    """Live status and officer location for one incident (owner or assigned officer).

    Server sends `snapshot` once, then `status` / `location` messages. The client may only
    send "ping" (answered with "pong"); anything else closes the socket.
    """
    # --- authenticate and authorize BEFORE accepting the socket ---
    try:
        claims = decode_token(token, "access")
    except InvalidTokenError:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return
    user = await UserRepository(db).get(claims.user_id)
    if user is None or not user.is_active:
        await websocket.close(code=CLOSE_UNAUTHORIZED)
        return
    incident = await IncidentRepository(db).get_with_events(incident_id)
    allowed = False
    if incident is not None:
        if user.role == UserRole.CITIZEN:
            allowed = incident.citizen_id == user.id
        elif user.role == UserRole.OFFICER:
            officer = await OfficerRepository(db).get_by_user_id(user.id)
            allowed = officer is not None and incident.officer_id == officer.id
    if not allowed:
        await websocket.close(code=CLOSE_NOT_FOUND)
        return
    snapshot = IncidentOut.from_incident(incident).model_dump(mode="json")
    # Release the DB connection now; a socket can stay open for a long time.
    await db.close()

    redis = getattr(websocket.app.state, "redis", None)
    if redis is None:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    await websocket.accept()
    await websocket.send_json({"type": "snapshot", "incident": snapshot})

    pubsub = redis.pubsub()
    await pubsub.subscribe(incident_channel(incident_id))
    forward = asyncio.create_task(_forward_updates(websocket, pubsub))
    listen = asyncio.create_task(_answer_pings(websocket))
    try:
        await asyncio.wait({forward, listen}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (forward, listen):
            task.cancel()
        await pubsub.unsubscribe()
        await pubsub.aclose()


async def _forward_updates(websocket: WebSocket, pubsub) -> None:
    async for message in pubsub.listen():
        if message["type"] == "message":
            await websocket.send_text(message["data"])


async def _answer_pings(websocket: WebSocket) -> None:
    try:
        while True:
            text = await websocket.receive_text()
            if text != "ping":
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            await websocket.send_text("pong")
    except WebSocketDisconnect:
        return
