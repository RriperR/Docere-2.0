"""Контракт файлового хранилища."""

from __future__ import annotations


class FileStoragePort:
    """Порт загрузки и чтения бинарного содержимого вложений."""

    def upload(self, *, key: str, content: bytes, content_type: str) -> None:
        """Сохранить содержимое по ключу.

        Args:
            key: Ключ объекта в хранилище.
            content: Бинарное содержимое файла.
            content_type: MIME-тип содержимого.
        """
        raise NotImplementedError

    def download(self, *, key: str) -> bytes:
        """Вернуть содержимое объекта по ключу.

        Args:
            key: Ключ объекта в хранилище.

        Returns:
            Бинарное содержимое объекта.
        """
        raise NotImplementedError
