"""Сценарий создания медицинской записи."""

from __future__ import annotations

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.common.mappers import to_medical_record_dto
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordValidationError,
    PatientPassportNotFoundError,
    PractitionerPassportNotFoundError,
)


class CreateMedicalRecordUseCase:
    """Создать медицинскую запись и вернуть ее проекцию для автора."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use case репозиторием медицинских записей."""
        self._repository = repository

    def execute(self, input_dto: CreateMedicalRecordDTO) -> MedicalRecordDTO:
        """Создать медицинскую запись и определить ее врача-автора.

        Returns:
            Проекция созданной медицинской записи.

        Raises:
            MedicalRecordAccessDeniedError: Если роль или доступ к пациенту некорректны.
            MedicalRecordValidationError: Если не указаны данные врача-автора.
            PatientPassportNotFoundError: Если паспорт пациента не найден.
            PractitionerPassportNotFoundError: Если указанный паспорт врача не найден.
        """
        if input_dto.actor_role not in {'doctor', 'patient', 'admin'}:
            raise MedicalRecordAccessDeniedError

        patient_passport = self._repository.get_patient_passport(
            patient_passport_id=input_dto.patient_passport_id,
        )
        if patient_passport is None:
            raise PatientPassportNotFoundError

        if input_dto.actor_role == 'patient' and patient_passport.patient_user_id != input_dto.actor_user_id:
            raise MedicalRecordAccessDeniedError
        if input_dto.actor_role in {'doctor', 'admin'} and not self._repository.user_can_access_patient_passport(
            user_id=input_dto.actor_user_id,
            user_role=input_dto.actor_role,
            patient_passport_id=input_dto.patient_passport_id,
        ):
            raise MedicalRecordAccessDeniedError

        author_practitioner_passport = None
        if input_dto.author_practitioner_passport_id is not None:
            author_practitioner_passport = self._repository.get_practitioner_passport(
                practitioner_passport_id=input_dto.author_practitioner_passport_id,
            )
            if author_practitioner_passport is None:
                raise PractitionerPassportNotFoundError
        elif input_dto.actor_role == 'doctor':
            author_practitioner_passport = self._repository.get_or_create_practitioner_passport_for_user(
                user_id=input_dto.actor_user_id,
                full_name=input_dto.actor_fio,
                email=input_dto.actor_email,
                phone=input_dto.actor_phone,
            )
        elif input_dto.author_practitioner_full_name:
            author_practitioner_passport = self._repository.create_practitioner_passport(
                created_by_user_id=input_dto.actor_user_id,
                full_name=input_dto.author_practitioner_full_name,
                specialty=input_dto.author_practitioner_specialty,
                organization=input_dto.author_practitioner_organization,
                position=input_dto.author_practitioner_position,
                email=input_dto.author_practitioner_email,
                phone=input_dto.author_practitioner_phone,
            )
        else:
            raise MedicalRecordValidationError

        accessible_record = self._repository.create_record(
            creator_user_id=input_dto.actor_user_id,
            patient_passport_id=input_dto.patient_passport_id,
            author_practitioner_passport_id=(
                author_practitioner_passport.id if author_practitioner_passport is not None else None
            ),
            record_type=input_dto.record_type,
            event_date=input_dto.event_date,
            title=input_dto.title,
            appointment_location=input_dto.appointment_location,
            clinical_summary=input_dto.clinical_summary,
            payload_json=input_dto.payload_json,
        )
        return to_medical_record_dto(accessible_record)
