"""Детерминированный набор синтетических документов и эталон E1 без сети."""

import argparse
import json
import textwrap
from collections.abc import Sequence
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import cast, Literal, NotRequired, TypedDict
from zipfile import ZipFile, ZipInfo

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, UID

FIXTURES = Path(__file__).resolve().parents[1] / 'tests/fixtures/import_ai'
MANIFEST = FIXTURES / 'manifest.json'
DatasetSplit = Literal['all', 'development', 'holdout']


class Source(TypedDict):
    """Подтверждающий фрагмент конкретной страницы."""

    page: int
    excerpt: str


class Page(TypedDict):
    """Синтетическая исходная страница."""

    number: int
    text: str


class ExpectedField(TypedDict):
    """Допустимые значения реквизита и подтверждающие источники."""

    allowed_values: list[str | None]
    sources: list[Source]


class ExpectedFact(TypedDict):
    """Проверяемое утверждение без буквального сравнения пересказа."""

    id: str
    claim: str
    sources: list[Source]
    required: bool


class Expected(TypedDict):
    """Эталон документа, включая корректные отказы."""

    fields: dict[str, ExpectedField]
    empty_fields: list[str]
    facts: list[ExpectedFact]
    issues: list[str]
    multiple_patients: bool
    error_code: str | None
    abstention_allowed: NotRequired[bool]
    forbidden_claims: NotRequired[list[str]]


class DocumentRecipe(TypedDict):
    """Параметры рендеринга; строковые страницы сохраняют legacy-контракт."""

    name: str
    pages: Sequence[Page | str]
    render: Literal['protected_pdf', 'corrupt_pdf', 'text_pdf', 'scan_pdf', 'jpeg', 'png']
    rotation: NotRequired[int]
    blur: NotRequired[bool]
    low_quality: NotRequired[bool]
    photo: NotRequired[bool]


class Document(DocumentRecipe):
    """Документ эталона и необязательные метаданные сгенерированного файла."""

    split: Literal['development', 'holdout']
    tags: list[str]
    expected: Expected
    synthetic_source: NotRequired[str]
    test_password: NotRequired[str]
    mime_type: NotRequired[str]
    sha256: NotRequired[str]


class MixedZip(TypedDict):
    """Ожидания development-архива с исключённым из AI DICOM."""

    name: str
    split: Literal['development']
    documents: list[str]
    dicom: str
    expected_ai_documents: list[str]
    expected_dicom_provider_calls: int


class DatasetManifest(TypedDict):
    """Версия, выбранные документы и только относящийся к split mixed ZIP."""

    schema_version: int
    dataset_version: str
    synthetic_only: bool
    summary_policy: str
    split_policy: str
    documents: list[Document]
    mixed_zip: NotRequired[MixedZip]
    selected_split: NotRequired[DatasetSplit]


def load_manifest() -> DatasetManifest:
    """Прочитать только версионируемый синтетический эталон.

    Returns:
        Источники, допустимые значения, пустые поля и разделение набора.
    """
    return cast(DatasetManifest, json.loads(MANIFEST.read_text(encoding='utf-8')))


def _pdf(objects: list[bytes]) -> bytes:
    output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f'{number} 0 obj\n'.encode() + value + b'\nendobj\n')
    xref = len(output)
    output.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(output)


def _stream(content: bytes, attributes: str = '') -> bytes:
    return f'<< /Length {len(content)} {attributes} >>\nstream\n'.encode() + content + b'\nendstream'


def _text_pdf(pages: list[str]) -> bytes:
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for text in pages:
        number = len(objects) + 1
        kids.append(f'{number} 0 R')
        objects.append(
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 800 600] '
            f'/Resources << /Font << /F1 3 0 R >> >> /Contents {number + 1} 0 R >>'.encode()
        )
        lines = [part for line in text.splitlines() for part in textwrap.wrap(line, 95) or ['']]
        commands = ['BT /F1 12 Tf 20 TL 30 555 Td']
        for index, line in enumerate(lines):
            escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands.append(('T* ' if index else '') + f'({escaped}) Tj')
        commands.append('ET')
        objects.append(_stream('\n'.join(commands).encode('ascii')))
    objects[1] = f'<< /Type /Pages /Count {len(pages)} /Kids [{" ".join(kids)}] >>'.encode()
    return _pdf(objects)


