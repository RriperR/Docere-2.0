"""PostgreSQL-регрессии ACL, фильтров и серверных страниц истории пациента."""

from datetime import date, datetime, timedelta, UTC
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from test_records import (
    _create_doctor,
    _create_record,
    _create_share_request,
    _get_patient_passport_id_by_email,
    _get_user_by_email,
    _login,
    _register_patient,
    TEST_DOCTOR_PASSWORD,
    TEST_PATIENT_PASSWORD,
)

from app.application.ports.repositories.patient_cards.dtos import PatientPageFilterDTO, PatientRecordPageFilterDTO
from app.domain.entities.file_attachment import FileAttachmentCategory
from app.domain.entities.medical_record import MedicalRecordStatus, MedicalRecordType
from app.infrastructure.adapters.repositories.patient_cards.sqlalchemy_patient_card_repository import (
    SqlAlchemyPatientCardRepositoryAdapter,
)
from app.infrastructure.db.models.medical_records.file_attachment import FileAttachmentRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.record_comment import RecordCommentRow
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow, UserRecordLinkSourceRow
from app.infrastructure.db.session import get_engine, get_session_factory

pytestmark = pytest.mark.critical


@pytest.fixture
def history(postgres_case_client: TestClient):
    """Создать только синтетическую историю внутри собственной PostgreSQL-схемы."""
    client = postgres_case_client
    _create_doctor(email='reader@example.com')
    _create_doctor(email='owner@example.com')
    reader = _get_user_by_email('reader@example.com')
    owner = _get_user_by_email('owner@example.com')
    headers = {'Authorization': f'Bearer {_login(client, reader.email, TEST_DOCTOR_PASSWORD)}'}
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    card_ids = [UUID(int=n) for n in range(1, 6)]
    record_ids = [UUID(int=n) for n in range(101, 107)]
    with get_session_factory()() as session:
        session.add_all(
            [
                PatientPassportRow(id=card_id, created_by_user_id=reader.id if n < 3 else owner.id, fio=fio)
                for n, (card_id, fio) in enumerate(
                    zip(card_ids, ['Alpha', 'Alpha', 'Literal %_/\\', 'Shared', 'Secret'], strict=False)
                )
            ]
        )
        session.flush()
        for n, record_id in enumerate(record_ids):
            record = MedicalRecordRow(
                id=record_id,
                creator_user_id=owner.id,
                record_type=MedicalRecordType.LAB_RESULT if n == 0 else MedicalRecordType.OTHER,
                status=MedicalRecordStatus.CONFIRMED if n == 0 else MedicalRecordStatus.UNCONFIRMED,
                event_date=date(2026, 1, 3) if n == 0 else date(2026, 1, 2),
                title='Needle %_/\\' if n == 0 else 'Title',
                clinical_summary='Summary Needle' if n == 1 else None,
                payload_json={'pdf_text': 'excluded pdf search'},
                created_at=instant,
                updated_at=instant,
            )
            session.add(record)
        session.flush()
        session.add_all(
            [
                UserRecordLinkRow(
                    user_id=reader.id,
                    record_id=record_id,
                    patient_passport_id=card_ids[3],
                    source=UserRecordLinkSourceRow.SHARE_ACCEPTED,
                    expires_at=datetime.now(UTC) - timedelta(seconds=1) if n == 5 else None,
                )
                for n, record_id in enumerate(record_ids)
                if n != 4
            ]
        )
        session.add(
            UserRecordLinkRow(
                user_id=owner.id,
                record_id=record_ids[4],
                patient_passport_id=card_ids[3],
                source=UserRecordLinkSourceRow.CREATOR,
            )
        )
        comment = RecordCommentRow(record_id=record_ids[2], author_user_id=owner.id, body='excluded comment search')
        session.add(comment)
        session.flush()
        session.add_all(
            [
                FileAttachmentRow(
                    record_id=record_ids[2],
                    comment_id=None,
                    uploaded_by_user_id=owner.id,
                    filename=f'Attachment Needle {n}.pdf',
                    category=FileAttachmentCategory.OTHER,
                    storage_key=f'fixture/{uuid4()}',
                    mime_type='application/pdf',
                    size_bytes=12,
                )
                for n in range(2)
            ]
        )
        session.add(
            FileAttachmentRow(
                record_id=record_ids[2],
                comment_id=comment.id,
                uploaded_by_user_id=owner.id,
                filename='excluded comment attachment.pdf',
                category=FileAttachmentCategory.OTHER,
                storage_key=f'fixture/{uuid4()}',
                mime_type='application/pdf',
                size_bytes=12,
            )
        )
        session.add(
            FileAttachmentRow(
                record_id=record_ids[4],
                comment_id=None,
                uploaded_by_user_id=owner.id,
                filename='Secret Needle.pdf',
                category=FileAttachmentCategory.OTHER,
                storage_key=f'fixture/{uuid4()}',
                mime_type='application/pdf',
                size_bytes=12,
            )
        )
        session.commit()
    return client, headers, reader.id, card_ids, record_ids


