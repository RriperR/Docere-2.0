"""Вспомогательные пути и поиск корня проекта."""

from pathlib import Path


def find_project_root(start_path: Path) -> Path:
    """Найти корень проекта по структуре `src/app` или `pyproject.toml`.

    Args:
        start_path: Каталог, от которого начинается поиск вверх по дереву.

    Returns:
        Абсолютный путь до корня проекта.

    Raises:
        FileNotFoundError: Если не удалось найти корень проекта.
    """
    resolved_start_path = start_path.resolve()

    for directory in (resolved_start_path, *resolved_start_path.parents):
        if directory.name == 'src' and (directory / 'app').is_dir():
            return directory.parent

        if (directory / 'pyproject.toml').exists():
            return directory

    raise FileNotFoundError('Unable to locate project root via src/app layout or pyproject.toml')


PROJECT_ROOT = find_project_root(Path(__file__).resolve().parent)
DEFAULT_ENV_FILE = PROJECT_ROOT / '.env'
