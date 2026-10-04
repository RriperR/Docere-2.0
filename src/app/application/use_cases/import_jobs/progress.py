"""Чтение статуса импорта без передачи медицинских данных в поток."""

from uuid import UUID

from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.application.use_cases.auth.get_authenticated_user.use_case import GetAuthenticatedUserUseCase
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError
from app.domain.entities.import_job import ImportJobProgress


class GetImportProgressUseCase:
    """Повторно проверить актуальный токен, пользователя и доступ на каждом чтении."""

    def __init__(self, auth: GetAuthenticatedUserUseCase, jobs: ImportJobRepositoryPort) -> None:
        """Связать проверку доступа с чтением проекции.

        Args:
            auth: Проверка действующего токена и пользователя.
            jobs: Репозиторий заданий импорта.
        """
        self._auth = auth
        self._jobs = jobs

    def execute(self, *, token: str, job_id: UUID) -> ImportJobProgress:
        """Прочитать статус для активного пользователя.

        Args:
            token: Access-токен подписчика.
            job_id: Идентификатор задания.

        Returns:
            Актуальное состояние фоновой обработки.

        Raises:
            ImportJobNotFoundError: Задание не существует или недоступно пользователю.
        """
        user = self._auth.execute(token=token)
        progress = self._jobs.get_progress(
            job_id=job_id,
            requested_by_user_id=user.id,
            requested_by_role=user.role,
        )
        if progress is None:
            raise ImportJobNotFoundError
        return progress
