"""Critical API tests for medical record creation, reading, and comments."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, UTC
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid, SecondaryCaptureImageStorage
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified

from app.application.ports.storage.file_storage import FileStoragePort
from app.domain.entities.file_attachment import FileAttachmentCategory
from app.infrastructure.adapters.queue.recover_import_jobs import enqueue_recoverable_import_jobs
from app.infrastructure.adapters.queue.tasks import process_import_job
from app.infrastructure.adapters.security.pbkdf2_password_hasher import Pbkdf2PasswordHasherAdapter
from app.infrastructure.config.settings import clear_settings_cache
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.audit_event import AuditEventRow
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.medical_records.file_attachment import FileAttachmentRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.practitioner_passport import PractitionerPassportRow
from app.infrastructure.db.models.medical_records.record_share import (
    RecordShareRequestRow,
    RecordShareRow,
    RecordShareStatusRow,
)
from app.infrastructure.db.models.medical_records.user_record_link import (
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
)
from app.infrastructure.db.session import clear_db_session_cache, get_engine, get_session_factory
from app.presentation.main import create_app
from app.presentation.webserver.rate_limit import clear_auth_rate_limits

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
    clear_auth_rate_limits()
    Base.metadata.create_all(bind=get_engine())

    with TestClient(create_app()) as client:
        yield client

    clear_db_session_cache()
    clear_settings_cache()
    clear_auth_rate_limits()


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


def _create_share_request(
    client: TestClient,
    access_token: str,
    *,
    to_user_email: str,
    record_ids: list[str],
    message: str | None = 'Please review.',
    expires_at: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        'to_user_email': to_user_email,
        'record_ids': record_ids,
        'message': message,
    }
    if expires_at is not None:
        payload['expires_at'] = expires_at
    response = client.post(
        '/api/share-requests',
        headers={'Authorization': f'Bearer {access_token}'},
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


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


def _get_first_record_link_values() -> tuple[UUID, UUID, UUID | None]:
    with get_session_factory()() as session:
        link = session.scalar(select(UserRecordLinkRow))
        assert link is not None
        return link.user_id, link.record_id, link.patient_passport_id


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
    record_type: str = 'consultation_result',
    event_date: str = '2026-03-11',
) -> dict[str, object]:
    payload: dict[str, object] = {
        'patient_passport_id': str(patient_passport_id),
        'record_type': record_type,
        'event_date': event_date,
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
    assert response_body['confirmed_by_user_id'] is None
    assert response_body['confirmed_at'] is None
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
        audit_event = session.scalar(
            select(AuditEventRow).where(
                AuditEventRow.event_type == 'create_record',
                AuditEventRow.entity_id == UUID(response_body['id']),
            ),
        )

    assert record is not None
    assert record.appointment_location == 'Clinic A'
    assert record.clinical_summary == 'Patient is stable.'
    assert access_link is not None
    assert access_link.patient_passport_id == patient_passport_id
    assert practitioner is not None
    assert practitioner.user_id is None
    assert audit_event is not None
    assert audit_event.entity_type == 'medical_record'


@pytest.mark.critical
def test_doctor_can_create_record_and_internal_practitioner_is_linked(record_client: TestClient) -> None:
    _create_doctor()
    access_token = _login(record_client, 'doctor@example.com', password=TEST_DOCTOR_PASSWORD)
    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'fio': 'Doctor Local Patient',
            'date_of_birth': '1988-02-01',
            'email': 'doctor-local-patient@example.com',
            'phone': '+79994445566',
        },
    )
    assert create_patient_response.status_code == 201
    patient_passport_id = UUID(create_patient_response.json()['id'])

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
def test_duplicate_user_record_link_is_rejected(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient-link-unique@example.com')
    access_token = _login(record_client, 'patient-link-unique@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient-link-unique@example.com')

    _create_record(
        record_client,
        access_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
    )
    user_id, record_id, link_patient_passport_id = _get_first_record_link_values()

    with get_session_factory()() as session:
        session.add(
            UserRecordLinkRow(
                user_id=user_id,
                record_id=record_id,
                patient_passport_id=link_patient_passport_id,
                source=UserRecordLinkSourceRow.MANUAL_ATTACH,
            ),
        )
        with pytest.raises(IntegrityError):
            session.commit()


@pytest.mark.critical
def test_doctor_cannot_create_record_for_inaccessible_passport(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient2-private@example.com')
    patient_passport_id = _get_patient_passport_id_by_email('patient2-private@example.com')
    _create_doctor(email='doctor-no-access@example.com')
    access_token = _login(record_client, 'doctor-no-access@example.com', password=TEST_DOCTOR_PASSWORD)

    response = record_client.post(
        '/api/records',
        headers={'Authorization': f'Bearer {access_token}'},
        json={
            'patient_passport_id': str(patient_passport_id),
            'record_type': 'consultation_result',
            'event_date': '2026-03-11',
            'title': 'Forbidden doctor record',
            'payload_json': {'note': 'doctor has no patient access'},
        },
    )

    assert response.status_code == 403


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
            category=FileAttachmentCategory.DOCUMENT,
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


class _InMemoryStorage(FileStoragePort):
    """Хранилище в памяти для тестов вложений."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, *, key: str, content: bytes, content_type: str) -> None:
        self.objects[key] = content

    def download(self, *, key: str) -> bytes:
        return self.objects[key]


def _build_zip_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode='w') as archive:
        archive.writestr('readme.txt', 'archive payload')
    return buffer.getvalue()


def _build_patient_archive_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode='w') as archive:
        archive.writestr('Иванов Иван Иванович/dob 1980-01-02/lab 2026-04-05/result.pdf', b'%PDF-1.4')
        archive.writestr('__MACOSX/.DS_Store', b'noise')
    return buffer.getvalue()


def _build_dicom_bytes() -> bytes:
    buffer = BytesIO()
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset('study.dcm', {}, file_meta=file_meta, preamble=b'\0' * 128)
    dataset.PatientName = 'Petrov^Petr^Petrovich'
    dataset.PatientBirthDate = '19750506'
    dataset.StudyDate = '20260407'
    dataset.Modality = 'MR'
    dataset.StudyDescription = 'Brain MRI'
    dataset.SeriesDescription = 'T2'
    dataset.InstitutionName = 'Demo Clinic'
    dataset.StudyInstanceUID = generate_uid()
    dataset.SeriesInstanceUID = generate_uid()
    dataset.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


def _build_dicom_archive_bytes() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode='w') as archive:
        archive.writestr('dicom/study.dcm', _build_dicom_bytes())
    return buffer.getvalue()


