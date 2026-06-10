from __future__ import annotations

from datetime import date, datetime, UTC
from uuid import UUID, uuid4

import pytest

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.application.use_cases.medical_records.errors import MedicalRecordAccessDeniedError
from app.domain.entities.medical_record import MedicalRecord, MedicalRecordStatus, MedicalRecordType
from app.domain.entities.patient_passport import PatientPassport, PatientPassportStatus
from app.domain.entities.practitioner_passport import PractitionerPassport, PractitionerPassportStatus
from app.domain.entities.record_comment import RecordComment


class MedicalRecordRepositoryFake(MedicalRecordRepositoryPort):
    def __init__(self, *, patient_passport: PatientPassport, can_access_patient: bool) -> None:
        self.patient_passport = patient_passport
        self.can_access_patient = can_access_patient
        self.access_checks: list[tuple[UUID, str, UUID]] = []
        self.created_records: list[AccessibleMedicalRecordDTO] = []
        self.practitioner = PractitionerPassport(
            id=uuid4(),
            created_by_user_id=None,
            user_id=uuid4(),
            full_name='Doctor Example',
            specialty=None,
            organization=None,
            position=None,
            email='doctor@example.test',
            phone=None,
            status=PractitionerPassportStatus.CONFIRMED,
            confirmed_at=_now(),
            created_at=_now(),
            updated_at=_now(),
        )

    def get_patient_passport(self, patient_passport_id: UUID) -> PatientPassport | None:
        if patient_passport_id != self.patient_passport.id:
            return None
        return self.patient_passport

    def user_can_access_patient_passport(
        self,
        *,
        user_id: UUID,
        user_role: str,
        patient_passport_id: UUID,
    ) -> bool:
        self.access_checks.append((user_id, user_role, patient_passport_id))
        return self.can_access_patient

    def get_practitioner_passport(self, practitioner_passport_id: UUID) -> PractitionerPassport | None:
        raise AssertionError('unexpected practitioner lookup')

    def get_or_create_practitioner_passport_for_user(
        self,
        user_id: UUID,
        full_name: str,
        email: str | None,
        phone: str | None,
    ) -> PractitionerPassport:
        return PractitionerPassport(
            id=self.practitioner.id,
            created_by_user_id=None,
            user_id=user_id,
            full_name=full_name,
            specialty=self.practitioner.specialty,
            organization=self.practitioner.organization,
            position=self.practitioner.position,
            email=email,
            phone=phone,
            status=self.practitioner.status,
            confirmed_at=self.practitioner.confirmed_at,
            created_at=self.practitioner.created_at,
            updated_at=self.practitioner.updated_at,
        )

    def create_practitioner_passport(
        self,
        created_by_user_id: UUID,
        full_name: str,
        specialty: str | None,
        organization: str | None,
        position: str | None,
        email: str | None,
        phone: str | None,
    ) -> PractitionerPassport:
        raise AssertionError('unexpected external practitioner creation')

    def create_record(
        self,
        creator_user_id: UUID,
        patient_passport_id: UUID,
        author_practitioner_passport_id: UUID | None,
        record_type: str,
        event_date: date,
        title: str | None,
        appointment_location: str | None,
        clinical_summary: str | None,
        payload_json: dict[str, object],
    ) -> AccessibleMedicalRecordDTO:
        created_at = _now()
        accessible_record = AccessibleMedicalRecordDTO(
            record=MedicalRecord(
                id=uuid4(),
                creator_user_id=creator_user_id,
                author_practitioner_passport_id=author_practitioner_passport_id,
                status=MedicalRecordStatus.DRAFT,
                record_type=MedicalRecordType(record_type),
                event_date=event_date,
                title=title,
                appointment_location=appointment_location,
                clinical_summary=clinical_summary,
                payload_json=payload_json,
                created_at=created_at,
                updated_at=created_at,
            ),
            patient_passport_id=patient_passport_id,
            author_practitioner_passport=self.practitioner,
            comments=(),
            attachments=(),
        )
        self.created_records.append(accessible_record)
        return accessible_record

    def get_accessible_record(self, record_id: UUID, user_id: UUID) -> AccessibleMedicalRecordDTO | None:
        raise AssertionError('unexpected accessible record lookup')

    def add_comment(self, record_id: UUID, author_user_id: UUID, body: str) -> RecordComment:
        raise AssertionError('unexpected comment creation')

    def record_exists(self, record_id: UUID) -> bool:
        raise AssertionError('unexpected record existence check')


@pytest.mark.critical
def test_doctor_cannot_create_record_for_inaccessible_patient_card() -> None:
    doctor_id = uuid4()
    patient_passport = _patient_passport()
    repository = MedicalRecordRepositoryFake(patient_passport=patient_passport, can_access_patient=False)

    with pytest.raises(MedicalRecordAccessDeniedError):
        CreateMedicalRecordUseCase(repository).execute(
            _create_medical_record_input(actor_user_id=doctor_id, patient_passport_id=patient_passport.id),
        )

    assert repository.access_checks == [(doctor_id, 'doctor', patient_passport.id)]
    assert repository.created_records == []


@pytest.mark.critical
def test_doctor_can_create_record_for_accessible_patient_card() -> None:
    doctor_id = uuid4()
    patient_passport = _patient_passport()
    repository = MedicalRecordRepositoryFake(patient_passport=patient_passport, can_access_patient=True)

    record = CreateMedicalRecordUseCase(repository).execute(
        _create_medical_record_input(actor_user_id=doctor_id, patient_passport_id=patient_passport.id),
    )

    assert repository.access_checks == [(doctor_id, 'doctor', patient_passport.id)]
    assert len(repository.created_records) == 1
    assert record.creator_user_id == doctor_id
    assert record.patient_passport_id == patient_passport.id


def _patient_passport() -> PatientPassport:
    created_at = _now()
    return PatientPassport(
        id=uuid4(),
        created_by_user_id=uuid4(),
        patient_user_id=uuid4(),
        fio='Patient Example',
        date_of_birth=date(1990, 1, 1),
        email='patient@example.test',
        phone=None,
        status=PatientPassportStatus.CONFIRMED,
        confirmed_at=created_at,
        created_at=created_at,
        updated_at=created_at,
    )


def _create_medical_record_input(*, actor_user_id: UUID, patient_passport_id: UUID) -> CreateMedicalRecordDTO:
    return CreateMedicalRecordDTO(
        actor_user_id=actor_user_id,
        actor_role='doctor',
        actor_fio='Doctor Example',
        actor_email='doctor@example.test',
        actor_phone='',
        patient_passport_id=patient_passport_id,
        author_practitioner_passport_id=None,
        author_practitioner_full_name=None,
        author_practitioner_specialty=None,
        author_practitioner_organization=None,
        author_practitioner_position=None,
        author_practitioner_email=None,
        author_practitioner_phone=None,
        record_type=MedicalRecordType.CONSULTATION_RESULT.value,
        event_date=date(2026, 6, 10),
        title='Consultation',
        appointment_location=None,
        clinical_summary='Summary',
        payload_json={},
    )


def _now() -> datetime:
    return datetime.now(UTC)
