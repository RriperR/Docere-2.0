"""DTO административной оперативной сводки."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AdminUserMetricsDTO:
    """Счетчики учетных записей."""

    total: int
    active: int
    blocked: int
    doctors: int
    patients: int
    admins: int


@dataclass(frozen=True, slots=True)
class AdminArchiveMetricsDTO:
    """Счетчики заданий импорта архивов."""

    total: int
    processing: int
    needs_review: int
    failed: int
    completed: int


@dataclass(frozen=True, slots=True)
class AdminSharingMetricsDTO:
    """Счетчики sharing-запросов."""

    pending_requests: int
    active_requests: int


@dataclass(frozen=True, slots=True)
class AdminDashboardSummaryDTO:
    """Оперативная сводка для панели администратора."""

    users: AdminUserMetricsDTO
    patient_cards_total: int
    archives: AdminArchiveMetricsDTO
    sharing: AdminSharingMetricsDTO