@pytest.mark.critical
def test_import_job_upload_status_and_worker_completion(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr(
        'app.presentation.rest.public.v1.archives.router.get_file_storage',
        lambda: storage,
    )
    monkeypatch.setattr(
        'app.infrastructure.adapters.queue.tasks.get_file_storage',
        lambda: storage,
    )
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-owner@example.com')
    token = _login(record_client, 'import-owner@example.com', TEST_DOCTOR_PASSWORD)
    archive_content = _build_patient_archive_bytes()

    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('records.zip', archive_content, 'application/zip')},
    )

    assert upload_response.status_code == 201
    uploaded_job = upload_response.json()
    assert uploaded_job['status'] == 'queued'
    assert uploaded_job['original_filename'] == 'records.zip'
    assert uploaded_job['size_bytes'] == len(archive_content)
    assert len(storage.objects) == 1

    status_response = record_client.get(
        f'/api/archives/imports/{uploaded_job["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert status_response.status_code == 200
    assert status_response.json()['archive_storage_key'] == uploaded_job['archive_storage_key']

    process_import_job(str(uploaded_job['id']))
    review_response = record_client.get(
        f'/api/archives/imports/{uploaded_job["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert review_response.status_code == 200
    assert review_response.json()['status'] == 'needs_review'
    report = review_response.json()['report_json']
    assert report['patients'][0]['fio'] == 'Иванов Иван Иванович'
    assert report['patients'][0]['date_of_birth'] == '1980-01-02'
    assert report['patients'][0]['record_groups'][0]['record_type'] == 'lab_result'

    resolve_response = record_client.post(
        f'/api/archives/imports/{uploaded_job["id"]}/resolve',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'decisions': [
                {
                    'candidate_id': report['patients'][0]['candidate_id'],
                    'action': 'create',
                    'fio': report['patients'][0]['fio'],
                    'date_of_birth': report['patients'][0]['date_of_birth'],
                    'record_groups': [
                        {
                            'group_id': report['patients'][0]['record_groups'][0]['group_id'],
                            'action': 'create',
                            'record_type': 'lab_result',
                            'event_date': '2026-04-05',
                            'title': 'Импортированный анализ',
                        },
                    ],
                },
            ],
        },
    )

    assert resolve_response.status_code == 200
    assert resolve_response.json()['status'] == 'completed_with_warnings'
    assert resolve_response.json()['report_json']['patients_created'] == 1
    assert resolve_response.json()['report_json']['records_created'] == 1
    assert resolve_response.json()['report_json']['attachments_created'] == 1
    repeat_resolve_response = record_client.post(
        f'/api/archives/imports/{uploaded_job["id"]}/resolve',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'decisions': [
                {
                    'candidate_id': report['patients'][0]['candidate_id'],
                    'action': 'create',
                    'fio': report['patients'][0]['fio'],
                    'date_of_birth': report['patients'][0]['date_of_birth'],
                    'record_groups': [
                        {
                            'group_id': report['patients'][0]['record_groups'][0]['group_id'],
                            'action': 'create',
                            'record_type': 'lab_result',
                            'event_date': '2026-04-05',
                            'title': 'Повторный импорт',
                        },
                    ],
                },
            ],
        },
    )
    assert repeat_resolve_response.status_code == 200
    assert repeat_resolve_response.json()['status'] == 'completed_with_warnings'
    with get_session_factory()() as session:
        job = session.get(ImportJobRow, UUID(uploaded_job['id']))
        audit_event = session.scalar(
            select(AuditEventRow).where(
                AuditEventRow.event_type == 'import',
                AuditEventRow.entity_id == UUID(uploaded_job['id']),
            ),
        )
        patient = session.scalar(select(PatientPassportRow).where(PatientPassportRow.fio == 'Иванов Иван Иванович'))
        assert patient is not None
        record = session.scalar(
            select(MedicalRecordRow).join(UserRecordLinkRow).where(UserRecordLinkRow.patient_passport_id == patient.id),
        )
        assert record is not None
        import_provenance = record.payload_json.get('import_provenance')
        assert isinstance(import_provenance, dict)
        assert import_provenance['source'] == 'archive'
        assert import_provenance['import_job_id'] == uploaded_job['id']
        assert import_provenance['source_archive'] == 'records.zip'
        assert import_provenance['files'][0]['path'].endswith('result.pdf')
        attachment = session.scalar(select(FileAttachmentRow).where(FileAttachmentRow.record_id == record.id))
        assert attachment is not None
        records_count = len(session.scalars(select(MedicalRecordRow)).all())
    assert job is not None
    assert job.archive_storage_key in storage.objects
    assert audit_event is not None
    assert audit_event.entity_type == 'import_job'
    assert records_count == 1


@pytest.mark.critical
def test_import_job_resolve_warns_when_report_file_disappeared(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.infrastructure.adapters.queue.tasks.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-missing-file@example.com')
    token = _login(record_client, 'import-missing-file@example.com', TEST_DOCTOR_PASSWORD)

    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('records.zip', _build_patient_archive_bytes(), 'application/zip')},
    )
    process_import_job(upload_response.json()['id'])
    with get_session_factory()() as session:
        job = session.get(ImportJobRow, UUID(upload_response.json()['id']))
        assert job is not None
        report = dict(job.report_json)
        report['patients'][0]['record_groups'][0]['files'][0]['path'] = 'missing/result.pdf'
        job.report_json = report
        flag_modified(job, 'report_json')
        session.commit()

    status_response = record_client.get(
        f'/api/archives/imports/{upload_response.json()["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )
    report = status_response.json()['report_json']
    resolve_response = record_client.post(
        f'/api/archives/imports/{upload_response.json()["id"]}/resolve',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'decisions': [
                {
                    'candidate_id': report['patients'][0]['candidate_id'],
                    'action': 'create',
                    'fio': report['patients'][0]['fio'],
                    'date_of_birth': report['patients'][0]['date_of_birth'],
                    'record_groups': [
                        {
                            'group_id': report['patients'][0]['record_groups'][0]['group_id'],
                            'action': 'create',
                            'record_type': 'lab_result',
                            'event_date': '2026-04-05',
                            'title': 'Импорт без файла',
                        },
                    ],
                },
            ],
        },
    )

    body = resolve_response.json()
    assert resolve_response.status_code == 200
    assert body['status'] == 'completed_with_warnings'
    assert body['report_json']['records_created'] == 1
    assert body['report_json']['attachments_created'] == 0
    assert any('File disappeared from archive during resolve' in warning for warning in body['report_json']['warnings'])


