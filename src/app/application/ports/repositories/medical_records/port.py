"""Контракт репозитория медицинских записей."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.domain.entities.patient_passport import PatientPassport
from app.domain.entities.practitioner_passport import PractitionerPassport
from app.domain.entities.record_comment import RecordComment


class MedicalRecordRepositoryPort:
    """Порт для создания и чтения медицинских записей и связанных сущностей."""

    def get_patient_passport(self, patient_passport_id: UUID) -> PatientPassport | None:
        """Вернуть паспорт пациента по идентификатору."""
        raise NotImplementedError

    def user_can_access_patient_passport(
        self,
        *,
        user_id: UUID,
        user_role: str,
        patient_passport_id: UUID,
    ) -> bool:
        """РџСЂРѕРІРµСЂРёС‚СЊ РґРѕСЃС‚СѓРї РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Рє РїР°СЃРїРѕСЂС‚Сѓ РїР°С†РёРµРЅС‚Р°."""
        raise NotImplementedError

    def get_practitioner_passport(self, practitioner_passport_id: UUID) -> PractitionerPassport | None:
        """Вернуть паспорт врача по идентификатору."""
        raise NotImplementedError

    def get_or_create_practitioner_passport_for_user(
        self,
        user_id: UUID,
        full_name: str,
        email: str | None,
        phone: str | None,
    ) -> PractitionerPassport:
        """Вернуть паспорт внутреннего врача, создав его при необходимости."""
        raise NotImplementedError

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
        """Создать паспорт внешнего врача."""
        raise NotImplementedError

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
        """Создать медицинскую запись и вернуть ее доступную проекцию."""
        raise NotImplementedError

    def get_accessible_record(
        self,
        record_id: UUID,
        user_id: UUID,
    ) -> AccessibleMedicalRecordDTO | None:
        """Вернуть медицинскую запись, если у пользователя есть ссылка доступа."""
        raise NotImplementedError

    def add_comment(
        self,
        record_id: UUID,
        author_user_id: UUID,
        author_fio: str,
        author_role: str,
        body: str,
    ) -> RecordComment:
        """Добавить комментарий к медицинской записи."""
        raise NotImplementedError

    def record_exists(self, record_id: UUID) -> bool:
        """Проверить существование медицинской записи."""
        raise NotImplementedError
