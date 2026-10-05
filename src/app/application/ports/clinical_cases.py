"""Порты хранения разбора и выдачи прав с происхождением."""

from typing import Protocol
from uuid import UUID

from app.domain.clinical_cases import ClinicalCase


class CaseRepositoryPort(Protocol):
    """Транзакционное хранилище клинических случаев."""

    def get(self, case_id: UUID, *, lock: bool = False) -> ClinicalCase | None:
        """Получить агрегат из хранилища."""
        ...

    def save(self, case: ClinicalCase) -> None:
        """Сохранить агрегат в текущей транзакции."""
        ...

    def list_for(
        self, user_id: UUID, *, scope: str, status: str | None, offset: int, limit: int
    ) -> tuple[list[ClinicalCase], int]:
        """Выбрать страницу случаев пользователя."""
        ...

    def is_doctor(self, user_id: UUID) -> bool:
        """Проверить действующую роль врача."""
        ...

    def doctor_name(self, user_id: UUID) -> str:
        """Получить имя врача."""
        ...

    def search_doctors(self, user_id: UUID, query: str) -> list[dict[str, str]]:
        """Найти активных врачей."""
        ...

    def grant(self, case: ClinicalCase, user_id: UUID) -> UUID:
        """Создать права с происхождением от случая."""
        ...

    def revoke(self, case: ClinicalCase, user_id: UUID) -> None:
        """Отозвать только права данного случая."""
        ...

    def available_materials(
        self, patient_id: UUID, user_id: UUID, query: str, offset: int, limit: int
    ) -> dict[str, object]:
        """Выбрать страницу доступных записей пациента."""
        ...
