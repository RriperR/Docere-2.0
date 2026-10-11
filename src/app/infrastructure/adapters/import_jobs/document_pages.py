"""Подготовка PDF и изображений для анализа без внешнего файлового хранилища."""

import warnings
from base64 import b64encode
from io import BytesIO

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from app.application.ports.import_jobs.ai import DocumentPage
from app.domain.import_ai import ImportAiError

MAX_PIXELS = 25_000_000


def _encode(image: Image.Image) -> str:
    image.thumbnail((2000, 2000))
    output = BytesIO()
    image.convert('RGB').save(output, format='JPEG', quality=85)
    return b64encode(output.getvalue()).decode('ascii')


class DocumentPages:
    """Сформировать страницы с явными ограничениями памяти и числа страниц."""

    def prepare(self, content: bytes, mime_type: str, max_pages: int) -> tuple[DocumentPage, ...]:
        """Извлечь текст и отрисовать страницы.

        Args:
            content: Документ из безопасного архива.
            mime_type: Проверенный формат документа.
            max_pages: Максимальное число страниц документа.

        Returns:
            Полный набор страниц.

        Raises:
            ImportAiError: Формат, размер или содержимое недопустимы.
        """
        try:
            if mime_type == 'application/pdf':
                with pdfium.PdfDocument(content) as pdf:
                    if not len(pdf) or len(pdf) > max_pages:
                        raise ImportAiError('document_page_limit')
                    pages = []
                    for index in range(len(pdf)):
                        with pdf[index] as page:
                            width, height = page.get_size()
                            if width <= 0 or height <= 0:
                                raise ImportAiError('unreadable_document')
                            scale = min(2.0, 2000 / max(width, height))
                            with (
                                page.get_textpage() as text_page,
                                page.render(scale=scale) as bitmap,
                                bitmap.to_pil() as image,
                            ):
                                pages.append(
                                    DocumentPage(index + 1, text_page.get_text_bounded()[:30000], _encode(image))
                                )
                    return tuple(pages)
            if mime_type in {'image/png', 'image/jpeg'}:
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(BytesIO(content), formats=['PNG', 'JPEG']) as image:
                        if image.width * image.height > MAX_PIXELS:
                            raise ImportAiError('image_size_limit')
                        image.load()
                        with ImageOps.exif_transpose(image) as normalized:
                            return (DocumentPage(1, '', _encode(normalized)),)
            raise ImportAiError('unsupported_document')
        except (
            pdfium.PdfiumError,
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise ImportAiError('unreadable_document') from exc
