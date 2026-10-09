import time
from datetime import timedelta
from typing import Protocol

from arq.connections import ArqRedis

from app.core.config import get_settings


class JobQueue(Protocol):
    async def schedule_escalation(self, incident_id: int, officer_id: int) -> None: ...


class ArqJobQueue:
    def __init__(self, arq: ArqRedis):
        self.arq = arq

    async def schedule_escalation(self, incident_id: int, officer_id: int) -> None:
        """Check back after the accept timeout; the job is a no-op if the officer accepted."""
        await self.arq.enqueue_job(
            "escalate_unaccepted_sos",
            incident_id,
            officer_id,
            _defer_by=timedelta(seconds=get_settings().sos_accept_timeout_seconds),
            # Unique per assignment (arq ignores a duplicate job id while the old one is kept).
            _job_id=f"escalate:{incident_id}:{officer_id}:{time.time_ns()}",
        )


class NullJobQueue:
    async def schedule_escalation(self, incident_id: int, officer_id: int) -> None:
        return None
