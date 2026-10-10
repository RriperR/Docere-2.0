"""Личные формы не раскрывают контекст и не теряются между вкладками."""

from datetime import datetime, timedelta, UTC
from uuid import UUID

import pytest
from sqlalchemy import select
from test_clinical_cases import invite, setup_case

from app.infrastructure.db.models.clinical_cases import CaseWorkDraftRow
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.critical


def test_work_drafts_are_private_versioned_and_revoked_with_case(record_client):
    """Черновик переживает reload, но не выдаётся коллеге или потерявшему доступ врачу."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    url = f'/api/cases/{case["id"]}/work-drafts/message'
    empty = client.get(url, headers=headers[0])
    assert empty.status_code == 200
    assert empty.json()['version'] == 0
    saved = client.put(
        url,
        headers=headers[0],
        json={
            'version': 0,
            'content': {'text': 'Личное незавершённое мнение', 'record_ids': [records[0]['id']]},
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()['version'] == 1
    assert (
        client.put(url, headers=headers[0], json={'version': 0, 'content': {'text': 'Старая вкладка'}}).status_code
        == 409
    )
    assert client.get(url, headers=headers[0]).json()['content']['text'] == 'Личное незавершённое мнение'
    case = invite(client, case, headers, ids[1])
    assert client.get(url, headers=headers[1]).status_code == 403
    assert client.get(url, headers=headers[2]).status_code == 404
    base = f'/api/cases/{case["id"]}'
    assert client.post(base + '/invitations/accept', headers=headers[1]).status_code == 200
    assert client.get(url, headers=headers[1]).json()['content']['text'] == ''
    assert client.get(base + '/work-drafts/conclusion', headers=headers[1]).status_code == 403
    peer = client.put(url, headers=headers[1], json={'version': 0, 'content': {'text': 'Мой черновик'}})
    assert peer.status_code == 200
    assert client.post(base + '/leave', headers=headers[1]).status_code == 200
    assert client.get(url, headers=headers[1]).status_code == 404
    # Независимое право на записи не открывает личные формы или контекст без членства.
    assert client.get(url, headers=headers[0]).json()['content']['text'] == 'Личное незавершённое мнение'


def test_work_drafts_expire_validate_materials_and_cannot_change_closed_case(record_client):
    """TTL, ссылки другого пациента и закрытие проверяются на сервере."""
    client = record_client
    case, records, _, headers, _ = setup_case(client)
    base = f'/api/cases/{case["id"]}'
    url = base + '/work-drafts/conclusion'
    assert (
        client.put(
            url,
            headers=headers[0],
            json={
                'version': 0,
                'content': {'text': 'Незавершённый итог', 'record_ids': [records[1]['id']]},
            },
        ).status_code
        == 404
    )
    assert (
        client.put(url, headers=headers[0], json={'version': 0, 'content': {'text': 'Личный итог'}}).status_code == 200
    )
    with get_session_factory()() as session:
        row = session.scalar(select(CaseWorkDraftRow).where(CaseWorkDraftRow.case_id == UUID(case['id'])))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert client.get(url, headers=headers[0]).json()['version'] == 0
    with get_session_factory()() as session:
        assert session.scalar(select(CaseWorkDraftRow)) is None
    assert (
        client.post(
            base + '/conclusions',
            headers=headers[0],
            json={
                'version': case['case']['version'],
                'summary': 'Итог',
                'source_ids': [],
            },
        ).status_code
        == 201
    )
    current = client.get(base, headers=headers[0]).json()['case']
    assert client.post(base + '/close', headers=headers[0], json={'version': current['version']}).status_code == 200
    assert (
        client.put(url, headers=headers[0], json={'version': 0, 'content': {'text': 'Поздний текст'}}).status_code
        == 409
    )


def test_message_consumes_private_form_atomically(record_client):
    """Опубликованное сообщение очищает черновик и не сбрасывает счётчик версий."""
    from uuid import uuid4

    client = record_client
    case, _, _, headers, _ = setup_case(client)
    base = f'/api/cases/{case["id"]}'
    key = str(uuid4())
    url = base + '/work-drafts/message'
    assert (
        client.put(
            url,
            headers=headers[0],
            json={
                'version': 0,
                'content': {'text': 'Сообщение', 'idempotency_key': key},
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            base + '/messages',
            headers=headers[0],
            json={
                'body': 'Сообщение',
                'idempotency_key': key,
            },
        ).status_code
        == 201
    )
    cleared = client.get(url, headers=headers[0]).json()
    assert cleared['content']['text'] == ''
    assert cleared['version'] == 2
    assert (
        client.put(
            url,
            headers=headers[0],
            json={
                'version': 1,
                'content': {'text': 'Устаревший текст'},
            },
        ).status_code
        == 409
    )


def test_concurrent_work_draft_writes_keep_one_version(postgres_case_client):
    """PostgreSQL сериализует два сохранения одной версии под блокировкой случая."""
    from concurrent.futures import ThreadPoolExecutor

    client = postgres_case_client
    case, _, _, headers, _ = setup_case(client)
    url = f'/api/cases/{case["id"]}/work-drafts/message'

    def save(text):
        return client.put(url, headers=headers[0], json={'version': 0, 'content': {'text': text}})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(save, ['Первая вкладка', 'Вторая вкладка']))
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json()['content']['text'] for response in responses if response.status_code == 200)
    assert client.get(url, headers=headers[0]).json()['content']['text'] == winner


def test_private_form_is_hidden_after_losing_one_material(record_client):
    """Доступ к личному тексту требует всех исходных материалов, даже при действующем членстве."""
    from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    url = f'/api/cases/{case["id"]}/work-drafts/message'
    assert (
        client.put(
            url, headers=headers[0], json={'version': 0, 'content': {'text': 'Сведения из документа'}}
        ).status_code
        == 200
    )
    with get_session_factory()() as session:
        links = session.scalars(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == ids[0],
                UserRecordLinkRow.record_id == UUID(records[0]['id']),
            )
        ).all()
        for link in links:
            session.delete(link)
        session.commit()
    assert client.get(url, headers=headers[0]).status_code == 403
    assert (
        client.put(url, headers=headers[0], json={'version': 1, 'content': {'text': 'Дополнение'}}).status_code == 403
    )