@pytest.mark.critical
def test_import_job_resolve_warns_when_archive_becomes_unreadable(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.infrastructure.adapters.queue.tasks.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-unreadable-resolve@example.com')
    token = _login(record_client, 'import-unreadable-resolve@example.com', TEST_DOCTOR_PASSWORD)

    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('records.zip', _build_patient_archive_bytes(), 'application/zip')},
    )
    process_import_job(upload_response.json()['id'])
    uploaded_job = upload_response.json()
    storage.objects[uploaded_job['archive_storage_key']] = b'not a zip anymore'
    status_response = record_client.get(
        f'/api/archives/imports/{uploaded_job["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )
    report = status_response.json()['report_json']

    resolve_response = record_client.post(
        f'/api/archives/imports/{uploaded_job["id"]}/resolve',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'decisions': [
                {
                    'candidate_id': report['patients'][0]['candidate_id'],
                    'action': 'create',
                    'fio': report['patients'][0]['fio'],
                    'date_of_birth': report['patients'][0]['date_of_birth'],
                    'record_groups': [
                        {
                            'group_id': report['patients'][0]['record_groups'][0]['group_id'],
                            'action': 'create',
                            'record_type': 'lab_result',
                            'event_date': '2026-04-05',
                            'title': 'Импорт с битым архивом',
                        },
                    ],
                },
            ],
        },
    )

    body = resolve_response.json()
    assert resolve_response.status_code == 200
    assert body['status'] == 'completed_with_warnings'
    assert body['report_json']['records_created'] == 1
    assert body['report_json']['attachments_created'] == 0
    assert any('Archive became unreadable during resolve' in warning for warning in body['report_json']['warnings'])


@pytest.mark.critical
def test_import_job_suggests_exact_accessible_patient_match(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.infrastructure.adapters.queue.tasks.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-match@example.com')
    token = _login(record_client, 'import-match@example.com', TEST_DOCTOR_PASSWORD)
    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {token}'},
        json={
            'fio': 'Иванов Иван Иванович',
            'date_of_birth': '1980-01-02',
            'email': None,
            'phone': None,
        },
    )
    assert create_patient_response.status_code == 201
    existing_record = _create_record(
        record_client,
        token,
        UUID(create_patient_response.json()['id']),
        title='Импортированный анализ',
        record_type='lab_result',
        event_date='2026-04-05',
    )

    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('records.zip', _build_patient_archive_bytes(), 'application/zip')},
    )
    process_import_job(upload_response.json()['id'])
    status_response = record_client.get(
        f'/api/archives/imports/{upload_response.json()["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert upload_response.status_code == 201
    assert status_response.status_code == 200
    patient = status_response.json()['report_json']['patients'][0]
    exact_matches = [match for match in patient['existing_matches'] if match['match_type'] == 'exact']
    assert exact_matches[0]['id'] == create_patient_response.json()['id']
    duplicate_candidates = patient['record_groups'][0]['duplicate_candidates']
    assert duplicate_candidates[0]['record_id'] == existing_record['id']
    assert duplicate_candidates[0]['match_reason'] == 'same_date'


@pytest.mark.critical
def test_import_job_list_shows_own_jobs_and_admin_sees_all(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-list-a@example.com')
    _create_doctor(email='import-list-b@example.com')
    _create_admin(email='import-list-admin@example.com')
    token_a = _login(record_client, 'import-list-a@example.com', TEST_DOCTOR_PASSWORD)
    token_b = _login(record_client, 'import-list-b@example.com', TEST_DOCTOR_PASSWORD)
    admin_token = _login(record_client, 'import-list-admin@example.com', TEST_DOCTOR_PASSWORD)

    first_upload = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token_a}'},
        files={'file': ('first.zip', _build_patient_archive_bytes(), 'application/zip')},
    )
    second_upload = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token_b}'},
        files={'file': ('second.zip', _build_patient_archive_bytes(), 'application/zip')},
    )
    own_list = record_client.get('/api/archives/imports', headers={'Authorization': f'Bearer {token_a}'})
    admin_list = record_client.get('/api/archives/imports', headers={'Authorization': f'Bearer {admin_token}'})

    assert first_upload.status_code == 201
    assert second_upload.status_code == 201
    assert own_list.status_code == 200
    assert admin_list.status_code == 200
    assert [job['id'] for job in own_list.json()] == [first_upload.json()['id']]
    assert {job['id'] for job in admin_list.json()}.issuperset(
        {first_upload.json()['id'], second_upload.json()['id']},
    )


@pytest.mark.critical
def test_import_job_recovery_enqueues_queued_jobs(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    enqueued: list[str] = []

    class _TaskStub:
        @staticmethod
        def delay(job_id: str) -> None:
            enqueued.append(job_id)

    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    monkeypatch.setattr('app.infrastructure.adapters.queue.recover_import_jobs.process_import_job', _TaskStub)
    _create_doctor(email='import-recover@example.com')
    token = _login(record_client, 'import-recover@example.com', TEST_DOCTOR_PASSWORD)
    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('recover.zip', _build_patient_archive_bytes(), 'application/zip')},
    )

    recovered_count = enqueue_recoverable_import_jobs()

    assert upload_response.status_code == 201
    assert recovered_count == 1
    assert enqueued == [upload_response.json()['id']]


@pytest.mark.critical
def test_import_job_requires_zip_archive(record_client: TestClient) -> None:
    _create_doctor(email='import-invalid@example.com')
    token = _login(record_client, 'import-invalid@example.com', TEST_DOCTOR_PASSWORD)

    response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('records.txt', b'not a zip', 'text/plain')},
    )

    assert response.status_code == 422


