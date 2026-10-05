"""Инварианты совместного клинического разбора."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


class CaseError(Exception):
    """Ошибка сценария с безопасным для пользователя сообщением."""

    def __init__(self, message: str, status: int = 409) -> None:
        """Сохранить безопасное сообщение и код ошибки для транспортной границы.

        Args:
            message: Безопасное сообщение об ошибке.
            status: Код ошибки для преобразования на границе HTTP API.
        """
        super().__init__(message)
        self.status = status


@dataclass
class CaseMember:
    """Приглашение и текущее участие врача."""

    user_id: UUID
    status: str = 'pending'
    name: str = ''
    share_request_id: UUID | None = None
    read_sequence: int = 0


@dataclass
class ClinicalCase:
    """Совместный разбор выбранных записей одного пациента."""

    id: UUID
    patient_id: UUID
    coordinator_id: UUID
    title: str
    question: str
    status: str = 'draft'
    version: int = 1
    previous_case_id: UUID | None = None
    record_ids: list[UUID] = field(default_factory=list)
    members: list[CaseMember] = field(default_factory=list)
    created_at: datetime | None = None
    sequence: int = 0
    published_record_id: UUID | None = None

    def member(self, user_id: UUID) -> CaseMember | None:
        """Найти участие пользователя в этом разборе.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Участие указанного пользователя либо None, если он не был приглашён.
        """
        return next((item for item in self.members if item.user_id == user_id), None)

    def require_coordinator(self, user_id: UUID) -> None:
        """Запретить административное действие другому участнику.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        if user_id != self.coordinator_id:
            raise CaseError('Действие доступно только координатору', 403)

    def require_writable(self) -> None:
        """Запретить изменение завершённого разбора.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        if self.status == 'closed':
            raise CaseError('Разбор завершён и доступен только для чтения')

    def check_version(self, version: int) -> None:
        """Отклонить изменение устаревшей версии.

        Args:
            version: Версия случая, прочитанная клиентом перед изменением.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        if version != self.version:
            raise CaseError('Случай изменился. Обновите данные')


@dataclass(frozen=True)
class CaseMessage:
    """Неизменяемое сообщение с одним уровнем ответов и ключом повтора."""

    id: UUID
    case_id: UUID
    author_id: UUID
    body: str
    idempotency_key: UUID
    sequence: int
    parent_id: UUID | None = None
    record_id: UUID | None = None
    attachment_id: UUID | None = None
    opinion_id: UUID | None = None
    created_at: datetime | None = None
    author_name: str = ''


@dataclass
class OpinionRequest:
    """Адресный запрос мнения внутри случая."""

    id: UUID
    case_id: UUID
    requester_id: UUID
    assignee_id: UUID
    question: str
    status: str = 'open'
    record_id: UUID | None = None
    reason: str | None = None
    response_message_id: UUID | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class CaseConclusion:
    """Неизменяемая версия итога без автоматического согласия участников."""

    id: UUID
    case_id: UUID
    number: int
    author_id: UUID
    summary: str
    findings: str
    next_actions: str
    source_ids: list[UUID]
    created_at: datetime | None = None
