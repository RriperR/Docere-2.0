"""Отказы доставки, повторные сообщения и fencing при восстановлении worker."""

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.adapters.queue import import_execution, recover_import_jobs
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.import_dispatch import ImportDispatchRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow

pytestmark = pytest.mark.critical


@pytest.fixture
def delivery_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    url = os.environ.get('DOCERE_TEST_POSTGRES_URL')
    schema = f'test_delivery_{uuid4().hex}'
    admin = create_engine(url) if url else None
    if admin is not None:
        with admin.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
    engine = (
        create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
        if url
        else create_engine(f'sqlite:///{tmp_path / "delivery.sqlite"}')
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(import_execution, 'get_session_factory', lambda: factory)
    monkeypatch.setattr(recover_import_jobs, 'get_session_factory', lambda: factory)
    try:
        yield factory
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            admin.dispose()


def create_job(factory: sessionmaker[Session]) -> UUID:
    with factory() as session:
        user = UserRow(
            id=uuid4(),
            fio='Test',
            email=f'{uuid4()}@example.com',
            phone='+79990000000',
            password_hash='test-only',  # noqa: S106
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        session.flush()
        job = SqlAlchemyImportJobRepositoryAdapter(session).create_job(
            uploaded_by_user_id=user.id,
            original_filename='synthetic.zip',
            archive_storage_key='synthetic/archive',
            size_bytes=123,
            request_id='request-123',
        )
        session.commit()
        return job.id


def test_outbox_is_atomic_with_import(delivery_db: sessionmaker[Session]) -> None:
    job_id = create_job(delivery_db)
    with delivery_db() as session:
        job = session.get(ImportJobRow, job_id)
        assert job is not None
        rolled_back = SqlAlchemyImportJobRepositoryAdapter(session).create_job(
            uploaded_by_user_id=job.uploaded_by_user_id,
            original_filename='rollback.zip',
            archive_storage_key='rollback',
            size_bytes=1,
        )
        session.rollback()
    with delivery_db() as session:
        assert session.get(ImportJobRow, rolled_back.id) is None
        assert session.get(ImportDispatchRow, rolled_back.id) is None
        outbox = session.get(ImportDispatchRow, job_id)
        assert outbox is not None and outbox.request_id == 'request-123'


def test_broker_outage_and_lost_publication_are_retried(
    delivery_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = create_job(delivery_db)
    messages: list[tuple[list[str], dict[str, str | None]]] = []

    class Broker:
        online = False

        @classmethod
        def apply_async(cls, *, args: list[str], kwargs: dict[str, str | None]) -> None:
            if not cls.online:
                raise ConnectionError('offline')
            messages.append((args, kwargs))

    monkeypatch.setattr(recover_import_jobs, 'process_import_job', Broker)
    assert recover_import_jobs.enqueue_recoverable_import_jobs() == 0
    Broker.online = True
    assert recover_import_jobs.enqueue_recoverable_import_jobs() == 0  # Retry backoff.
    for _ in range(2):  # Redis may lose an acknowledged publication before a worker claims it.
        with delivery_db() as session:
            session.execute(update(ImportDispatchRow).values(next_attempt_at=utc_now() - timedelta(seconds=1)))
            session.commit()
        assert recover_import_jobs.enqueue_recoverable_import_jobs() == 1
    assert messages == [([str(job_id)], {'request_id': 'request-123'})] * 2
    assert import_execution.claim_import(job_id, uuid4()) is not None
    with delivery_db() as session:
        session.execute(update(ImportDispatchRow).values(next_attempt_at=utc_now() - timedelta(seconds=1)))
        session.commit()
    assert recover_import_jobs.enqueue_recoverable_import_jobs() == 0  # Active worker is not disturbed.


def test_concurrent_claim_and_completed_job_are_idempotent(delivery_db: sessionmaker[Session]) -> None:
    job_id = create_job(delivery_db)
    tokens = [uuid4(), uuid4()]
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda token: import_execution.claim_import(job_id, token), tokens))
    assert sum(job is not None for job in claims) == 1
    winner = tokens[next(i for i, job in enumerate(claims) if job is not None)]
    report = {'message': 'Ready for review'}
    assert import_execution.finish_import(job_id, winner, ImportJobStatus.NEEDS_REVIEW, report)
    assert import_execution.claim_import(job_id, uuid4()) is None
    assert not import_execution.finish_import(job_id, winner, ImportJobStatus.FAILED, {})
    with delivery_db() as session:
        job = session.get(ImportJobRow, job_id)
        assert job is not None and job.report_json == report and job.version == 3


def test_expired_lease_recovers_and_rejects_stale_result(delivery_db: sessionmaker[Session]) -> None:
    job_id = create_job(delivery_db)
    old_token, new_token = uuid4(), uuid4()
    assert import_execution.claim_import(job_id, old_token)
    recover_import_jobs.recover_expired_imports()
    assert import_execution.claim_import(job_id, new_token) is None
    with delivery_db() as session:
        session.execute(update(ImportJobRow).values(lease_expires_at=utc_now() - timedelta(seconds=1)))
        session.commit()
    recover_import_jobs.recover_expired_imports()
    assert import_execution.claim_import(job_id, new_token)
    assert not import_execution.finish_import(job_id, old_token, ImportJobStatus.FAILED, {})
    assert import_execution.finish_import(job_id, new_token, ImportJobStatus.NEEDS_REVIEW, {'message': 'recovered'})
    with delivery_db() as session:
        assert session.scalar(select(ImportJobRow.version)) == 5


@pytest.mark.skipif(not os.environ.get('DOCERE_TEST_POSTGRES_URL'), reason='Requires isolated PostgreSQL')
def test_dispatchers_skip_locked_rows(delivery_db: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> None:
    ids = {str(create_job(delivery_db)), str(create_job(delivery_db))}
    published: list[str] = []
    barrier = Barrier(2)

    class Broker:
        @staticmethod
        def apply_async(*, args: list[str], kwargs: dict[str, str | None]) -> None:
            published.append(args[0])
            barrier.wait(timeout=5)

    monkeypatch.setattr(recover_import_jobs, 'process_import_job', Broker)
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(pool.map(lambda _: recover_import_jobs.enqueue_recoverable_import_jobs(limit=1), range(2)))
    assert counts == [1, 1]
    assert set(published) == ids


def test_publish_succeeded_but_commit_failed_is_retried(
    delivery_db: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = create_job(delivery_db)
    publications: list[str] = []
    fail_commit = False
    original_commit = Session.commit

    class Broker:
        @staticmethod
        def apply_async(*, args: list[str], kwargs: dict[str, str | None]) -> None:
            nonlocal fail_commit
            publications.append(args[0])
            fail_commit = len(publications) == 1

    def commit(session: Session) -> None:
        nonlocal fail_commit
        if fail_commit:
            fail_commit = False
            raise ConnectionError('database commit lost')
        original_commit(session)

    monkeypatch.setattr(recover_import_jobs, 'process_import_job', Broker)
    monkeypatch.setattr(Session, 'commit', commit)
    with pytest.raises(ConnectionError):
        recover_import_jobs.enqueue_recoverable_import_jobs()
    assert recover_import_jobs.enqueue_recoverable_import_jobs() == 1
    assert publications == [str(job_id), str(job_id)]
    assert import_execution.claim_import(job_id, uuid4()) is not None
    assert import_execution.claim_import(job_id, uuid4()) is None
