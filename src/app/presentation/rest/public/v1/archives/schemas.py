"""Pydantic-схемы REST-эндпоинтов архивов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.presentation.rest.serialization import MoscowDatetime


class ImportFileDraftSchema(BaseModel):
    """Файл-кандидат из отчёта импорта."""

    path: str
    filename: str
    mime_type: str
    size_bytes: int
    is_dicom: bool = False


class ImportPatientMatchSchema(BaseModel):
    """Найденное совпадение пациента для отчёта импорта."""

    id: str
    fio: str
    date_of_birth: date | None = None
    status: str
    match_score: float
    match_type: str = Field(pattern='^(exact|fuzzy)$')


class ImportDuplicateRecordSchema(BaseModel):
    """Похожая существующая запись пациента."""

    record_id: UUID
    patient_passport_id: UUID
    title: str | None = None
    record_type: str
    event_date: date
    status: str
    match_reason: str


class ImportRecordGroupDraftSchema(BaseModel):
    """Группа файлов, из которой можно создать медицинскую запись."""

    group_id: str
    record_type: str = Field(pattern='^(consultation_result|exam_result|lab_result|other)$')
    event_date: date | None = None
    event_date_candidates: list[date] = Field(default_factory=list)
    title: str
    payload_json: dict[str, object] = Field(default_factory=dict)
    files: list[ImportFileDraftSchema] = Field(default_factory=list)
    duplicate_candidates: list[ImportDuplicateRecordSchema] = Field(default_factory=list)


class ImportPatientDraftSchema(BaseModel):
    """Пациент-кандидат из отчёта импорта."""

    candidate_id: str
    fio: str | None = None
    date_of_birth: date | None = None
    sources: list[str] = Field(default_factory=list)
    existing_matches: list[ImportPatientMatchSchema] = Field(default_factory=list)
    record_groups: list[ImportRecordGroupDraftSchema] = Field(default_factory=list)


class ImportReportSchema(BaseModel):
    """Типизированный отчёт ImportJob."""

    message: str | None = None
    source_archive: str | None = None
    patients: list[ImportPatientDraftSchema] = Field(default_factory=list)
    files_total: int | None = None
    warnings: list[str] = Field(default_factory=list)
    skipped_files: int | None = None
    patients_created: int | None = None
    records_created: int | None = None
    attachments_created: int | None = None
    errors: list[str] = Field(default_factory=list)
    duplicate_overrides: list[dict[str, object]] = Field(default_factory=list)
    resolved_at: date | None = None


class ImportRecordGroupResolveSchema(BaseModel):
    """Решение пользователя по группе файлов импортируемой записи."""

    group_id: str
    action: str = Field(pattern='^(create|skip)$')
    record_type: str | None = Field(default=None, pattern='^(consultation_result|exam_result|lab_result|other)$')
    event_date: date | None = None
    title: str | None = Field(default=None, max_length=255)
    allow_possible_duplicate: bool = False

    @model_validator(mode='before')
    @classmethod
    def accept_legacy_duplicate_confirmation(cls, value: object) -> object:
        """Принять прежнее имя override-флага без возврата его в API.

        Returns:
            Нормализованный вход с новым именем поля.
        """
        if not isinstance(value, dict):
            return value
        if 'allow_possible_duplicate' in value or 'duplicate_confirmed' not in value:
            return value
        return {**value, 'allow_possible_duplicate': value['duplicate_confirmed']}


class ImportPatientResolveSchema(BaseModel):
    """Решение пользователя по кандидату пациента из ImportJob."""

    candidate_id: str
    action: str = Field(pattern='^(existing|create|skip)$')
    patient_passport_id: UUID | None = None
    fio: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    record_groups: list[ImportRecordGroupResolveSchema] = Field(default_factory=list)


class ImportJobResponseSchema(BaseModel):
    """Схема ответа ImportJob."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by_user_id: UUID
    status: str
    original_filename: str | None
    archive_storage_key: str | None
    size_bytes: int | None
    report_json: ImportReportSchema
    review_decisions: list[ImportPatientResolveSchema] = Field(default_factory=list)
    review_updated_at: MoscowDatetime | None = None
    created_at: MoscowDatetime
    finished_at: MoscowDatetime | None


class ResolveImportJobRequestSchema(BaseModel):
    """Тело запроса финализации ImportJob после review."""

    decisions: list[ImportPatientResolveSchema] = Field(min_length=1)


class SaveImportReviewDraftRequestSchema(BaseModel):
    """Тело запроса сохранения промежуточных решений review."""

    decisions: list[ImportPatientResolveSchema] = Field(max_length=500)


class ImportReviewDraftResponseSchema(BaseModel):
    """Сохраненный серверный черновик review."""

    decisions: list[ImportPatientResolveSchema] = Field(default_factory=list)
    updated_at: MoscowDatetime | None = None