@pytest.mark.critical
def test_import_job_extracts_dicom_metadata(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.infrastructure.adapters.queue.tasks.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-dicom@example.com')
    token = _login(record_client, 'import-dicom@example.com', TEST_DOCTOR_PASSWORD)

    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('dicom.zip', _build_dicom_archive_bytes(), 'application/zip')},
    )
    process_import_job(upload_response.json()['id'])
    status_response = record_client.get(
        f'/api/archives/imports/{upload_response.json()["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert upload_response.status_code == 201
    assert status_response.status_code == 200
    report = status_response.json()['report_json']
    patient = report['patients'][0]
    record_group = patient['record_groups'][0]
    dicom_metadata = record_group['payload_json']['dicom_metadata'][0]
    assert status_response.json()['status'] == 'needs_review'
    assert patient['fio'] == 'Petrov Petr Petrovich'
    assert patient['date_of_birth'] == '1975-05-06'
    assert record_group['event_date'] == '2026-04-07'
    assert record_group['record_type'] == 'exam_result'
    assert dicom_metadata['Modality'] == 'MR'
    assert dicom_metadata['StudyDescription'] == 'Brain MRI'


@pytest.mark.critical
def test_import_job_worker_marks_corrupted_zip_failed(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.infrastructure.adapters.queue.tasks.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.process_import_job.delay', lambda _: None)
    _create_doctor(email='import-broken@example.com')
    token = _login(record_client, 'import-broken@example.com', TEST_DOCTOR_PASSWORD)

    upload_response = record_client.post(
        '/api/archives/imports',
        headers={'Authorization': f'Bearer {token}'},
        files={'file': ('broken.zip', b'PKbroken', 'application/zip')},
    )
    process_import_job(upload_response.json()['id'])
    status_response = record_client.get(
        f'/api/archives/imports/{upload_response.json()["id"]}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert upload_response.status_code == 201
    assert status_response.status_code == 200
    assert status_response.json()['status'] == 'failed'
    assert status_response.json()['report_json']['errors']


@pytest.mark.critical
def test_doctor_can_attach_and_download_comment_file(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_patient(record_client, 'patient-att@example.com')
    patient_token = _login(record_client, 'patient-att@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient-att@example.com')
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
        json={'body': 'See attached lab result.'},
    )
    assert comment_response.status_code == 201
    comment_id = comment_response.json()['id']

    storage = _InMemoryStorage()
    monkeypatch.setattr(
        'app.presentation.rest.public.v1.records.dependencies.get_file_storage',
        lambda: storage,
    )

    upload_response = record_client.post(
        f'/api/records/{created_record["id"]}/comments/{comment_id}/attachments',
        headers={'Authorization': f'Bearer {doctor_token}'},
        files={'file': ('результат.pdf', b'PDF-bytes', 'application/pdf')},
    )

    assert upload_response.status_code == 201
    attachment = upload_response.json()
    assert attachment['comment_id'] == comment_id
    assert attachment['filename'] == 'результат.pdf'
    assert len(storage.objects) == 1

    detail = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {patient_token}'},
    )
    assert detail.status_code == 200
    comment_payload = detail.json()['comments'][0]
    assert len(comment_payload['attachments']) == 1
    assert comment_payload['attachments'][0]['filename'] == 'результат.pdf'
    assert detail.json()['attachments_count'] == 0

    download = record_client.get(
        f'/api/records/{created_record["id"]}/attachments/{attachment["id"]}',
        headers={'Authorization': f'Bearer {patient_token}'},
    )
    assert download.status_code == 200
    assert download.content == b'PDF-bytes'


@pytest.mark.critical
def test_patient_and_doctor_can_attach_files_to_record(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_patient(record_client, 'patient-recatt@example.com')
    patient_token = _login(record_client, 'patient-recatt@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient-recatt@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. Outside',
    )

    storage = _InMemoryStorage()
    monkeypatch.setattr(
        'app.presentation.rest.public.v1.records.dependencies.get_file_storage',
        lambda: storage,
    )

    patient_upload = record_client.post(
        f'/api/records/{created_record["id"]}/attachments',
        headers={'Authorization': f'Bearer {patient_token}'},
        files={'file': ('анализ.pdf', b'patient-bytes', 'application/pdf')},
    )
    assert patient_upload.status_code == 201
    assert patient_upload.json()['comment_id'] is None
    assert patient_upload.json()['filename'] == 'анализ.pdf'

    _create_doctor()
    doctor_token = _login(record_client, 'doctor@example.com', TEST_DOCTOR_PASSWORD)
    doctor = _get_user_by_email('doctor@example.com')
    _grant_record_access(doctor.id, UUID(created_record['id']), patient_passport_id)

    doctor_upload = record_client.post(
        f'/api/records/{created_record["id"]}/attachments',
        headers={'Authorization': f'Bearer {doctor_token}'},
        files={'file': ('снимок.png', b'doctor-bytes', 'image/png')},
    )
    assert doctor_upload.status_code == 201

    detail = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {patient_token}'},
    )
    assert detail.status_code == 200
    assert detail.json()['attachments_count'] == 2
    assert len(storage.objects) == 2


@pytest.mark.critical
def test_oversized_attachment_returns_413(
    record_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _register_patient(record_client, 'patient-big@example.com')
    patient_token = _login(record_client, 'patient-big@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient-big@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. Outside',
    )

    monkeypatch.setattr('app.presentation.rest.public.v1.records.router.MAX_ATTACHMENT_SIZE_BYTES', 4)

    response = record_client.post(
        f'/api/records/{created_record["id"]}/attachments',
        headers={'Authorization': f'Bearer {patient_token}'},
        files={'file': ('big.png', b'too-large-bytes', 'image/png')},
    )

    assert response.status_code == 413
    assert 'превышает' in response.json()['detail']


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


@pytest.mark.critical
def test_patient_can_list_own_patient_card_and_records(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient9@example.com')
    patient_token = _login(record_client, 'patient9@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient9@example.com')
    created_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Self record',
    )

    patients_response = record_client.get(
        '/api/patients',
        headers={'Authorization': f'Bearer {patient_token}'},
    )
    records_response = record_client.get(
        f'/api/patients/{patient_passport_id}/records',
        headers={'Authorization': f'Bearer {patient_token}'},
    )

    assert patients_response.status_code == 200
    assert len(patients_response.json()) == 1
    assert patients_response.json()[0]['id'] == str(patient_passport_id)
    assert patients_response.json()[0]['access_context'] == 'own_confirmed'
    assert patients_response.json()[0]['record_count'] == 1

    assert records_response.status_code == 200
    assert len(records_response.json()) == 1
    assert records_response.json()[0]['id'] == created_record['id']
    assert records_response.json()[0]['title'] == 'Self record'
    assert records_response.json()[0]['author_practitioner_passport']['full_name'] == 'Dr. External'


@pytest.mark.critical
def test_doctor_can_create_patient_card_and_see_patient_records(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient10@example.com')
    patient_token = _login(record_client, 'patient10@example.com', TEST_PATIENT_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('patient10@example.com')
    _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Visible record',
    )

    _create_doctor(email='doctor-list@example.com')
    doctor_token = _login(record_client, 'doctor-list@example.com', TEST_DOCTOR_PASSWORD)
    doctor = _get_user_by_email('doctor-list@example.com')
    with get_session_factory()() as session:
        record = session.scalar(
            select(MedicalRecordRow).where(MedicalRecordRow.title == 'Visible record'),
        )
        assert record is not None
    _grant_record_access(doctor.id, record.id, patient_passport_id)

    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json={
            'fio': 'Петров Пётр Петрович',
            'date_of_birth': '1985-07-01',
            'email': 'draft-patient@example.com',
            'phone': '+79995554433',
        },
    )
    list_patients_response = record_client.get(
        '/api/patients',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )
    patient_records_response = record_client.get(
        f'/api/patients/{patient_passport_id}/records',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )

    assert create_patient_response.status_code == 201
    assert create_patient_response.json()['fio'] == 'Петров Пётр Петрович'
    assert create_patient_response.json()['status'] == 'draft'
    assert create_patient_response.json()['access_context'] == 'created'

    assert list_patients_response.status_code == 200
    assert any(patient['id'] == create_patient_response.json()['id'] for patient in list_patients_response.json())
    assert any(patient['id'] == str(patient_passport_id) for patient in list_patients_response.json())

    assert patient_records_response.status_code == 200
    assert len(patient_records_response.json()) == 1
    assert patient_records_response.json()[0]['title'] == 'Visible record'
    assert patient_records_response.json()[0]['creator_user_id']
    assert patient_records_response.json()[0]['creator_fio'] == 'Ivan Ivanov'
    assert patient_records_response.json()[0]['created_at']


@pytest.mark.critical
def test_doctor_can_search_patient_passport_matches(record_client: TestClient) -> None:
    _create_doctor(email='doctor-search@example.com')
    doctor_token = _login(record_client, 'doctor-search@example.com', TEST_DOCTOR_PASSWORD)
    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json={
            'fio': 'Doctor Local Patient',
            'date_of_birth': '1988-02-01',
            'email': 'doctor-local-patient@example.com',
            'phone': '+79994445566',
        },
    )
    assert create_patient_response.status_code == 201

    search_response = record_client.get(
        '/api/patients/search',
        headers={'Authorization': f'Bearer {doctor_token}'},
        params={'q': 'Doctor Local Patien', 'date_of_birth': '1988-02-01'},
    )

    assert search_response.status_code == 200
    candidates = search_response.json()
    assert candidates[0]['patient']['id'] == create_patient_response.json()['id']
    assert candidates[0]['match_score'] >= 0.7


@pytest.mark.critical
def test_patient_cannot_search_patient_passports(record_client: TestClient) -> None:
    _register_patient(record_client, 'patient-search-forbidden@example.com')
    patient_token = _login(record_client, 'patient-search-forbidden@example.com', TEST_PATIENT_PASSWORD)

    response = record_client.get(
        '/api/patients/search',
        headers={'Authorization': f'Bearer {patient_token}'},
        params={'q': 'Ivan'},
    )

    assert response.status_code == 403


@pytest.mark.critical
def test_admin_can_create_staff_users(record_client: TestClient) -> None:
    _create_admin(email='staff-admin@example.com')
    admin_token = _login(record_client, 'staff-admin@example.com', TEST_DOCTOR_PASSWORD)

    doctor_response = record_client.post(
        '/api/admin/users',
        headers={'Authorization': f'Bearer {admin_token}'},
        json={
            'fio': 'Demo Doctor',
            'email': 'demo-doctor@example.com',
            'phone': '+79990001122',
            'password': TEST_DOCTOR_PASSWORD,
            'role': 'doctor',
        },
    )
    admin_response = record_client.post(
        '/api/admin/users',
        headers={'Authorization': f'Bearer {admin_token}'},
        json={
            'fio': 'Demo Admin',
            'email': 'demo-admin@example.com',
            'phone': '+79990001123',
            'password': TEST_DOCTOR_PASSWORD,
            'role': 'admin',
        },
    )

    assert doctor_response.status_code == 201
    assert doctor_response.json()['role'] == 'doctor'
    assert admin_response.status_code == 201
    assert admin_response.json()['role'] == 'admin'


@pytest.mark.critical
def test_only_admin_can_create_staff_users_and_email_must_be_unique(record_client: TestClient) -> None:
    _create_doctor(email='staff-doctor@example.com')
    _create_admin(email='staff-owner@example.com')
    doctor_token = _login(record_client, 'staff-doctor@example.com', TEST_DOCTOR_PASSWORD)
    admin_token = _login(record_client, 'staff-owner@example.com', TEST_DOCTOR_PASSWORD)
    payload = {
        'fio': 'Duplicate Staff',
        'email': 'duplicate-staff@example.com',
        'phone': '+79990001124',
        'password': TEST_DOCTOR_PASSWORD,
        'role': 'doctor',
    }

    forbidden_response = record_client.post(
        '/api/admin/users',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json=payload,
    )
    first_response = record_client.post(
        '/api/admin/users',
        headers={'Authorization': f'Bearer {admin_token}'},
        json=payload,
    )
    duplicate_response = record_client.post(
        '/api/admin/users',
        headers={'Authorization': f'Bearer {admin_token}'},
        json=payload,
    )

    assert forbidden_response.status_code == 403
    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409


@pytest.mark.critical
def test_doctor_created_empty_patient_card_is_not_visible_to_other_doctor(record_client: TestClient) -> None:
    _create_doctor(email='doctor-card-owner@example.com')
    _create_doctor(email='doctor-card-stranger@example.com')
    owner_token = _login(record_client, 'doctor-card-owner@example.com', TEST_DOCTOR_PASSWORD)
    stranger_token = _login(record_client, 'doctor-card-stranger@example.com', TEST_DOCTOR_PASSWORD)

    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {owner_token}'},
        json={
            'fio': 'Local Draft Patient',
            'date_of_birth': '1977-04-01',
            'email': 'local-draft-patient@example.com',
            'phone': '+79995550011',
        },
    )
    patient_id = create_patient_response.json()['id']

    owner_patients_response = record_client.get('/api/patients', headers={'Authorization': f'Bearer {owner_token}'})
    stranger_patients_response = record_client.get(
        '/api/patients', headers={'Authorization': f'Bearer {stranger_token}'}
    )
    stranger_patient_response = record_client.get(
        f'/api/patients/{patient_id}',
        headers={'Authorization': f'Bearer {stranger_token}'},
    )

    assert create_patient_response.status_code == 201
    assert create_patient_response.json()['access_context'] == 'created'
    assert any(patient['id'] == patient_id for patient in owner_patients_response.json())
    assert all(patient['id'] != patient_id for patient in stranger_patients_response.json())
    assert stranger_patient_response.status_code == 404


@pytest.mark.critical
def test_share_request_accept_grants_record_access_to_registered_user(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner@example.com')
    _register_patient(record_client, 'share-recipient@example.com', fio='Recipient Patient')
    owner_token = _login(record_client, 'share-owner@example.com', TEST_PATIENT_PASSWORD)
    recipient_token = _login(record_client, 'share-recipient@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner@example.com')
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Shared record',
    )

    before_accept_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    share_response = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient@example.com',
        record_ids=[created_record['id']],
    )
    inbox_response = record_client.get(
        '/api/share-requests/inbox',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    outbox_response = record_client.get(
        '/api/share-requests/outbox',
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    accept_response = record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    after_accept_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    recipient_patients_response = record_client.get(
        '/api/patients',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    recipient_patient_records_response = record_client.get(
        f'/api/patients/{owner_passport_id}/records',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    patient_comment_response = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {recipient_token}'},
        json={'body': 'Patient should not be allowed to comment.'},
    )

    assert before_accept_response.status_code == 403
    assert inbox_response.status_code == 200
    assert inbox_response.json()[0]['id'] == share_response['request']['id']
    inbox_share = inbox_response.json()[0]['shares'][0]
    assert inbox_share['record_id'] == created_record['id']
    assert inbox_share['title'] == 'Shared record'
    assert inbox_share['record_type'] == 'consultation_result'
    assert inbox_share['event_date'] == '2026-03-11'
    assert inbox_share['patient_fio'] == 'Ivan Ivanov'
    assert inbox_share['patient_passport_id'] == str(owner_passport_id)
    assert inbox_share['attachments_count'] == 0
    assert inbox_share['comments_count'] == 0
    assert outbox_response.status_code == 200
    assert outbox_response.json()[0]['shares'][0]['title'] == 'Shared record'
    assert accept_response.status_code == 200
    assert accept_response.json()['status'] == 'accepted'
    assert accept_response.json()['shares'][0]['status'] == 'accepted'
    assert after_accept_response.status_code == 200
    assert after_accept_response.json()['id'] == created_record['id']
    assert recipient_patients_response.status_code == 200
    recipient_patient = next(
        patient for patient in recipient_patients_response.json() if patient['id'] == str(owner_passport_id)
    )
    assert recipient_patient['access_context'] == 'shared'
    assert recipient_patient_records_response.status_code == 200
    assert [record['id'] for record in recipient_patient_records_response.json()] == [created_record['id']]
    assert patient_comment_response.status_code == 403

    recipient = _get_user_by_email('share-recipient@example.com')
    with get_session_factory()() as session:
        link = session.scalar(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == recipient.id,
                UserRecordLinkRow.record_id == UUID(created_record['id']),
                UserRecordLinkRow.source == UserRecordLinkSourceRow.SHARE_ACCEPTED,
            ),
        )
        audit_events = session.scalars(
            select(AuditEventRow.event_type).where(AuditEventRow.entity_id == UUID(share_response['request']['id'])),
        ).all()
    assert link is not None
    assert link.source_record_share_id == UUID(accept_response.json()['shares'][0]['id'])
    assert {'share', 'accept'}.issubset(set(audit_events))


@pytest.mark.critical
def test_expired_share_access_is_not_usable(record_client: TestClient) -> None:
    _register_patient(record_client, 'expiring-owner@example.com')
    _register_patient(record_client, 'expiring-recipient@example.com', fio='Expiring Recipient')
    owner_token = _login(record_client, 'expiring-owner@example.com', TEST_PATIENT_PASSWORD)
    recipient_token = _login(record_client, 'expiring-recipient@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('expiring-owner@example.com')
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. Expiration',
        title='Expiring shared record',
    )

    share_response = _create_share_request(
        record_client,
        owner_token,
        to_user_email='expiring-recipient@example.com',
        record_ids=[created_record['id']],
        expires_at='2099-01-02',
    )
    accept_response = record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    active_record_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )

    assert share_response['request']['expires_at'] is not None
    assert accept_response.status_code == 200
    assert active_record_response.status_code == 200

    recipient = _get_user_by_email('expiring-recipient@example.com')
    expired_at = datetime(2020, 1, 1, tzinfo=UTC)
    with get_session_factory()() as session:
        request_row = session.get(RecordShareRequestRow, UUID(share_response['request']['id']))
        link = session.scalar(
            select(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == recipient.id,
                UserRecordLinkRow.record_id == UUID(created_record['id']),
                UserRecordLinkRow.source == UserRecordLinkSourceRow.SHARE_ACCEPTED,
            ),
        )
        assert request_row is not None
        assert link is not None
        assert link.expires_at is not None
        request_row.expires_at = expired_at
        link.expires_at = expired_at
        session.commit()

    expired_record_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    expired_patients_response = record_client.get(
        '/api/patients',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )

    assert expired_record_response.status_code == 403
    assert expired_patients_response.status_code == 200
    assert all(patient['id'] != str(owner_passport_id) for patient in expired_patients_response.json())


@pytest.mark.critical
def test_share_recipient_search_finds_active_users_by_email_or_fio(record_client: TestClient) -> None:
    _register_patient(record_client, 'recipient-search-owner@example.com', fio='Search Owner')
    _register_patient(record_client, 'recipient-search-patient@example.com', fio='Recipient Search Patient')
    _create_doctor(email='recipient-search-doctor@example.com')
    _create_user(
        email='recipient-search-blocked@example.com',
        password=TEST_PATIENT_PASSWORD,
        role=UserRole.PATIENT,
        fio='Blocked Recipient',
    )
    with get_session_factory()() as session:
        blocked_user = session.scalar(select(UserRow).where(UserRow.email == 'recipient-search-blocked@example.com'))
        assert blocked_user is not None
        blocked_user.status = UserStatus.BLOCKED
        session.commit()

    owner_token = _login(record_client, 'recipient-search-owner@example.com', TEST_PATIENT_PASSWORD)

    fio_response = record_client.get(
        '/api/share-requests/recipients',
        headers={'Authorization': f'Bearer {owner_token}'},
        params={'q': 'Recipient Search'},
    )
    email_response = record_client.get(
        '/api/share-requests/recipients',
        headers={'Authorization': f'Bearer {owner_token}'},
        params={'q': 'recipient-search-doctor'},
    )
    self_response = record_client.get(
        '/api/share-requests/recipients',
        headers={'Authorization': f'Bearer {owner_token}'},
        params={'q': 'Search Owner'},
    )
    blocked_response = record_client.get(
        '/api/share-requests/recipients',
        headers={'Authorization': f'Bearer {owner_token}'},
        params={'q': 'Blocked Recipient'},
    )

    assert fio_response.status_code == 200
    assert [user['email'] for user in fio_response.json()] == ['recipient-search-patient@example.com']
    assert email_response.status_code == 200
    assert [user['email'] for user in email_response.json()] == ['recipient-search-doctor@example.com']
    assert self_response.status_code == 200
    assert self_response.json() == []
    assert blocked_response.status_code == 200
    assert blocked_response.json() == []


@pytest.mark.critical
def test_record_confirmation_rules_and_share_auto_confirm(record_client: TestClient) -> None:
    _register_patient(record_client, 'confirm-patient@example.com', fio='Confirm Patient')
    _create_doctor(email='confirm-doctor@example.com')
    patient_token = _login(record_client, 'confirm-patient@example.com', TEST_PATIENT_PASSWORD)
    doctor_token = _login(record_client, 'confirm-doctor@example.com', TEST_DOCTOR_PASSWORD)
    patient_passport_id = _get_patient_passport_id_by_email('confirm-patient@example.com')

    patient_record = _create_record(
        record_client,
        patient_token,
        patient_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Patient-created unconfirmed record',
    )
    patient_to_doctor_share = _create_share_request(
        record_client,
        patient_token,
        to_user_email='confirm-doctor@example.com',
        record_ids=[patient_record['id']],
    )
    accept_patient_record_response = record_client.post(
        f'/api/share-requests/{patient_to_doctor_share["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )
    confirm_patient_record_response = record_client.post(
        f'/api/records/{patient_record["id"]}/confirm',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )
    repeat_confirm_response = record_client.post(
        f'/api/records/{patient_record["id"]}/confirm',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )

    doctor_record = _create_record(
        record_client,
        doctor_token,
        patient_passport_id,
        title='Doctor-created unconfirmed record',
    )
    doctor_to_patient_share = _create_share_request(
        record_client,
        doctor_token,
        to_user_email='confirm-patient@example.com',
        record_ids=[doctor_record['id']],
    )
    accept_doctor_record_response = record_client.post(
        f'/api/share-requests/{doctor_to_patient_share["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {patient_token}'},
    )

    assert accept_patient_record_response.status_code == 200
    assert confirm_patient_record_response.status_code == 200
    assert confirm_patient_record_response.json()['status'] == 'confirmed'
    assert confirm_patient_record_response.json()['confirmed_by_user_id'] == str(
        _get_user_by_email('confirm-doctor@example.com').id,
    )
    assert confirm_patient_record_response.json()['confirmed_at'] is not None
    assert repeat_confirm_response.status_code == 422
    assert doctor_record['status'] == 'unconfirmed'
    assert accept_doctor_record_response.status_code == 200

    with get_session_factory()() as session:
        confirmed_doctor_record = session.get(MedicalRecordRow, UUID(doctor_record['id']))
    assert confirmed_doctor_record is not None
    assert confirmed_doctor_record.status.value == 'confirmed'
    assert confirmed_doctor_record.confirmed_by_user_id == _get_user_by_email('confirm-patient@example.com').id
    assert confirmed_doctor_record.confirmed_at is not None


@pytest.mark.critical
def test_doctor_patient_doctor_share_chain_preserves_creator(record_client: TestClient) -> None:
    _create_doctor(email='chain-doctor-a@example.com')
    _create_doctor(email='chain-doctor-b@example.com')
    _register_patient(record_client, 'chain-patient@example.com', fio='Chain Patient')
    doctor_a_token = _login(record_client, 'chain-doctor-a@example.com', TEST_DOCTOR_PASSWORD)
    doctor_b_token = _login(record_client, 'chain-doctor-b@example.com', TEST_DOCTOR_PASSWORD)
    patient_token = _login(record_client, 'chain-patient@example.com', TEST_PATIENT_PASSWORD)

    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {doctor_a_token}'},
        json={
            'fio': 'Doctor A Local Patient',
            'date_of_birth': '1991-05-01',
            'email': 'doctor-a-local-patient@example.com',
            'phone': '+79990004455',
        },
    )
    assert create_patient_response.status_code == 201
    local_patient_id = UUID(create_patient_response.json()['id'])
    record = _create_record(
        record_client,
        doctor_a_token,
        local_patient_id,
        title='Chain source record',
    )
    doctor_a = _get_user_by_email('chain-doctor-a@example.com')

    doctor_to_patient_share = _create_share_request(
        record_client,
        doctor_a_token,
        to_user_email='chain-patient@example.com',
        record_ids=[record['id']],
    )
    patient_accept_response = record_client.post(
        f'/api/share-requests/{doctor_to_patient_share["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {patient_token}'},
    )
    patient_record_response = record_client.get(
        f'/api/records/{record["id"]}',
        headers={'Authorization': f'Bearer {patient_token}'},
    )
    patient_to_doctor_share = _create_share_request(
        record_client,
        patient_token,
        to_user_email='chain-doctor-b@example.com',
        record_ids=[record['id']],
    )
    doctor_b_accept_response = record_client.post(
        f'/api/share-requests/{patient_to_doctor_share["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {doctor_b_token}'},
    )
    doctor_b_record_response = record_client.get(
        f'/api/records/{record["id"]}',
        headers={'Authorization': f'Bearer {doctor_b_token}'},
    )
    doctor_b_patients_response = record_client.get(
        '/api/patients',
        headers={'Authorization': f'Bearer {doctor_b_token}'},
    )

    assert patient_accept_response.status_code == 200
    assert patient_record_response.status_code == 200
    assert doctor_b_accept_response.status_code == 200
    assert doctor_b_record_response.status_code == 200
    assert doctor_b_record_response.json()['creator_user_id'] == str(doctor_a.id)
    assert doctor_b_record_response.json()['patient_passport_id'] == str(local_patient_id)
    assert any(patient['id'] == str(local_patient_id) for patient in doctor_b_patients_response.json())


