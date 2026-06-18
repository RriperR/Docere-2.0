"""S3/MinIO-реализация файлового хранилища на boto3."""

from __future__ import annotations

import boto3

from app.application.ports.storage.file_storage import FileStoragePort
from app.infrastructure.config.settings import StorageSettings


class S3FileStorageAdapter(FileStoragePort):
    """Хранилище вложений поверх S3-совместимого объектного хранилища."""

    def __init__(self, settings: StorageSettings) -> None:
        """Инициализировать клиент S3 по настройкам хранилища.

        Args:
            settings: Настройки файлового хранилища.
        """
        self._bucket = settings.bucket
        self._client = boto3.client(
            's3',
            endpoint_url=settings.endpoint,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key.get_secret_value(),
            region_name=settings.region,
        )

    def upload(self, *, key: str, content: bytes, content_type: str) -> None:
        """Сохранить содержимое в бакете.

        Args:
            key: Ключ объекта в хранилище.
            content: Бинарное содержимое файла.
            content_type: MIME-тип содержимого.
        """
        self._client.put_object(Bucket=self._bucket, Key=key, Body=content, ContentType=content_type)

    def download(self, *, key: str) -> bytes:
        """Вернуть содержимое объекта из бакета.

        Args:
            key: Ключ объекта в хранилище.

        Returns:
            Бинарное содержимое объекта.
        """
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        data: bytes = response['Body'].read()
        return data
