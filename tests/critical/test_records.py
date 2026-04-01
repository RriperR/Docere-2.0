"""Critical API tests for medical record creation, reading, and comments."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.adapters.security.pbkdf2_password_hasher import Pbkdf2PasswordHasherAdapter
from app.infrastructure.config.settings import clear_settings_cache
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.medical_records.file_attachment import (
    FileAttachmentCategoryRow,
    FileAttachmentRow,
)
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.practitioner_passport import PractitionerPassportRow
from app.infrastructure.db.models.medical_records.user_record_link import (
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
)
from app.infrastructure.db.session import clear_db_session_cache, get_engine, get_session_factory
from app.presentation.main import create_app

TEST_PATIENT_PASSWORD = 'VeryStrongPass123'  # noqa: S105
TEST_DOCTOR_PASSWORD = 'DoctorStrongPass123'  # noqa: S105


def _set_required_env(monkeypatch: pytest.MonkeyPatch, sqlite_path: Path) -> None:
    monkeypatch.setenv('APP_DATABASE__URL', f'sqlite+pysqlite:///{sqlite_path.as_posix()}')
    monkeypatch.setenv('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    monkeypatch.setenv('APP_AUTH__ACCESS_TOKEN_TTL_MINUTES', '60')
    monkeypatch.setenv('APP_AUTH__REFRESH_TOKEN_TTL_MINUTES', '10080')
    monkeypatch.setenv('APP_AUTH__JWT_ALGORITHM', 'HS256')
    monkeypatch.setenv('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    monkeypatch.setenv('APP_STORAGE__BUCKET', 'docere-records')
    monkeypatch.setenv('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('APP_QUEUE__RESULT_BACKEND', 'redis://localhost:6379/1')


@pytest.fixture
def record_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    sqlite_path = tmp_path / 'records.sqlite3'
    _set_required_env(monkeypatch, sqlite_path)
    clear_settings_cache()
    clear_db_session_cache()
    Base.metadata.create_all(bind=get_engine())

    with TestClient(create_app()) as client:
        yield client

    clear_db_session_cache()
    clear_settings_cache()


def _register_patient(
    client: TestClient,
    email: str,
    fio: str = 'Ivan Ivanov',
) -> None:
    response = client.post(
        '/api/auth/register',
        json={
            'fio': fio,
            'email': email,
            'phone': '+79990000000',
            'password': TEST_PATIENT_PASSWORD,
            'date_of_birth': '1990-01-01',
        },
    )
    assert response.status_code == 201


def _login(client: TestClient, email: str, password: str) -> str:
    response = client.post(
        '/api/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200
    return response.json()['access_token']


def _get_user_by_email(email: str) -> UserRow:
    with get_session_factory()() as session:
        user = session.scalar(select(UserRow).where(UserRow.email == email.lower()))
        assert user is not None
        return user


def _get_patient_passport_id_by_email(email: str) -> UUID:
    with get_session_factory()() as session:
        user = session.scalar(select(UserRow).where(UserRow.email == email.lower()))
        assert user is not None
        patient_passport = session.scalar(
            select(PatientPassportRow).where(PatientPassportRow.patient_user_id == user.id),
        )
        assert patient_passport is not None
        return patient_passport.id


def _create_user(
    *,
    email: str,
    password: str,
    role: UserRole,
    fio: str,
) -> None:
    with get_session_factory()() as session:
        user = UserRow(
            fio=fio,
            email=email,
            phone='+79991112233',
            password_hash=Pbkdf2PasswordHasherAdapter().hash_password(plain_password=password),
            role=role,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        session.commit()


def _create_doctor(email: str = 'doctor@example.com', password: str = TEST_DOCTOR_PASSWORD) -> None:
    _create_user(
        email=email,
        password=password,
        role=UserRole.DOCTOR,
        fio='Dr. House',
    )


def _create_admin(email: str = 'admin@example.com', password: str = TEST_DOCTOR_PASSWORD) -> None:
    _create_user(
        email=email,
        password=password,
        role=UserRole.ADMIN,
        fio='System Admin',
    )


def _grant_record_access(user_id: UUID, record_id: UUID, patient_passport_id: UUID) -> None:
    with get_session_factory()() as session:
        session.add(
            UserRecordLinkRow(
                user_id=user_id,
                record_id=record_id,
                patient_passport_id=patient_passport_id,
                source=UserRecordLinkSourceRow.MANUAL_ATTACH,
            ),
        )
        session.commit()


def _create_record(
    client: TestClient,
    access_token: str,
    patient_passport_id: UUID,
    *,
    author_practitioner_passport_id: UUID | None = None,
    author_practitioner_full_name: str | None = None,
    title: str = 'Initial visit',
    appointment_location: str | None = 'Clinic A',
    clinical_summary: str | None = 'Patient is stable.',
) -> dict[str, object]:
    payload: dict[str, object] = {
        'patient_passport_id': str(patient_passport_id),
        'record_type': 'consultation_result',
        'event_date': '2026-03-11',
        'title': title,
        'appointment_location': appointment_location,
        'clinical_summary': clinical_summary,
        'payload_json': {
            'complaints': 'Headache',
            'conclusion': 'Observation recommended',
        },
    }
    if author_practitioner_passport_id is not None:
        payload['author_practitioner_passport_id'] = str(author_practitioner_passport_id)
    if author_practitioner_full_name is not None:
        payload['author_practitioner_full_name'] = author_practitioner_full_name
        payload['author_practitioner_specialty'] = 'Neurologist'
        payload['author_practitioner_organization'] = 'City Hospital'
        payload['author_practitioner_position'] = 'Senior Doctor'
        payload['author_practitioner_email'] = 'external-doctor@example.com'
        payload['author_practitioner_phone'] = '+79998887766'

    response = client.post(
        '/api/records',
        headers={'Authorization': f'Bearer {access_token}'},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.critical
def test_patient_can_create_record_for_own_passport_with_external_practitioner(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient1@example.com')
    access_token = _login(record_client, 'patient1@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient1@example.com')

    response_body = _create_record(
        record_client,
        access_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
    )

    assert response_body['patient_passport_id'] == str(patient_passport_id)
    assert response_body['record_type'] == 'consultation_result'
    assert response_body['status'] == 'unconfirmed'
    assert response_body['appointment_location'] == 'Clinic A'
    assert response_body['clinical_summary'] == 'Patient is stable.'
    assert response_body['author_practitioner_passport']['full_name'] == 'Dr. External'
    assert response_body['comments_count'] == 0
    assert response_body['attachments_count'] == 0

    with get_session_factory()() as session:
        record = session.get(MedicalRecordRow, UUID(response_body['id']))
        access_link = session.scalar(
            select(UserRecordLinkRow).where(UserRecordLinkRow.record_id == UUID(response_body['id'])),
        )
        practitioner = session.get(
            PractitionerPassportRow,
            UUID(response_body['author_practitioner_passport']['id']),
        )

    assert record is not None
    assert record.appointment_location == 'Clinic A'
    assert record.clinical_summary == 'Patient is stable.'
    assert access_link is not None
    assert access_link.patient_passport_id == patient_passport_id
    assert practitioner is not None
    assert practitioner.user_id is None


@pytest.mark.critical
def test_doctor_can_create_record_and_internal_practitioner_is_linked(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient2@example.com')
    patient_passport_id = _get_patient_passport_id_by_email('patient2@example.com')
    _create_doctor()
    access_token = _login(record_client, 'doctor@example.com', password=TEST_DOCTOR_PASSWORD)

    response_body = _create_record(
        record_client,
        access_token,
        patient_passport_id,
        title='Doctor visit',
    )

    doctor = _get_user_by_email('doctor@example.com')
    assert response_body['author_practitioner_passport']['user_id'] == str(doctor.id)

    with get_session_factory()() as session:
        record = session.get(MedicalRecordRow, UUID(response_body['id']))

    assert record is not None
    assert record.author_practitioner_passport_id is not None


@pytest.mark.critical
def test_record_detail_returns_comments_and_attachments_separately(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient3@example.com')
    patient_token = _login(record_client, 'patient3@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient3@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. Outside',
    )

    _create_doctor()
    doctor_token = _login(record_client, 'doctor@example.com', TEST_DOCTOR_PASSWORD)
    doctor = _get_user_by_email('doctor@example.com')
    _grant_record_access(doctor.id, UUID(created_record['id']), patient_passport_id)

    comment_response = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json={'body': 'Follow-up in 3 days.'},
    )
    assert comment_response.status_code == 201

    doctor = _get_user_by_email('doctor@example.com')
    with get_session_factory()() as session:
        attachment = FileAttachmentRow(
            record_id=UUID(created_record['id']),
            uploaded_by_user_id=doctor.id,
            category=FileAttachmentCategoryRow.DOCUMENT,
            storage_key='records/doc-1.pdf',
            mime_type='application/pdf',
            size_bytes=1024,
        )
        session.add(attachment)
        session.commit()

    response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {patient_token}'},
    )

    assert response.status_code == 200
    assert response.json()['comments_count'] == 1
    assert response.json()['attachments_count'] == 1
    assert response.json()['comments'][0]['body'] == 'Follow-up in 3 days.'
    assert response.json()['attachments'][0]['category'] == 'document'


@pytest.mark.critical
def test_patient_cannot_comment_on_record(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient4@example.com')
    patient_token = _login(record_client, 'patient4@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient4@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
    )

    response = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {patient_token}'},
        json={'body': 'I should not be able to add this comment.'},
    )

    assert response.status_code == 403


@pytest.mark.critical
def test_multiple_doctors_can_comment_same_record(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient5@example.com')
    patient_token = _login(record_client, 'patient5@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient5@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
    )

    _create_doctor(email='doctor1@example.com')
    _create_doctor(email='doctor2@example.com')
    doctor1_token = _login(record_client, 'doctor1@example.com', TEST_DOCTOR_PASSWORD)
    doctor2_token = _login(record_client, 'doctor2@example.com', TEST_DOCTOR_PASSWORD)
    doctor1 = _get_user_by_email('doctor1@example.com')
    doctor2 = _get_user_by_email('doctor2@example.com')
    _grant_record_access(doctor1.id, UUID(created_record['id']), patient_passport_id)
    _grant_record_access(doctor2.id, UUID(created_record['id']), patient_passport_id)

    response1 = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {doctor1_token}'},
        json={'body': 'First opinion.'},
    )
    response2 = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {doctor2_token}'},
        json={'body': 'Second opinion.'},
    )

    assert response1.status_code == 201
    assert response2.status_code == 201

    response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {patient_token}'},
    )

    assert response.status_code == 200
    assert response.json()['comments_count'] == 2
    assert [comment['body'] for comment in response.json()['comments']] == [
        'First opinion.',
        'Second opinion.',
    ]


@pytest.mark.critical
def test_patient_cannot_create_record_for_foreign_passport(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient6@example.com')
    foreign_passport_id = _get_patient_passport_id_by_email('patient6@example.com')

    _register_patient(record_client, 'patient7@example.com', fio='Another Patient')
    access_token = _login(record_client, 'patient7@example.com', TEST_PATIENT_PASSWORD)

    response = record_client.post(
        '/api/records',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'patient_passport_id': str(foreign_passport_id),
            'record_type': 'consultation_result',
            'event_date': '2026-03-11',
            'title': 'Forbidden record',
            'author_practitioner_full_name': 'Dr. External',
            'payload_json': {'note': 'forbidden'},
        },
    )

    assert response.status_code == 403


@pytest.mark.critical
def test_admin_can_comment_when_has_access_link(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient8@example.com')
    patient_token = _login(record_client, 'patient8@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient8@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
    )
    _create_admin()
    admin = _get_user_by_email('admin@example.com')
    admin_token = _login(record_client, 'admin@example.com', TEST_DOCTOR_PASSWORD)
    _grant_record_access(admin.id, UUID(created_record['id']), patient_passport_id)

    response = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {admin_token}'},
        json={'body': 'Admin review note.'},
    )

    assert response.status_code == 201
