"""Прямые API-проверки изоляции и происхождения прав клинических случаев."""

from uuid import UUID

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
    """Выполнить операцию клинического случая."""
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
    """Выполнить операцию клинического случая."""
    response = client.post(
        f'/api/cases/{view["id"]}/invitations',
        headers=headers[0],
        json={'version': view['case']['version'], 'user_id': str(target)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_pending_invitation_never_exposes_clinical_context(record_client):
    """Выполнить операцию клинического случая."""
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
    """Выполнить операцию клинического случая."""
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
    """Выполнить операцию клинического случая."""
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
    """Выполнить операцию клинического случая."""
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
