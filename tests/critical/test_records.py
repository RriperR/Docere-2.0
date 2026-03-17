"""Критические API-тесты для создания и чтения медицинских записей."""

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
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow
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
    fio: str = 'РРІР°РЅРѕРІ РРІР°РЅ РРІР°РЅРѕРІРёС‡',
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


def _get_patient_passport_id_by_email(email: str) -> UUID:
    with get_session_factory()() as session:
        user = session.scalar(select(UserRow).where(UserRow.email == email.lower()))
        assert user is not None
        patient_passport = session.scalar(
            select(PatientPassportRow).where(PatientPassportRow.patient_user_id == user.id),
        )
        assert patient_passport is not None
        return patient_passport.id


def _create_doctor(email: str = 'doctor@example.com', password: str = TEST_DOCTOR_PASSWORD) -> None:
    with get_session_factory()() as session:
        doctor = UserRow(
            fio='РџРµС‚СЂРѕРІ РџРµС‚СЂ РџРµС‚СЂРѕРІРёС‡',
            email=email,
            phone='+79991112233',
            password_hash=Pbkdf2PasswordHasherAdapter().hash_password(plain_password=password),
            role=UserRole.DOCTOR,
            status=UserStatus.ACTIVE,
        )
        session.add(doctor)
        session.commit()


def _create_record(
    client: TestClient,
    access_token: str,
    patient_passport_id: UUID,
    title: str = 'РџРµСЂРІРёС‡РЅС‹Р№ РѕСЃРјРѕС‚СЂ',
) -> dict[str, object]:
    response = client.post(
        '/api/records',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'patient_passport_id': str(patient_passport_id),
            'record_type': 'consultation_result',
            'event_date': '2026-03-11',
            'title': title,
            'payload_json': {
                'complaints': 'Р“РѕР»РѕРІРЅР°СЏ Р±РѕР»СЊ',
                'conclusion': 'РќР°Р±Р»СЋРґРµРЅРёРµ',
            },
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.critical
def test_patient_can_create_record_for_own_passport(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient1@example.com')
    access_token = _login(record_client, 'patient1@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient1@example.com')

    response_body = _create_record(record_client, access_token, patient_passport_id)

    assert response_body['patient_passport_id'] == str(patient_passport_id)
    assert response_body['record_type'] == 'consultation_result'
    assert response_body['status'] == 'unconfirmed'

    with get_session_factory()() as session:
        record = session.get(MedicalRecordRow, UUID(response_body['id']))
        access_link = session.scalar(
            select(UserRecordLinkRow).where(UserRecordLinkRow.record_id == UUID(response_body['id'])),
        )

    assert record is not None
    assert access_link is not None
    assert access_link.patient_passport_id == patient_passport_id


@pytest.mark.critical
def test_doctor_can_create_record_for_existing_patient_passport(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient2@example.com')
    patient_passport_id = _get_patient_passport_id_by_email('patient2@example.com')
    _create_doctor()
    access_token = _login(record_client, 'doctor@example.com', password=TEST_DOCTOR_PASSWORD)

    response_body = _create_record(record_client, access_token, patient_passport_id, title='РћСЃРјРѕС‚СЂ РІСЂР°С‡Р°')

    assert response_body['patient_passport_id'] == str(patient_passport_id)


@pytest.mark.critical
def test_record_author_can_get_created_record(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient3@example.com')
    access_token = _login(record_client, 'patient3@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient3@example.com')
    created_record = _create_record(record_client, access_token, patient_passport_id)

    response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {access_token}'},
    )

    assert response.status_code == 200
    assert response.json()['id'] == created_record['id']


@pytest.mark.critical
def test_user_without_user_record_link_gets_forbidden(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient4@example.com')
    owner_token = _login(record_client, 'patient4@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('patient4@example.com')
    created_record = _create_record(record_client, owner_token, owner_passport_id)

    _register_patient(record_client, 'patient5@example.com', fio='РЎРёРґРѕСЂРѕРІ РЎРёРґРѕСЂ РЎРёРґРѕСЂРѕРІРёС‡')
    stranger_token = _login(record_client, 'patient5@example.com', TEST_PATIENT_PASSWORD)

    response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {stranger_token}'},
    )

    assert response.status_code == 403


@pytest.mark.critical
def test_patient_cannot_create_record_for_foreign_passport(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient6@example.com')
    foreign_passport_id = _get_patient_passport_id_by_email('patient6@example.com')

    _register_patient(record_client, 'patient7@example.com', fio='РЎРµРјРµРЅРѕРІ РЎРµРјРµРЅ РЎРµРјРµРЅРѕРІРёС‡')
    access_token = _login(record_client, 'patient7@example.com', TEST_PATIENT_PASSWORD)

    response = record_client.post(
        '/api/records',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'patient_passport_id': str(foreign_passport_id),
            'record_type': 'consultation_result',
            'event_date': '2026-03-11',
            'title': 'РџРѕРїС‹С‚РєР° СЃРѕР·РґР°С‚СЊ С‡СѓР¶СѓСЋ Р·Р°РїРёСЃСЊ',
            'payload_json': {'note': 'forbidden'},
        },
    )

    assert response.status_code == 403
