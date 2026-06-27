"""Ошибки сценариев заявок на роль врача."""


class DoctorRoleApplicationError(Exception):
    """Базовая ошибка workflow роли врача."""


class DoctorRoleApplicationAccessDeniedError(DoctorRoleApplicationError):
    """Текущий пользователь не может выполнить действие."""


class DoctorRoleApplicationValidationError(DoctorRoleApplicationError):
    """Параметры заявки или решения не проходят бизнес-валидацию."""


class DoctorRoleApplicationConflictError(DoctorRoleApplicationError):
    """Действие конфликтует с текущим состоянием заявки."""


class DoctorRoleApplicationNotFoundError(DoctorRoleApplicationError):
    """Заявка не найдена или не назначена текущему пользователю."""
