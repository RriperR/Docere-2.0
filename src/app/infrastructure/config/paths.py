"""Вспомогательные пути и поиск корня проекта."""

from pathlib import Path


def find_project_root(start_path: Path) -> Path:
    """Найти корень проекта по `pyproject.toml`.

    Args:
        start_path: Каталог, от которого начинается поиск вверх по дереву.

    Returns:
        Абсолютный путь до корня проекта.

    Raises:
        FileNotFoundError: Если `pyproject.toml` не найден ни в одном родительском каталоге.
    """
    for directory in (start_path, *start_path.parents):
        if (directory / 'pyproject.toml').exists():
            return directory

    raise FileNotFoundError('Unable to locate project root via pyproject.toml')


PROJECT_ROOT = find_project_root(Path(__file__).resolve().parent)
DEFAULT_ENV_FILE = PROJECT_ROOT / '.env'