def _image_pdf(images: list[Image.Image]) -> bytes:
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'']
    kids = []
    for image in images:
        number = len(objects) + 1
        kids.append(f'{number} 0 R')
        objects.append(
            f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 800 500] '
            f'/Resources << /XObject << /Im0 {number + 2} 0 R >> >> /Contents {number + 1} 0 R >>'.encode()
        )
        objects.append(_stream(b'q 800 0 0 500 0 0 cm /Im0 Do Q'))
        output = BytesIO()
        image.save(output, format='JPEG', quality=90)
        objects.append(
            _stream(
                output.getvalue(),
                f'/Type /XObject /Subtype /Image /Width {image.width} /Height {image.height} '
                '/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode',
            )
        )
    objects[1] = f'<< /Type /Pages /Count {len(images)} /Kids [{" ".join(kids)}] >>'.encode()
    return _pdf(objects)


def make_document(document: DocumentRecipe) -> tuple[bytes, str]:
    """Сформировать документ из синтетических страниц без временных меток.

    Args:
        document: Элемент manifest с render, name и pages.

    Returns:
        Байты и MIME-тип. Повторный вызов с теми же версиями библиотек идентичен.
    """
    kind = document['render']
    if kind == 'protected_pdf':
        return (FIXTURES / 'synthetic-protected.pdf').read_bytes(), 'application/pdf'
    if kind == 'corrupt_pdf':
        return b'%PDF-1.4\nSYNTHETIC TRUNCATED DOCUMENT\n', 'application/pdf'
    pages = [page['text'] if isinstance(page, dict) else page for page in document['pages']]
    if kind == 'text_pdf':
        return _text_pdf(pages), 'application/pdf'
    images = []
    try:
        font = ImageFont.load_default(size=26)
        for text in pages:
            image = Image.new('RGB', (1600, 1000), 'white')
            wrapped = '\n'.join(part for line in text.splitlines() for part in textwrap.wrap(line, 95) or [''])
            ImageDraw.Draw(image).multiline_text((60, 70), wrapped, font=font, fill='black', spacing=16)
            if document.get('rotation'):
                rotated = image.rotate(document['rotation'], expand=True)
                image.close()
                image = rotated
            if document.get('blur'):
                blurred = image.filter(ImageFilter.GaussianBlur(1.2))
                image.close()
                image = blurred
            if document.get('low_quality'):
                small = image.resize((400, 250))
                image.close()
                image = small
            if document.get('photo'):
                skewed = image.transform(image.size, Image.Transform.QUAD, (0, 70, 80, 980, 1540, 930, 1590, 0))
                image.close()
                image = skewed
            images.append(image)
        if kind == 'scan_pdf':
            return _image_pdf(images), 'application/pdf'
        output = BytesIO()
        jpeg = kind == 'jpeg'
        images[0].save(output, format='JPEG' if jpeg else 'PNG', quality=45 if document.get('low_quality') else 90)
        return output.getvalue(), 'image/jpeg' if jpeg else 'image/png'
    finally:
        for image in images:
            image.close()


def make_dicom() -> bytes:
    """Создать синтетический DICOM с фиксированными UID для mixed ZIP.

    Returns:
        DICOM, содержащий только тестовые метаданные.
    """
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = UID('1.2.826.0.1.3680043.10.543.1')
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset('synthetic-study.dcm', {}, file_meta=meta, preamble=b'\0' * 128)
    dataset.PatientName = 'Synthetic^Dicom'
    dataset.PatientID = 'SYNTHETIC-E1'
    dataset.PatientBirthDate = '19800201'
    dataset.StudyDate = '20240823'
    dataset.Modality = 'OT'
    dataset.StudyDescription = 'SYNTHETIC - NOT A REAL PATIENT'
    dataset.StudyInstanceUID = '1.2.826.0.1.3680043.10.543.2'
    dataset.SeriesInstanceUID = '1.2.826.0.1.3680043.10.543.3'
    output = BytesIO()
    dataset.save_as(output, enforce_file_format=True)
    return output.getvalue()


