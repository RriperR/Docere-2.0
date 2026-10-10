"""Прямые API-проверки изоляции и происхождения прав клинических случаев."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_records import (
    _create_doctor,
    _create_record,
    _get_patient_passport_id_by_email,
    _get_user_by_email,
    _grant_record_access,
    _login,
    _register_patient,
    TEST_DOCTOR_PASSWORD,
    TEST_PATIENT_PASSWORD,
)

from app.infrastructure.db.models.auth.user import UserRow, UserStatus
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.critical


def setup_case(client):
    """Создать пациента, три врача и три записи в изолированной БД."""
    _register_patient(client, 'patient@cases.example.com')
    patient = _get_patient_passport_id_by_email('patient@cases.example.com')
    tokens, ids = [], []
    for name in ['owner', 'peer', 'outsider']:
        email = f'{name}@cases.example.com'
        _create_doctor(email)
        tokens.append(_login(client, email, TEST_DOCTOR_PASSWORD))
        ids.append(_get_user_by_email(email).id)
    pt = _login(client, 'patient@cases.example.com', TEST_PATIENT_PASSWORD)
    records = [
        _create_record(client, pt, patient, author_practitioner_full_name='Doctor', title=f'Private {i}')
        for i in range(3)
    ]
    for record in records:
        _grant_record_access(ids[0], UUID(record['id']), patient)
    headers = [{'Authorization': f'Bearer {token}'} for token in tokens]
    response = client.post(
        '/api/cases',
        headers=headers[0],
        json={
            'patient_id': str(patient),
            'title': 'Secret clinical case',
            'question': 'Secret question',
            'record_ids': [records[0]['id']],
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), records, ids, headers, patient


def invite(client, view, headers, target):
    """Отправить приглашение от координатора и вернуть обновлённую карточку."""
    response = client.post(
        f'/api/cases/{view["id"]}/invitations',
        headers=headers[0],
        json={'version': view['case']['version'], 'user_id': str(target)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_pending_invitation_never_exposes_clinical_context(record_client):
    """Непринятое приглашение скрывает контекст и не открывает остальные записи пациента."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    pending = client.get(url, headers=headers[1])
    assert pending.status_code == 200
    assert pending.json()['case'] is None
    assert 'Secret' not in pending.text
    assert client.get(url, headers=headers[2]).status_code == 404
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[1]).status_code in {403, 404}
    assert client.post(url + '/invitations/accept', headers=headers[1]).json()['accessible']
    assert client.post(url + '/invitations/accept', headers=headers[1]).status_code == 200
    assert client.get(f'/api/records/{records[1]["id"]}', headers=headers[1]).status_code in {403, 404}
    with get_session_factory()() as session:
        link = session.scalar(select(UserRecordLinkRow).where(UserRecordLinkRow.user_id == ids[1]))
        share_id = link.source_record_share_id
        from app.infrastructure.db.models.medical_records.record_share import RecordShareRow

        request_id = session.get(RecordShareRow, share_id).request_id
    assert client.get('/api/share-requests/inbox', headers=headers[1]).json() == []
    assert client.post(f'/api/share-requests/{request_id}/accept', headers=headers[1]).status_code == 404
    assert client.post(f'/api/share-requests/{request_id}/revoke', headers=headers[0]).status_code == 404


def test_leave_preserves_independent_access_and_removes_only_case_grants(record_client):
    """Выход отзывает только источник случая, сохраняя независимый доступ."""
    client = record_client
    case, records, ids, headers, patient = setup_case(client)
    _grant_record_access(ids[1], UUID(records[0]['id']), patient)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    assert client.post(url + '/invitations/accept', headers=headers[1]).status_code == 200
    version = client.get(url, headers=headers[0]).json()['case']['version']
    assert (
        client.post(
            url + '/materials', headers=headers[0], json={'version': version, 'record_ids': [records[1]['id']]}
        ).status_code
        == 200
    )
    assert (
        client.post(
            url + '/materials', headers=headers[0], json={'version': version, 'record_ids': [records[2]['id']]}
        ).status_code
        == 409
    )
    assert client.get(f'/api/records/{records[1]["id"]}', headers=headers[1]).status_code == 200
    assert client.post(url + '/leave', headers=headers[1]).status_code == 200
    assert client.get(url, headers=headers[1]).status_code == 404
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[1]).status_code == 200
    assert client.get(f'/api/records/{records[1]["id"]}', headers=headers[1]).status_code in {403, 404}


