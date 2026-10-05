"""Входные контракты клинических случаев."""

from datetime import date
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

        Args:
            value: Входной текст до удаления внешних пробелов.

        Returns:
            Текст без внешних пробелов.

        Raises:
            ValueError: Если текст пуст или состоит только из пробелов.
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

    @field_validator('title', 'question')
    @classmethod
    def nonblank(cls, value: str) -> str:
        """Отклонить пустое описание черновика.

        Args:
            value: Входной текст до удаления внешних пробелов.

        Returns:
            Текст без внешних пробелов.

        Raises:
            ValueError: Если текст пуст или состоит только из пробелов.
        """
        if not value.strip():
            raise ValueError('Введите текст')
        return value.strip()


class MaterialsSchema(BaseModel):
    """Добавление материалов с optimistic concurrency."""

    version: int = Field(ge=1)
    record_ids: list[UUID] = Field(min_length=1, max_length=100)


class InviteSchema(BaseModel):
    """Приглашение зарегистрированному врачу."""

    version: int = Field(ge=1)
    user_id: UUID


class MessageSchema(BaseModel):
    """Новая неизменяемая реплика или ответ."""

    body: str = Field(min_length=1, max_length=10000)
    idempotency_key: UUID
    parent_id: UUID | None = None
    record_id: UUID | None = None
    attachment_id: UUID | None = None
    opinion_id: UUID | None = None

    @field_validator('body')
    @classmethod
    def nonblank(cls, value: str) -> str:
        """Не принимать пустые реплики.

        Args:
            value: Входной текст до удаления внешних пробелов.

        Returns:
            Текст без внешних пробелов.

        Raises:
            ValueError: Если текст пуст или состоит только из пробелов.
        """
        if not value.strip():
            raise ValueError('Введите сообщение')
        return value.strip()


class OpinionSchema(BaseModel):
    """Вопрос конкретному участнику."""

    assignee_id: UUID
    question: str = Field(min_length=1, max_length=10000)
    record_id: UUID | None = None

    @field_validator('question')
    @classmethod
    def nonblank(cls, value: str) -> str:
        """Не принимать пустые вопросы.

        Args:
            value: Входной текст до удаления внешних пробелов.

        Returns:
            Текст без внешних пробелов.

        Raises:
            ValueError: Если текст пуст или состоит только из пробелов.
        """
        if not value.strip():
            raise ValueError('Введите вопрос')
        return value.strip()


class ConclusionSchema(BaseModel):
    """Новая версия итога и ссылки на использованные материалы."""

    version: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=10000)
    findings: str = Field(default='', max_length=10000)
    next_actions: str = Field(default='', max_length=10000)
    source_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator('summary')
    @classmethod
    def nonblank(cls, value: str) -> str:
        """Не принимать пустой итог.

        Args:
            value: Входной текст до удаления внешних пробелов.

        Returns:
            Текст без внешних пробелов.

        Raises:
            ValueError: Если текст пуст или состоит только из пробелов.
        """
        if not value.strip():
            raise ValueError('Введите резюме')
        return value.strip()


class CloseSchema(BaseModel):
    """Явное подтверждение отмены оставшихся запросов."""

    version: int = Field(ge=1)
    cancel_open_requests: bool = False


class PublishSchema(BaseModel):
    """Дата медицинского события не подменяется временем публикации."""

    event_date: date


class DiscussionReadSchema(BaseModel):
    """Позиция прочтения реплик, не связанная с приглашениями."""

    sequence: int = Field(ge=0)
