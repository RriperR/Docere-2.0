"""Безопасная упаковка PDF и изображений в архив импорта."""

from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZIP_STORED, ZipFile

from app.application.ports.import_jobs.document_bundle import UploadedDocument
from app.application.use_cases.import_jobs.errors import ImportJobValidationError


class DocumentBundle:
    """Упаковать документы с уникальными именами без пользовательских путей."""

    def pack(self, documents: tuple[UploadedDocument, ...]) -> bytes:
        """Вернуть архив после проверки сигнатур и размеров.

        Args:
            documents: PDF, PNG или JPEG.

        Returns:
            ZIP с независимыми документами.

        Raises:
            ImportJobValidationError: Формат, число или размер файлов недопустимы.
        """
        if not documents or len(documents) > 100 or sum(len(d.content) for d in documents) > 200 * 1024 * 1024:
            raise ImportJobValidationError
        output = BytesIO()
        with ZipFile(output, 'w', compression=ZIP_STORED) as archive:
            for index, document in enumerate(documents, start=1):
                name = PurePosixPath(document.filename.replace('\\', '/')).name
                suffix = PurePosixPath(name).suffix.lower()
                valid = (
                    suffix == '.pdf'
                    and document.content.startswith(b'%PDF-')
                    or suffix == '.png'
                    and document.content.startswith(b'\x89PNG\r\n\x1a\n')
                    or suffix in {'.jpg', '.jpeg'}
                    and document.content.startswith(b'\xff\xd8\xff')
                )
                if not valid or len(document.content) > 100 * 1024 * 1024:
                    raise ImportJobValidationError
                safe_name = ''.join(c for c in name if c.isprintable() and c not in '<>:"|?*')[:180]
                archive.writestr(f'{index:03d}/{safe_name}', document.content)
        return output.getvalue()