@pytest.mark.critical
def test_doctor_patient_share_comment_and_revoke_flow_for_foreign_patient_card(record_client: TestClient) -> None:
    _create_doctor(email='flow-doctor@example.com')
    _register_patient(record_client, 'flow-recipient@example.com', fio='Recipient Patient')
    doctor_token = _login(record_client, 'flow-doctor@example.com', TEST_DOCTOR_PASSWORD)
    recipient_token = _login(record_client, 'flow-recipient@example.com', TEST_PATIENT_PASSWORD)

    create_patient_response = record_client.post(
        '/api/patients',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json={
            'fio': 'Shared Foreign Patient',
            'date_of_birth': '1991-05-12',
            'email': 'shared-foreign-patient@example.com',
            'phone': '+79995550123',
        },
    )
    assert create_patient_response.status_code == 201
    foreign_patient_id = create_patient_response.json()['id']

    created_record = _create_record(
        record_client,
        doctor_token,
        UUID(foreign_patient_id),
        title='Doctor owned shared record',
        clinical_summary='Shared context summary.',
    )
    share_response = _create_share_request(
        record_client,
        doctor_token,
        to_user_email='flow-recipient@example.com',
        record_ids=[created_record['id']],
    )
    accept_response = record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    recipient_patients_response = record_client.get(
        '/api/patients', headers={'Authorization': f'Bearer {recipient_token}'}
    )
    recipient_foreign_records_response = record_client.get(
        f'/api/patients/{foreign_patient_id}/records',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    comment_response = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json={'body': 'Doctor follow-up comment.'},
    )
    recipient_record_detail_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    revoke_response = record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/revoke',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )
    recipient_after_revoke_patients_response = record_client.get(
        '/api/patients',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    recipient_after_revoke_record_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )

    assert accept_response.status_code == 200
    shared_patient = next(
        patient for patient in recipient_patients_response.json() if patient['id'] == foreign_patient_id
    )
    assert shared_patient['access_context'] == 'shared'
    assert recipient_foreign_records_response.status_code == 200
    assert [record['id'] for record in recipient_foreign_records_response.json()] == [created_record['id']]
    assert comment_response.status_code == 201
    assert recipient_record_detail_response.status_code == 200
    assert recipient_record_detail_response.json()['comments'][0]['body'] == 'Doctor follow-up comment.'
    assert revoke_response.status_code == 200
    assert all(patient['id'] != foreign_patient_id for patient in recipient_after_revoke_patients_response.json())
    assert recipient_after_revoke_record_response.status_code == 403


