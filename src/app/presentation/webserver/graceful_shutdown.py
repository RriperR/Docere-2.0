"""Механизмы graceful shutdown HTTP-приложения."""

from __future__ import annotations

from threading import Lock
from time import monotonic
from types import FrameType

from uvicorn import Config
from uvicorn.server import Server


class GracefulShutdownController:
    """Контролировать переход приложения в режим graceful shutdown."""

    def __init__(self) -> None:
        """Инициализировать контроллер graceful shutdown."""
        self._lock = Lock()
        self._is_shutting_down = False

    @property
    def is_shutting_down(self) -> bool:
        """Вернуть признак режима завершения приложения."""
        with self._lock:
            return self._is_shutting_down

    def begin_shutdown(self) -> None:
        """Перевести приложение в режим graceful shutdown."""
        with self._lock:
            self._is_shutting_down = True


class GracefulShutdownServer(Server):
    """Добавить короткое окно draining перед штатным shutdown uvicorn."""

    def __init__(
        self,
        config: Config,
        *,
        controller: GracefulShutdownController,
        reject_window_seconds: float,
    ) -> None:
        """Инициализировать uvicorn server с поддержкой draining.

        Args:
            config: Конфигурация uvicorn.
            controller: Контроллер режима graceful shutdown.
            reject_window_seconds: Длительность окна отказа новых запросов.
        """
        super().__init__(config)
        self._controller = controller
        self._reject_window_seconds = reject_window_seconds
        self._shutdown_started_at: float | None = None

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        """Запустить draining перед штатным завершением по первому сигналу.

        Args:
            sig: Номер Unix-сигнала.
            frame: Текущий stack frame обработчика сигнала.
        """
        if self._shutdown_started_at is None:
            self._controller.begin_shutdown()
            self._shutdown_started_at = monotonic()
            return

        super().handle_exit(sig, frame)

    async def on_tick(self, counter: int) -> bool:
        """Завершить процесс после окна draining и базовых проверок uvicorn.

        Args:
            counter: Счётчик тиков основного цикла uvicorn.

        Returns:
            `True`, если сервер должен завершить работу, иначе `False`.
        """
        if self._shutdown_started_at is not None and not self.should_exit:
            elapsed_seconds = monotonic() - self._shutdown_started_at
            if elapsed_seconds >= self._reject_window_seconds:
                self.should_exit = True

        return await super().on_tick(counter)