def test_patient_pages_sort_count_boundaries_and_legacy_shape(history):
    client, headers, _, cards, _ = history
    default = client.get('/api/patients/page', headers=headers)
    assert default.status_code == 200
    assert default.json()['total'] == 4
    assert default.json()['offset'] == 0
    assert default.json()['limit'] == 20
    assert [item['id'] for item in default.json()['items']] == [str(card) for card in cards[:4]]
    first = client.get('/api/patients/page', params={'limit': 3}, headers=headers).json()
    last = client.get('/api/patients/page', params={'limit': 3, 'offset': 3}, headers=headers).json()
    next_page = client.get('/api/patients/page', params={'limit': 3, 'offset': 6}, headers=headers).json()
    assert len(first['items']) == 3 and len(last['items']) == 1 and next_page['items'] == []
    assert first['total'] == last['total'] == next_page['total'] == 4
    assert last['items'][0]['record_count'] == 4
    assert last['items'][0]['last_record_date'] == '2026-01-03'
    legacy = client.get('/api/patients', headers=headers)
    assert isinstance(legacy.json(), list)
    assert {item['id']: item for item in legacy.json()} == {item['id']: item for item in default.json()['items']}


@pytest.mark.parametrize(
    ('q', 'total'),
    [('ALPHA', 2), ('%_', 1), ('/', 1), ('\\', 1), ('Secret', 0), ("%' OR 1=1 --", 0), ('', 4), ('missing', 0)],
)
def test_patient_literal_case_insensitive_search(history, q, total):
    client, headers, _, _, _ = history
    response = client.get('/api/patients/page', params={'q': q}, headers=headers)
    assert response.status_code == 200
    assert response.json()['total'] == total


def test_record_pages_stable_ties_count_and_legacy_shape(history):
    client, headers, _, cards, records = history
    path = f'/api/patients/{cards[3]}/records'
    pages = [
        client.get(path + '/page', params={'limit': 2, 'offset': offset}, headers=headers).json()
        for offset in [0, 2, 4, 100]
    ]
    assert [page['total'] for page in pages] == [4, 4, 4, 4]
    assert [item['id'] for page in pages for item in page['items']] == [str(records[n]) for n in [0, 3, 2, 1]]
    assert pages[2]['items'] == pages[3]['items'] == []
    legacy = client.get(path, headers=headers)
    assert isinstance(legacy.json(), list)
    assert {item['id']: item for item in legacy.json()} == {
        item['id']: item for page in pages for item in page['items']
    }
    empty = client.get(f'/api/patients/{cards[0]}/records/page', headers=headers)
    assert empty.json() == {'items': [], 'total': 0, 'offset': 0, 'limit': 20}


@pytest.mark.parametrize(
    ('params', 'expected'),
    [
        ({'q': 'NEEDLE'}, [0, 2, 1]),
        ({'q': 'Attachment Needle'}, [2]),
        ({'q': '%_'}, [0]),
        ({'q': '/'}, [0]),
        ({'q': '\\'}, [0]),
        ({'q': 'excluded'}, []),
        ({'q': 'Secret'}, []),
        ({'record_type': 'lab_result'}, [0]),
        ({'confirmation_status': 'confirmed'}, [0]),
        ({'confirmation_status': 'unconfirmed'}, [3, 2, 1]),
        ({'event_date_from': '2026-01-03', 'event_date_to': '2026-01-03'}, [0]),
        ({'event_date_from': '2026-01-02', 'event_date_to': '2026-01-03'}, [0, 3, 2, 1]),
        (
            {
                'q': 'Needle',
                'record_type': 'other',
                'confirmation_status': 'unconfirmed',
                'event_date_to': '2026-01-02',
            },
            [2, 1],
        ),
    ],
)
def test_record_filters_and_attachment_exists_do_not_duplicate(history, params, expected):
    client, headers, _, cards, records = history
    response = client.get(f'/api/patients/{cards[3]}/records/page', params=params, headers=headers)
    assert response.status_code == 200
    assert response.json()['total'] == len(expected)
    assert [item['id'] for item in response.json()['items']] == [str(records[n]) for n in expected]
    if params == {'q': 'Attachment Needle'}:
        item = response.json()['items'][0]
        assert item['attachments_count'] == 2
        assert item['comments_count'] == 1


@pytest.mark.parametrize(
    'params',
    [
        {'offset': -1},
        {'offset': 'x'},
        {'limit': 0},
        {'limit': 101},
        {'limit': 'x'},
        {'q': 'a' * 256},
        {'unknown_filter': 'x'},
    ],
)
def test_invalid_page_parameters_are_422(history, params):
    client, headers, _, cards, _ = history
    for path in ['/api/patients/page', f'/api/patients/{cards[3]}/records/page']:
        assert client.get(path, params=params, headers=headers).status_code == 422