@pytest.mark.critical
def test_declined_or_cancelled_share_request_does_not_grant_access(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner-2@example.com')
    _register_patient(record_client, 'share-recipient-2@example.com', fio='Recipient Patient')
    owner_token = _login(record_client, 'share-owner-2@example.com', TEST_PATIENT_PASSWORD)
    recipient_token = _login(record_client, 'share-recipient-2@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner-2@example.com')
    declined_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Declined record',
    )
    cancelled_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Cancelled record',
    )

    declined_share = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient-2@example.com',
        record_ids=[declined_record['id']],
    )
    decline_response = record_client.post(
        f'/api/share-requests/{declined_share["request"]["id"]}/decline',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    cancelled_share = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient-2@example.com',
        record_ids=[cancelled_record['id']],
    )
    cancel_response = record_client.post(
        f'/api/share-requests/{cancelled_share["request"]["id"]}/cancel',
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    accept_cancelled_response = record_client.post(
        f'/api/share-requests/{cancelled_share["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )

    declined_record_response = record_client.get(
        f'/api/records/{declined_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    cancelled_record_response = record_client.get(
        f'/api/records/{cancelled_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )

    assert decline_response.status_code == 200
    assert decline_response.json()['status'] == 'declined'
    assert cancel_response.status_code == 200
    assert cancel_response.json()['status'] == 'cancelled'
    assert accept_cancelled_response.status_code == 403
    assert declined_record_response.status_code == 403
    assert cancelled_record_response.status_code == 403


@pytest.mark.critical
def test_revoke_accepted_share_removes_record_access(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner-3@example.com')
    _register_patient(record_client, 'share-recipient-3@example.com', fio='Recipient Patient')
    owner_token = _login(record_client, 'share-owner-3@example.com', TEST_PATIENT_PASSWORD)
    recipient_token = _login(record_client, 'share-recipient-3@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner-3@example.com')
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Revoked record',
    )

    share_response = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient-3@example.com',
        record_ids=[created_record['id']],
    )
    accept_response = record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    visible_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    revoke_response = record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/revoke',
        headers={'Authorization': f'Bearer {owner_token}'},
    )
    revoked_access_response = record_client.get(
        f'/api/records/{created_record["id"]}',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )

    assert accept_response.status_code == 200
    assert visible_response.status_code == 200
    assert revoke_response.status_code == 200
    assert revoke_response.json()['status'] == 'revoked'
    assert revoke_response.json()['shares'][0]['status'] == 'revoked'
    assert revoked_access_response.status_code == 403


@pytest.mark.critical
def test_duplicate_share_records_are_skipped(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner-4@example.com')
    _register_patient(record_client, 'share-recipient-4@example.com', fio='Recipient Patient')
    owner_token = _login(record_client, 'share-owner-4@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner-4@example.com')
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Duplicate shared record',
    )

    first_share = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient-4@example.com',
        record_ids=[created_record['id']],
    )
    second_share = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient-4@example.com',
        record_ids=[created_record['id']],
    )

    assert first_share['request'] is not None
    assert second_share['request'] is None
    assert second_share['skipped_record_ids'] == [created_record['id']]

    with get_session_factory()() as session:
        shares_count = len(
            session.scalars(
                select(RecordShareRow).where(RecordShareRow.record_id == UUID(created_record['id'])),
            ).all(),
        )
        request_count = len(session.scalars(select(RecordShareRequestRow)).all())

    assert shares_count == 1
    assert request_count == 1


