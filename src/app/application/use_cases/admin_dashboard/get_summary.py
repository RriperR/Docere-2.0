"""Сценарий получения административной оперативной сводки."""

from app.application.ports.repositories.admin_dashboard.dtos import AdminDashboardSummaryDTO
from app.application.ports.repositories.admin_dashboard.port import AdminDashboardRepositoryPort


class AdminDashboardAccessDeniedError(Exception):
    """Текущий пользователь не может просматривать административную сводку."""


class GetAdminDashboardSummaryUseCase:
    """Вернуть актуальные счетчики для административной панели."""

    def __init__(self, repository: AdminDashboardRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий административной read-model.
        """
        self._repository = repository

    def execute(self, *, actor_role: str) -> AdminDashboardSummaryDTO:
        """Вернуть сводку администратору.

        Returns:
            Актуальные агрегированные счетчики.

        Raises:
            AdminDashboardAccessDeniedError: Если текущий пользователь не администратор.
        """
        if actor_role != 'admin':
            raise AdminDashboardAccessDeniedError
        return self._repository.get_summary()