def test_loss_of_any_material_hides_entire_context(record_client):
    """Потеря любого материала скрывает весь разбор, включая сообщения и итог."""
    client = record_client
    case, _, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    with get_session_factory()() as session:
        link = session.scalar(select(UserRecordLinkRow).where(UserRecordLinkRow.user_id == ids[1]))
        session.delete(link)
        session.commit()
    view = client.get(url, headers=headers[1])
    assert view.status_code == 200
    assert view.json()['case'] is None
    assert 'Secret' not in view.text


def test_blocked_coordinator_invalidates_case_acl(record_client):
    """Блокировка координатора прекращает действие прав, выданных случаем."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    with get_session_factory()() as session:
        session.get(UserRow, ids[0]).status = UserStatus.BLOCKED
        session.commit()
    assert client.get(url, headers=headers[1]).json()['case'] is None
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[1]).status_code in {403, 404}


def test_discussion_idempotency_one_reply_level_and_context_gate(record_client):
    from uuid import uuid4

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    for path in ['messages', 'opinions', 'activity']:
        assert client.get(url + '/' + path, headers=headers[1]).status_code == 403
        assert client.get(url + '/' + path, headers=headers[2]).status_code == 404
    client.post(url + '/invitations/accept', headers=headers[1])
    payload = {'body': 'Review this material', 'idempotency_key': str(uuid4()), 'record_id': records[0]['id']}
    original = client.post(url + '/messages', headers=headers[0], json=payload)
    assert original.status_code == 201, original.text
    repeated = client.post(url + '/messages', headers=headers[0], json=payload)
    assert repeated.json()['id'] == original.json()['id']
    assert client.post(url + '/messages', headers=headers[0], json={**payload, 'body': 'Different'}).status_code == 409
    reply = client.post(
        url + '/messages',
        headers=headers[1],
        json={'body': 'Reply', 'idempotency_key': str(uuid4()), 'parent_id': original.json()['id']},
    )
    assert reply.status_code == 201
    assert (
        client.post(
            url + '/messages',
            headers=headers[1],
            json={'body': 'Too deep', 'idempotency_key': str(uuid4()), 'parent_id': reply.json()['id']},
        ).status_code
        == 422
    )
    assert (
        client.post(
            url + '/messages',
            headers=headers[1],
            json={'body': 'Wrong record', 'idempotency_key': str(uuid4()), 'record_id': records[1]['id']},
        ).status_code
        == 404
    )
    page = client.get(url + '/messages?limit=1', headers=headers[1]).json()
    assert page['total'] == 2 and len(page['items']) == 1
    with get_session_factory()() as session:
        link = session.scalar(select(UserRecordLinkRow).where(UserRecordLinkRow.user_id == ids[1]))
        session.delete(link)
        session.commit()
    assert client.get(url + '/messages', headers=headers[1]).status_code == 403


def test_opinion_answer_permissions_and_leaving_cancels_open_requests(record_client):
    from uuid import uuid4

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    response = client.post(
        url + '/opinions',
        headers=headers[0],
        json={'assignee_id': str(ids[1]), 'question': 'Please review', 'record_id': records[0]['id']},
    )
    assert response.status_code == 201, response.text
    opinion = response.json()
    answer = {'body': 'Opinion', 'idempotency_key': str(uuid4()), 'opinion_id': opinion['id']}
    assert client.post(url + '/messages', headers=headers[0], json=answer).status_code == 403
    assert client.post(url + '/messages', headers=headers[1], json=answer).status_code == 201
    assert client.get(url + '/opinions', headers=headers[0]).json()['items'][0]['status'] == 'answered'
    response = client.post(
        url + '/opinions', headers=headers[0], json={'assignee_id': str(ids[1]), 'question': 'One more question'}
    )
    assert response.status_code == 201
    client.post(url + '/leave', headers=headers[1])
    cancelled = next(
        item
        for item in client.get(url + '/opinions', headers=headers[0]).json()['items']
        if item['id'] == response.json()['id']
    )
    assert cancelled['status'] == 'cancelled' and cancelled['reason'] == 'assignee_left'


def test_acceptance_uses_latest_materials(record_client):
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    assert (
        client.post(
            url + '/materials',
            headers=headers[0],
            json={'version': case['case']['version'], 'record_ids': [records[1]['id'], records[1]['id']]},
        ).status_code
        == 200
    )
    accepted = client.post(url + '/invitations/accept', headers=headers[1]).json()
    assert len(accepted['case']['record_ids']) == 2
    assert client.get(f'/api/records/{records[1]["id"]}', headers=headers[1]).status_code == 200


def test_conclusion_close_and_idempotent_publication(record_client):
    from uuid import uuid4

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    view = client.get(url, headers=headers[0]).json()
    case = invite(client, view, headers, ids[2])
    payload = {
        'version': case['case']['version'],
        'summary': 'Case discussion result',
        'findings': 'Findings',
        'next_actions': 'Follow up',
        'source_ids': [records[0]['id']],
    }
    assert client.post(url + '/conclusions', headers=headers[1], json=payload).status_code == 403
    assert client.get(url + '/conclusions', headers=headers[2]).status_code == 403
    assert client.post(url + '/conclusions', headers=headers[0], json=payload).status_code == 201
    assert client.post(url + '/conclusions', headers=headers[0], json=payload).status_code == 409
    opinion = client.post(
        url + '/opinions', headers=headers[0], json={'assignee_id': str(ids[1]), 'question': 'Pending question'}
    )
    assert opinion.status_code == 201
    version = client.get(url, headers=headers[0]).json()['case']['version']
    assert client.post(url + '/close', headers=headers[0], json={'version': version}).status_code == 409
    closed = client.post(url + '/close', headers=headers[0], json={'version': version, 'cancel_open_requests': True})
    assert closed.status_code == 200, closed.text
    assert client.get(url, headers=headers[1]).json()['accessible']
    assert client.get(url, headers=headers[2]).status_code == 404
    assert (
        client.post(
            url + '/messages', headers=headers[1], json={'body': 'Late', 'idempotency_key': str(uuid4())}
        ).status_code
        == 409
    )
    assert (
        client.post(
            url + '/conclusions', headers=headers[0], json={**payload, 'version': closed.json()['case']['version']}
        ).status_code
        == 409
    )
    assert client.post(url + '/publish', headers=headers[1], json={'event_date': '2026-01-10'}).status_code == 403
    first = client.post(url + '/publish', headers=headers[0], json={'event_date': '2026-01-10'})
    assert first.status_code == 200, first.text
    second = client.post(url + '/publish', headers=headers[0], json={'event_date': '2026-02-10'})
    assert first.json()['record_id'] == second.json()['record_id']
    assert second.json()['created'] is False
    record_id = first.json()['record_id']
    record = client.get(f'/api/records/{record_id}', headers=headers[0]).json()
    assert record['event_date'] == '2026-01-10' and record['status'] == 'unconfirmed'
    assert record['payload_json']['case_provenance']['case_id'] == case['id']
    assert record['payload_json']['case_provenance']['conclusion_version'] == 1
    assert client.get(f'/api/records/{record_id}', headers=headers[1]).status_code in {403, 404}
    with get_session_factory()() as session:
        link = session.scalar(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == ids[0], UserRecordLinkRow.record_id == UUID(records[0]['id'])
            )
        )
        session.delete(link)
        session.commit()
    assert client.get(url, headers=headers[0]).json()['case'] is None
    assert client.get(f'/api/records/{record_id}', headers=headers[0]).status_code == 200
    assert client.post(url + '/publish', headers=headers[0], json={'event_date': '2026-01-10'}).status_code == 403


def test_empty_result_cannot_close_case(record_client):
    client = record_client
    case, _, _, headers, _ = setup_case(client)
    assert (
        client.post(
            f'/api/cases/{case["id"]}/close', headers=headers[0], json={'version': case['case']['version']}
        ).status_code
        == 422
    )


def test_postgres_concurrent_versions_and_publication(postgres_case_client):
    from concurrent.futures import ThreadPoolExecutor

    client = postgres_case_client
    case, records, _, headers, _ = setup_case(client)
    url = f'/api/cases/{case["id"]}'
    version = case['case']['version']

    def add(record):
        return client.post(
            url + '/materials', headers=headers[0], json={'version': version, 'record_ids': [record['id']]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(add, records[1:]))
    assert sorted(r.status_code for r in results) == [200, 409]
    version = client.get(url, headers=headers[0]).json()['case']['version']
    assert (
        client.post(
            url + '/conclusions', headers=headers[0], json={'version': version, 'summary': 'Final result'}
        ).status_code
        == 201
    )
    version = client.get(url, headers=headers[0]).json()['case']['version']

    def close_or_append(action):
        if action == 'close':
            return client.post(url + '/close', headers=headers[0], json={'version': version})
        return client.post(
            url + '/materials', headers=headers[0], json={'version': version, 'record_ids': [records[0]['id']]}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(close_or_append, ['close', 'append']))
    assert sorted(r.status_code for r in results) == [200, 409]
    latest = client.get(url, headers=headers[0]).json()['case']
    if latest['status'] != 'closed':
        assert client.post(url + '/close', headers=headers[0], json={'version': latest['version']}).status_code == 200

    def publish(_):
        return client.post(url + '/publish', headers=headers[0], json={'event_date': '2026-02-20'})

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(publish, range(4)))
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()['record_id'] for r in results}) == 1
    assert sum(r.json()['created'] for r in results) == 1


def test_case_search_preview_and_attachment_association(record_client, monkeypatch):
    from test_records import _InMemoryStorage

    from app.domain.entities.file_attachment import FileAttachmentCategory
    from app.infrastructure.db.models.medical_records.file_attachment import FileAttachmentRow

    client = record_client
    case, records, ids, headers, patient = setup_case(client)
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.records.dependencies.get_file_storage', lambda: storage)
    files = []
    for index, record in enumerate(records[:2]):
        key = f'case-test-{index}.pdf'
        content = b'%PDF-1.4\nsynthetic-document'
        storage.upload(key=key, content=content, content_type='application/pdf')
        with get_session_factory()() as session:
            file = FileAttachmentRow(
                record_id=UUID(record['id']),
                uploaded_by_user_id=ids[0],
                category=FileAttachmentCategory.DOCUMENT,
                filename=f'unique-filename-{index}.pdf',
                storage_key=key,
                mime_type='application/pdf',
                size_bytes=len(content),
            )
            session.add(file)
            session.commit()
            files.append(str(file.id))
    _grant_record_access(ids[1], UUID(records[0]['id']), patient)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    file_url = url + f'/materials/{records[0]["id"]}/attachments/{files[0]}'
    assert client.get(file_url, headers=headers[1]).status_code == 403
    client.post(url + '/invitations/accept', headers=headers[1])
    response = client.get(file_url, headers=headers[1])
    assert response.status_code == 200
    assert response.content.startswith(b'%PDF-')
    assert response.headers['content-disposition'].startswith('inline')
    assert 'no-store' in response.headers['cache-control']
    assert (
        client.get(file_url + '?download=true', headers=headers[1])
        .headers['content-disposition']
        .startswith('attachment')
    )
    assert (
        client.get(url + f'/materials/{records[0]["id"]}/attachments/{files[1]}', headers=headers[1]).status_code == 404
    )
    assert client.get(f'/api/records/{records[0]["id"]}/attachments/{files[1]}', headers=headers[0]).status_code == 404
    search = client.get(url + '/materials?query=unique-filename', headers=headers[1]).json()
    assert search['total'] == 1 and search['items'][0]['id'] == records[0]['id']
    assert client.get(url + '/materials?status=confirmed', headers=headers[1]).json()['total'] == 0
    assert client.get(url + '/materials?date_from=2099-01-01', headers=headers[1]).json()['total'] == 0
    assert client.get(url + '/materials?record_type=exam_result', headers=headers[1]).json()['total'] == 0
    client.post(url + '/leave', headers=headers[1])
    assert client.get(file_url, headers=headers[1]).status_code == 404
    assert client.get(f'/api/records/{records[0]["id"]}/attachments/{files[0]}', headers=headers[1]).status_code == 200


def test_new_material_does_not_restore_revoked_old_case_rights(record_client):
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    accepted = client.post(url + '/invitations/accept', headers=headers[1]).json()
    with get_session_factory()() as session:
        link = session.scalar(select(UserRecordLinkRow).where(UserRecordLinkRow.user_id == ids[1]))
        session.delete(link)
        session.commit()
    added = client.post(
        url + '/materials',
        headers=headers[0],
        json={'version': accepted['case']['version'], 'record_ids': [records[1]['id']]},
    )
    assert added.status_code == 200
    assert client.get(url, headers=headers[1]).json()['case'] is None
    assert client.get(url + '/materials', headers=headers[1]).status_code == 403


def deliver_case_events():
    from app.infrastructure.adapters.queue.case_events import process_case_event
    from app.infrastructure.db.models.clinical_cases import CaseEventRow

    with get_session_factory()() as session:
        events = list(session.scalars(select(CaseEventRow.id)))
    for event_id in events:
        process_case_event(str(event_id))
        process_case_event(str(event_id))


def test_outbox_survives_broker_outage_and_deduplicates_notifications(record_client, monkeypatch):
    from app.infrastructure.adapters.queue.case_events import enqueue_case_events, process_case_event
    from app.infrastructure.db.models._time import utc_now
    from app.infrastructure.db.models.clinical_cases import CaseEventRow

    client = record_client
    case, _, ids, headers, _ = setup_case(client)

    def fail(**_):
        raise RuntimeError('broker unavailable')

    monkeypatch.setattr(process_case_event, 'apply_async', fail)
    case = invite(client, case, headers, ids[1])
    assert enqueue_case_events() == 0
    assert client.get(f'/api/cases/{case["id"]}', headers=headers[0]).json()['case']['status'] == 'active'
    assert client.get('/api/notifications/count', headers=headers[1]).json()['unread'] == 0
    queued = []
    monkeypatch.setattr(process_case_event, 'apply_async', lambda **kwargs: queued.append(kwargs['args'][0]))
    with get_session_factory()() as session:
        for row in session.scalars(select(CaseEventRow)):
            row.next_attempt_at = utc_now()
            assert row.delivered_at is None
        session.commit()
    assert enqueue_case_events() == len(queued) and queued
    for event_id in queued:
        process_case_event(event_id)
        process_case_event(event_id)
    assert client.get('/api/notifications/count', headers=headers[1]).json()['unread'] == 1
    notifications = client.get('/api/notifications', headers=headers[1])
    assert 'Secret' not in notifications.text and notifications.json()['total'] == 1
    assert client.get('/api/notifications?unread_only=true', headers=headers[1]).json()['total'] == 1
    notification_id = notifications.json()['items'][0]['id']
    assert client.post(f'/api/notifications/{notification_id}/read', headers=headers[2]).status_code == 404
    assert client.post('/api/notifications/read-all', headers=headers[1]).status_code == 200
    assert client.get('/api/notifications?unread_only=true', headers=headers[1]).json()['total'] == 0
    assert client.get('/api/notifications', headers=headers[1]).json()['total'] == 1
    assert client.get(f'/api/cases/{case["id"]}', headers=headers[1]).json()['membership_status'] == 'pending'
    assert client.get('/api/notifications/attention', headers=headers[1]).json()['total'] == 1


def test_messages_use_unread_positions_without_notification_fanout(record_client):
    from uuid import uuid4

    client = record_client
    case, _, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    deliver_case_events()
    initial_count = client.get('/api/notifications/count', headers=headers[1]).json()['unread']
    original = client.post(
        url + '/messages', headers=headers[0], json={'body': 'A message', 'idempotency_key': str(uuid4())}
    ).json()
    deliver_case_events()
    assert client.get('/api/notifications/count', headers=headers[1]).json()['unread'] == initial_count
    assert client.get(url, headers=headers[1]).json()['unread_messages'] == 1
    assert client.post(url + '/discussion/read', headers=headers[1], json={'sequence': 999999}).status_code == 200
    assert client.get(url, headers=headers[1]).json()['unread_messages'] == 0
    client.post(url + '/messages', headers=headers[0], json={'body': 'Next message', 'idempotency_key': str(uuid4())})
    client.post(url + '/discussion/read', headers=headers[1], json={'sequence': 0})
    assert client.get(url, headers=headers[1]).json()['unread_messages'] == 1
    response = client.post(
        url + '/messages',
        headers=headers[1],
        json={'body': 'A reply', 'idempotency_key': str(uuid4()), 'parent_id': original['id']},
    )
    assert response.status_code == 201
    deliver_case_events()
    owner_notifications = client.get('/api/notifications', headers=headers[0]).json()['items']
    assert any(n['event_type'] == 'message_reply' for n in owner_notifications)
    client.post(url + '/leave', headers=headers[1])
    item = client.get('/api/notifications', headers=headers[1]).json()['items'][0]
    assert item['event_type'] == 'unavailable' and item['case_id'] is None and item['subject_id'] is None


def test_blocking_revokes_case_and_downstream_rights_permanently(record_client):
    from test_records import _create_admin, _create_share_request

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    share = _create_share_request(
        client,
        headers[1]['Authorization'].removeprefix('Bearer '),
        to_user_email='outsider@cases.example.com',
        record_ids=[records[0]['id']],
    )['request']
    assert client.post(f'/api/share-requests/{share["id"]}/accept', headers=headers[2]).status_code == 200
    _create_admin()
    admin_token = _login(client, 'admin@example.com', TEST_DOCTOR_PASSWORD)
    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    blocked = client.patch(f'/api/admin/users/{ids[1]}/status', headers=admin_headers, json={'status': 'blocked'})
    assert blocked.status_code == 200, blocked.text
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[2]).status_code in {403, 404}
    assert (
        client.patch(f'/api/admin/users/{ids[1]}/status', headers=admin_headers, json={'status': 'active'}).status_code
        == 200
    )
    assert client.get(url, headers=headers[1]).status_code == 404
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[1]).status_code in {403, 404}


def test_losing_doctor_role_is_cleaned_and_cascaded(record_client):
    from app.infrastructure.adapters.queue.case_events import cleanup_invalid_participants
    from app.infrastructure.db.models.auth.user import UserRole

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    client.post(url + '/invitations/accept', headers=headers[1])
    with get_session_factory()() as session:
        session.get(UserRow, ids[1]).role = UserRole.PATIENT
        session.commit()
    assert client.get(url, headers=headers[1]).status_code == 403
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[1]).status_code in {403, 404}
    cleanup_invalid_participants()
    with get_session_factory()() as session:
        session.get(UserRow, ids[1]).role = UserRole.DOCTOR
        session.commit()
    assert client.get(url, headers=headers[1]).status_code == 404


def test_case_sse_rechecks_access_and_never_streams_clinical_text(record_client, monkeypatch):
    from app.presentation.rest.public.v1.cases import events

    client = record_client
    case, _, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    monkeypatch.setattr(events, 'CONNECTION_SECONDS', 0.03)
    monkeypatch.setattr(events, 'POLL_SECONDS', 0.005)
    monkeypatch.setattr(events, 'HEARTBEAT_SECONDS', 0.005)
    assert client.get(url + '/events', headers=headers[1]).status_code == 403
    client.post(url + '/invitations/accept', headers=headers[1])
    initial = client.get(url + '/events', headers=headers[1])
    assert initial.status_code == 200 and 'event: changed' in initial.text and 'Secret' not in initial.text
    cursor = initial.text.split('id: ')[1].split('\n')[0]
    resumed = client.get(url + '/events', headers={**headers[1], 'Last-Event-ID': cursor})
    assert 'event: changed' not in resumed.text and 'heartbeat' in resumed.text
    assert client.get(url + '/events', headers={**headers[1], 'Last-Event-ID': 'invalid'}).status_code == 400
    original = events.read_snapshot
    calls = 0

    def revoke_after_first(token, case_id):
        nonlocal calls
        calls += 1
        if calls == 2:
            with get_session_factory()() as session:
                link = session.scalar(select(UserRecordLinkRow).where(UserRecordLinkRow.user_id == ids[1]))
                session.delete(link)
                session.commit()
        return original(token, case_id)

    monkeypatch.setattr(events, 'read_snapshot', revoke_after_first)
    revoked = client.get(url + '/events', headers=headers[1])
    assert 'event: access-revoked' in revoked.text and 'Secret' not in revoked.text


def test_case_grants_and_downstream_shares_cannot_outlive_origin(record_client):
    """Ограниченный источник не превращается в бессрочное право через случай."""
    from datetime import datetime, timedelta, UTC

    from test_records import _create_share_request

    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    expiry = datetime.now(UTC) + timedelta(days=1)
    with get_session_factory()() as session:
        origin = session.scalar(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == ids[0], UserRecordLinkRow.record_id == UUID(records[0]['id'])
            )
        )
        origin.expires_at = expiry
        session.commit()
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    assert client.post(url + '/invitations/accept', headers=headers[1]).status_code == 200
    downstream = _create_share_request(
        client,
        headers[1]['Authorization'].removeprefix('Bearer '),
        to_user_email='outsider@cases.example.com',
        record_ids=[records[0]['id']],
    )
    assert (
        client.post(f'/api/share-requests/{downstream["request"]["id"]}/accept', headers=headers[2]).status_code == 200
    )
    with get_session_factory()() as session:
        links = session.scalars(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.record_id == UUID(records[0]['id']), UserRecordLinkRow.user_id.in_(ids[1:])
            )
        ).all()
        assert len(links) == 2
        assert all(link.expires_at.replace(tzinfo=UTC) == expiry for link in links)
        for link in links:
            link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    assert client.get(url, headers=headers[1]).json()['accessible'] is False
    assert client.get(f'/api/records/{records[0]["id"]}', headers=headers[2]).status_code in {403, 404}


def test_sse_requires_header_and_rejects_expired_token(record_client):
    """Токен в URL и просроченный Bearer не открывают SSE."""
    from datetime import datetime, timedelta, UTC

    import jwt

    from app.infrastructure.config.settings import get_settings

    client = record_client
    case, _, ids, headers, _ = setup_case(client)
    url = f'/api/cases/{case["id"]}/events'
    assert client.get(url, params={'token': headers[0]['Authorization']}).status_code in {401, 403}
    expired = jwt.encode(
        {'sub': str(ids[0]), 'type': 'access', 'exp': datetime.now(UTC) - timedelta(seconds=5)},
        get_settings().auth.secret_key.get_secret_value(),
        algorithm='HS256',
    )
    assert client.get(url, headers={'Authorization': f'Bearer {expired}'}).status_code == 401


def test_followup_does_not_merge_patients_and_neutral_owner_can_revoke(record_client):
    """Продолжение сохраняет личность пациента, отзыв не требует клинического контекста."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    _register_patient(client, 'other@cases.example.com')
    other = _get_patient_passport_id_by_email('other@cases.example.com')
    assert (
        client.post(
            '/api/cases',
            headers=headers[0],
            json={
                'patient_id': str(other),
                'previous_case_id': case['id'],
                'title': 'Followup',
                'question': 'Question',
                'record_ids': [],
            },
        ).status_code
        == 422
    )
    case = invite(client, case, headers, ids[1])
    url = f'/api/cases/{case["id"]}'
    assert client.post(url + '/invitations/accept', headers=headers[1]).status_code == 200
    with get_session_factory()() as session:
        origin = session.scalar(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == ids[0], UserRecordLinkRow.record_id == UUID(records[0]['id'])
            )
        )
        session.delete(origin)
        session.commit()
    neutral = client.get(url, headers=headers[0]).json()
    assert neutral['case'] is None and neutral['management_members'][0]['user_id'] == str(ids[1])
    assert client.post(url + f'/members/{ids[1]}/remove', headers=headers[0]).status_code == 200