@pytest.mark.critical
def test_doctor_recipient_can_comment_after_accepting_share(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner-5@example.com')
    owner_token = _login(record_client, 'share-owner-5@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner-5@example.com')
    _create_doctor(email='share-doctor@example.com')
    doctor_token = _login(record_client, 'share-doctor@example.com', TEST_DOCTOR_PASSWORD)
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Doctor shared record',
    )

    share_response = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-doctor@example.com',
        record_ids=[created_record['id']],
    )
    record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {doctor_token}'},
    )
    comment_response = record_client.post(
        f'/api/records/{created_record["id"]}/comments',
        headers={'Authorization': f'Bearer {doctor_token}'},
        json={'body': 'Doctor can comment after accepting share.'},
    )

    assert comment_response.status_code == 201


@pytest.mark.critical
def test_invalid_share_targets_and_records_are_rejected(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner-6@example.com')
    owner_token = _login(record_client, 'share-owner-6@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner-6@example.com')
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Invalid share target record',
    )
    _register_patient(record_client, 'share-other@example.com', fio='Other Patient')
    other_token = _login(record_client, 'share-other@example.com', TEST_PATIENT_PASSWORD)

    self_share_response = record_client.post(
        '/api/share-requests',
        headers={'Authorization': f'Bearer {owner_token}'},
        json={'to_user_email': 'share-owner-6@example.com', 'record_ids': [created_record['id']]},
    )
    missing_user_response = record_client.post(
        '/api/share-requests',
        headers={'Authorization': f'Bearer {owner_token}'},
        json={'to_user_email': 'missing-user@example.com', 'record_ids': [created_record['id']]},
    )
    inaccessible_record_response = record_client.post(
        '/api/share-requests',
        headers={'Authorization': f'Bearer {other_token}'},
        json={'to_user_email': 'share-owner-6@example.com', 'record_ids': [created_record['id']]},
    )

    assert self_share_response.status_code == 403
    assert missing_user_response.status_code == 404
    assert inaccessible_record_response.status_code == 403


