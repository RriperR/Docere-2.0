"""Жизненный цикл SSE без удержания ресурсов и раскрытия медицинского отчёта."""

from typing import cast
from uuid import uuid4

import pytest
from fastapi import Request

from app.application.use_cases.auth.errors import InvalidTokenError
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError
from app.domain.entities.import_job import ImportJobProgress, ImportJobStatus
from app.presentation.main import create_app  # noqa: F401
from app.presentation.rest.public.v1.archives import events

pytestmark = [pytest.mark.critical, pytest.mark.asyncio]


class RequestStub:
    disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.parametrize(
    'error,event', [(InvalidTokenError, 'auth-expired'), (ImportJobNotFoundError, 'access-revoked')]
)
async def test_stream_rechecks_permissions(monkeypatch: pytest.MonkeyPatch, error: type[Exception], event: str) -> None:
    job = ImportJobProgress(uuid4(), ImportJobStatus.RUNNING, 2)

    def read(*args: object) -> ImportJobProgress:
        raise error

    monkeypatch.setattr(events, 'POLL_SECONDS', 0)
    monkeypatch.setattr(events, 'read_progress', read)
    frames = [frame async for frame in events.progress_events(cast(Request, RequestStub()), 'token', job.id, job, 0)]
    assert len(frames) == 2
    assert f'event: {event}' in frames[-1]


async def test_disconnect_stops_reads_and_heartbeat_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    request = RequestStub()
    job = ImportJobProgress(uuid4(), ImportJobStatus.RUNNING, 2)
    monkeypatch.setattr(events, 'HEARTBEAT_SECONDS', 0)
    stream = events.progress_events(cast(Request, request), 'token', job.id, job, 2)
    assert await anext(stream) == ': heartbeat\n\n'
    await stream.aclose()
    request.disconnected = True
    assert [frame async for frame in events.progress_events(cast(Request, request), 'token', job.id, job, 0)] == []
