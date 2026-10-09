"""ARQ worker: `arq app.workers.main.WorkerSettings`."""

import logging
from typing import Any

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.enums import IncidentStatus
from app.services.dispatch_service import DispatchService
from app.services.incident_service import IncidentService
from app.services.realtime import RedisPublisher
from app.workers.queue import ArqJobQueue

logger = logging.getLogger(__name__)


async def escalate_unaccepted_sos(ctx: dict[str, Any], incident_id: int, officer_id: int) -> str:
    """BR Lifecycle 11: SOS not accepted in time -> next-nearest reachable officer."""
    async with ctx["sessionmaker"]() as session:
        incident = await DispatchService(session).escalate(incident_id, officer_id)
        if incident is None:
            return "noop"  # accepted, cancelled or reassigned in the meantime
        await IncidentService(session, RedisPublisher(ctx["redis"])).publish_status(incident)
        if incident.status == IncidentStatus.ASSIGNED and incident.officer_id is not None:
            await ArqJobQueue(ctx["redis"]).schedule_escalation(incident.id, incident.officer_id)
        logger.info("Escalated incident %s -> %s", incident_id, incident.status)
        return incident.status.value


async def startup(ctx: dict[str, Any]) -> None:
    ctx["engine"] = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    ctx["sessionmaker"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["engine"].dispose()


class WorkerSettings:
    functions = [escalate_unaccepted_sos]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