@pytest.mark.parametrize(
    'params',
    [
        {'record_type': 'future'},
        {'confirmation_status': 'future'},
        {'event_date_from': '2026-02-30'},
        {'event_date_to': 'bad'},
        {'event_date_from': '2026-01-03', 'event_date_to': '2026-01-02'},
    ],
)
def test_invalid_history_filters_are_422(history, params):
    client, headers, _, cards, _ = history
    assert client.get(f'/api/patients/{cards[3]}/records/page', params=params, headers=headers).status_code == 422


def test_foreign_and_missing_patient_have_same_404(history):
    client, headers, _, cards, _ = history
    foreign = client.get(f'/api/patients/{cards[4]}/records/page', headers=headers)
    missing = client.get(f'/api/patients/{uuid4()}/records/page', headers=headers)
    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    assert foreign.json()['detail'] == 'Patient not found'
    assert client.get('/api/patients/page').status_code == 401


def test_expired_last_access_hides_card_before_count(history):
    client, headers, reader, cards, _ = history
    with get_session_factory()() as session:
        for link in session.query(UserRecordLinkRow).filter_by(user_id=reader, patient_passport_id=cards[3]):
            link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    page = client.get('/api/patients/page', params={'q': 'Shared'}, headers=headers).json()
    assert page['total'] == 0 and page['items'] == []
    assert client.get(f'/api/patients/{cards[3]}/records/page', headers=headers).status_code == 404


def test_page_projection_query_count_is_constant_and_search_is_bound(history):
    _, _, reader, cards, _ = history
    statements = []

    def capture(connection, cursor, statement, parameters, context, many):
        statements.append((statement, parameters))

    engine = get_engine()
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        with get_session_factory()() as session:
            repository = SqlAlchemyPatientCardRepositoryAdapter(session)
            page = repository.list_accessible_patients_page(
                user_id=reader, user_role='doctor', filters=PatientPageFilterDTO(limit=100)
            )
            assert len(page.items) == 4 and len(statements) == 3
            statements.clear()
            records = repository.list_patient_records_page(
                patient_id=cards[3], user_id=reader, filters=PatientRecordPageFilterDTO(q='Needle', limit=100)
            )
            assert len(records.items) == 3 and len(statements) == 2
            assert 'Needle' not in statements[0][0]
            assert any('Needle' in str(value) for value in statements[0][1].values())
            assert 'LIMIT' in statements[1][0] and 'OFFSET' in statements[1][0]
    finally:
        event.remove(engine, 'before_cursor_execute', capture)


def test_real_share_revocation_updates_pages_and_patient_role(postgres_case_client: TestClient):
    client = postgres_case_client
    _register_patient(client, 'patient-owner@example.com', fio='Patient owner')
    _create_doctor(email='share-reader@example.com')
    patient_token = _login(client, 'patient-owner@example.com', TEST_PATIENT_PASSWORD)
    reader_token = _login(client, 'share-reader@example.com', TEST_DOCTOR_PASSWORD)
    patient_headers = {'Authorization': f'Bearer {patient_token}'}
    reader_headers = {'Authorization': f'Bearer {reader_token}'}
    patient_id = _get_patient_passport_id_by_email('patient-owner@example.com')
    record = _create_record(client, patient_token, patient_id, author_practitioner_full_name='Synthetic doctor')
    own = client.get('/api/patients/page', headers=patient_headers).json()
    assert own['total'] == 1 and own['items'][0]['id'] == str(patient_id)
    share = _create_share_request(
        client, patient_token, to_user_email='share-reader@example.com', record_ids=[record['id']]
    )
    share_id = share['request']['id']
    assert client.post(f'/api/share-requests/{share_id}/accept', headers=reader_headers).status_code == 200
    path = f'/api/patients/{patient_id}/records/page'
    assert client.get(path, headers=reader_headers).json()['total'] == 1
    assert client.get('/api/patients/page', headers=reader_headers).json()['total'] == 1
    assert client.post(f'/api/share-requests/{share_id}/revoke', headers=patient_headers).status_code == 200
    assert client.get(path, headers=reader_headers).status_code == 404
    assert client.get('/api/patients/page', headers=reader_headers).json()['total'] == 0
    assert client.get(path, headers=patient_headers).json()['total'] == 1


def test_record_created_at_precedes_id_for_equal_event_dates(history):
    client, headers, _, cards, records = history
    with get_session_factory()() as session:
        record = session.get(MedicalRecordRow, records[1])
        record.created_at = datetime(2026, 1, 2, tzinfo=UTC)
        session.commit()
    page = client.get(f'/api/patients/{cards[3]}/records/page', headers=headers).json()
    assert [item['id'] for item in page['items']] == [str(records[n]) for n in [0, 1, 3, 2]]
