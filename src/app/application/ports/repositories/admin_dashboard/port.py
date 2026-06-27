"""Контракт чтения административной оперативной сводки."""

from app.application.ports.repositories.admin_dashboard.dtos import AdminDashboardSummaryDTO


class AdminDashboardRepositoryPort:
    """Порт агрегированной read-model административной панели."""

    def get_summary(self) -> AdminDashboardSummaryDTO:
        """Вернуть актуальные системные счетчики.

        Returns:
            Агрегированная административная сводка.
        """
        raise NotImplementedError