@pytest.mark.critical
def test_share_statuses_are_persisted_for_audit(record_client: TestClient) -> None:
    _register_patient(record_client, 'share-owner-7@example.com')
    _register_patient(record_client, 'share-recipient-7@example.com', fio='Recipient Patient')
    owner_token = _login(record_client, 'share-owner-7@example.com', TEST_PATIENT_PASSWORD)
    recipient_token = _login(record_client, 'share-recipient-7@example.com', TEST_PATIENT_PASSWORD)
    owner_passport_id = _get_patient_passport_id_by_email('share-owner-7@example.com')
    created_record = _create_record(
        record_client,
        owner_token,
        owner_passport_id,
        author_practitioner_full_name='Dr. External',
        title='Audit shared record',
    )

    share_response = _create_share_request(
        record_client,
        owner_token,
        to_user_email='share-recipient-7@example.com',
        record_ids=[created_record['id']],
    )
    record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/accept',
        headers={'Authorization': f'Bearer {recipient_token}'},
    )
    record_client.post(
        f'/api/share-requests/{share_response["request"]["id"]}/revoke',
        headers={'Authorization': f'Bearer {owner_token}'},
    )

    with get_session_factory()() as session:
        request_row = session.get(RecordShareRequestRow, UUID(share_response['request']['id']))
        share_row = session.scalar(
            select(RecordShareRow).where(RecordShareRow.request_id == UUID(share_response['request']['id'])),
        )

    assert request_row is not None
    assert request_row.status == RecordShareStatusRow.REVOKED
    assert request_row.revoked_at is not None
    assert share_row is not None
    assert share_row.status == RecordShareStatusRow.REVOKED
    assert share_row.responded_at is not None
    assert share_row.revoked_at is not None
