"""Входные контракты клинических случаев."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CaseCreateSchema(BaseModel):
    """Черновик и выбранные записи одного пациента."""

    patient_id: UUID
    title: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=10000)
    record_ids: list[UUID] = Field(default_factory=list, max_length=100)
    previous_case_id: UUID | None = None

    @field_validator('title', 'question')
    @classmethod
    def nonblank(cls, value: str) -> str:
        """Отклонить пустой текст, состоящий из пробелов.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            ValueError: При нарушении условий операции.
        """
        if not value.strip():
            raise ValueError('Введите текст')
        return value.strip()


class DraftSchema(BaseModel):
    """Редактирование черновика с проверкой версии."""

    version: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    question: str = Field(min_length=1, max_length=10000)
    record_ids: list[UUID] = Field(max_length=100)


class MaterialsSchema(BaseModel):
    """Добавление материалов с optimistic concurrency."""

    version: int = Field(ge=1)
    record_ids: list[UUID] = Field(min_length=1, max_length=100)


class InviteSchema(BaseModel):
    """Приглашение зарегистрированному врачу."""

    version: int = Field(ge=1)
    user_id: UUID