def test_postgres_concurrent_delivery_and_activity_version(postgres_case_client):
    """Повторные workers не дублируют уведомление; обычная реплика обновляет входящие без fanout."""
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4

    from app.infrastructure.adapters.queue.case_events import process_case_event
    from app.infrastructure.db.models.clinical_cases import CaseEventRow

    client = postgres_case_client
    case, _, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    with get_session_factory()() as session:
        event_id = session.scalar(select(CaseEventRow.id).where(CaseEventRow.event_type == 'invitation'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(process_case_event, [str(event_id)] * 4))
    assert client.get('/api/notifications/count', headers=headers[1]).json()['unread'] == 1
    url = f'/api/cases/{case["id"]}'
    assert client.post(url + '/invitations/accept', headers=headers[1]).status_code == 200
    before = client.get('/api/notifications/count', headers=headers[1]).json()
    assert (
        client.post(
            url + '/messages', headers=headers[0], json={'body': 'Normal message', 'idempotency_key': str(uuid4())}
        ).status_code
        == 201
    )
    after = client.get('/api/notifications/count', headers=headers[1]).json()
    assert after['version'] != before['version'] and after['unread'] == before['unread']


def test_case_access_does_not_hydrate_clinical_records(record_client, monkeypatch):
    """Чтение карточки и SSE проверяет ACL без загрузки всех вложений и комментариев."""
    from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
        SqlAlchemyMedicalRecordRepositoryAdapter,
    )

    client = record_client
    case, records, _, headers, _ = setup_case(client)
    response = client.post(
        f'/api/cases/{case["id"]}/materials',
        headers=headers[0],
        json={'version': case['case']['version'], 'record_ids': [r['id'] for r in records]},
    )
    assert response.status_code == 200

    def forbid_record_hydration(*args, **kwargs):
        raise AssertionError('ACL must not hydrate medical records, comments and attachments')

    monkeypatch.setattr(SqlAlchemyMedicalRecordRepositoryAdapter, 'get_accessible_record', forbid_record_hydration)
    view = client.get(f'/api/cases/{case["id"]}', headers=headers[0])
    assert view.status_code == 200 and view.json()['accessible']
    assert view.json()['material_count'] == len(records)
    with get_session_factory()() as session:
        from app.infrastructure.adapters.repositories.clinical_cases import SqlAlchemyCaseRepository

        repository = SqlAlchemyCaseRepository(session)
        assert repository.has_material_access([], UUID(view.json()['coordinator_id']))
        assert not repository.has_material_access([UUID(r['id']) for r in records], uuid4())