def make_mixed_zip(manifest: DatasetManifest | None = None) -> bytes:
    """Собрать mixed ZIP с PDF, PNG и DICOM, фиксируя даты ZIP entries.

    Args:
        manifest: Синтетический эталон либо None для чтения из Git.

    Returns:
        Детерминированный ZIP; его DICOM запрещён для отправки в AI.
    """
    manifest = manifest or load_manifest()
    selected = {document['name']: document for document in manifest['documents']}
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        for name in manifest['mixed_zip']['documents']:
            content, _ = make_document(selected[name])
            archive.writestr(ZipInfo('documents/' + name, date_time=(2024, 1, 1, 0, 0, 0)), content)
        archive.writestr(ZipInfo('dicom/synthetic-study.dcm', date_time=(2024, 1, 1, 0, 0, 0)), make_dicom())
    return output.getvalue()


def _check_output(output: Path, split: DatasetSplit, manifest: DatasetManifest, allowed_names: set[str]) -> None:
    if not output.exists() or not any(output.iterdir()):
        return
    target = output / 'manifest.json'
    try:
        previous = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError('Output is not a managed dataset directory; choose a separate empty --output') from exc
    if (
        not isinstance(previous, dict)
        or previous.get('dataset_version') != manifest['dataset_version']
        or previous.get('selected_split') != split
    ):
        raise ValueError('Output contains another dataset version or split; choose a separate empty --output')
    managed_names = {d['name'] for d in manifest['documents']} | {manifest['mixed_zip']['name']}
    if any((output / name).exists() for name in managed_names - allowed_names):
        raise ValueError('Output contains documents outside the selected split; choose a separate empty --output')


def generate(output: Path, split: DatasetSplit = 'all') -> DatasetManifest:
    """Записать бинарники в artifacts и копию эталона с checksums, без AI.

    Args:
        output: Отдельный каталог синтетического набора.
        split: all, development либо holdout; состав задан до запуска AI.

    Returns:
        Manifest только с выбранными документами и checksums.

    Raises:
        ValueError: Split неизвестен или каталог содержит несовместимый набор.
    """
    if split not in {'all', 'development', 'holdout'}:
        raise ValueError('Unknown dataset split')
    manifest = load_manifest()
    documents = [d for d in manifest['documents'] if split == 'all' or d['split'] == split]
    include_mixed = split in {'all', manifest['mixed_zip']['split']}
    allowed_names = {document['name'] for document in documents}
    if include_mixed:
        allowed_names.add(manifest['mixed_zip']['name'])
    _check_output(output, split, manifest, allowed_names)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[Document] = []
    for document in documents:
        content, mime = make_document(document)
        (output / document['name']).write_bytes(content)
        rows.append({**document, 'mime_type': mime, 'sha256': sha256(content).hexdigest()})
    if include_mixed:
        mixed = make_mixed_zip(manifest)
        (output / manifest['mixed_zip']['name']).write_bytes(mixed)
    result: DatasetManifest = {**manifest, 'documents': rows, 'selected_split': split}
    if not include_mixed:
        result.pop('mixed_zip', None)
    (output / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    """Сгенерировать E1 без настроек провайдера, секретов и сетевых запросов."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--split', choices=('all', 'development', 'holdout'), default='all')
    args = parser.parse_args()
    output = args.output or Path('artifacts/import-ai-dataset' + ('' if args.split == 'all' else '-' + args.split))
    try:
        result = generate(output, args.split)
    except ValueError as exc:
        parser.error(str(exc))
    print(f'Generated {len(result["documents"])} documents ({args.split}) in {output}')


if __name__ == '__main__':
    main()
