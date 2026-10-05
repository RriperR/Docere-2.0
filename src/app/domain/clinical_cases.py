"""Инварианты совместного клинического разбора."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


class CaseError(Exception):
    """Ошибка сценария с безопасным для пользователя сообщением."""

    def __init__(self, message: str, status: int = 409) -> None:
        """Инициализировать зависимости сценария."""
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

        Returns:
            Результат операции в контексте доступа текущего пользователя.
        """
        return next((item for item in self.members if item.user_id == user_id), None)

    def require_coordinator(self, user_id: UUID) -> None:
        """Запретить административное действие другому участнику.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if user_id != self.coordinator_id:
            raise CaseError('Действие доступно только координатору', 403)

    def require_writable(self) -> None:
        """Запретить изменение завершённого разбора.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if self.status == 'closed':
            raise CaseError('Разбор завершён и доступен только для чтения')

    def check_version(self, version: int) -> None:
        """Отклонить изменение устаревшей версии.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if version != self.version:
            raise CaseError('Случай изменился. Обновите данные')
