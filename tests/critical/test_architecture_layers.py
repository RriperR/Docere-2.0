from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / 'src' / 'app'
DOMAIN_DIR = APP_DIR / 'domain'
APPLICATION_DIR = APP_DIR / 'application'
FORBIDDEN_PREFIXES = ('app.infrastructure', 'app.presentation')
APPLICATION_FORBIDDEN_MODULES = {'zipfile', 'pydicom', 'mimetypes'}
APPLICATION_FORBIDDEN_FROM_IMPORTS = {('io', 'BytesIO')}


@pytest.mark.critical
def test_required_layers_exist() -> None:
    layer_dirs = ('domain', 'application', 'infrastructure', 'presentation')
    for layer in layer_dirs:
        layer_path = APP_DIR / layer
        assert layer_path.is_dir(), f'Missing layer directory: {layer_path}'
        assert (layer_path / '__init__.py').is_file(), f'Missing __init__.py in layer: {layer_path}'


@pytest.mark.critical
def test_domain_layer_does_not_import_outer_layers() -> None:
    python_files = DOMAIN_DIR.rglob('*.py')

    for file_path in python_files:
        tree = ast.parse(file_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                import_names = [node.module] if node.module else []
            else:
                continue

            for import_name in import_names:
                if import_name and import_name.startswith(FORBIDDEN_PREFIXES):
                    raise AssertionError(
                        f'Domain layer must not import outer layers. File={file_path}, import={import_name}'
                    )


@pytest.mark.critical
def test_application_layer_does_not_import_infrastructure_or_archive_libraries() -> None:
    python_files = APPLICATION_DIR.rglob('*.py')

    for file_path in python_files:
        tree = ast.parse(file_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    _assert_application_import_allowed(file_path=file_path, import_name=alias.name)
            elif isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue
                _assert_application_import_allowed(file_path=file_path, import_name=node.module)
                for alias in node.names:
                    if (node.module, alias.name) in APPLICATION_FORBIDDEN_FROM_IMPORTS:
                        raise AssertionError(
                            'Application layer must use ports instead of infrastructure archive details. '
                            f'File={file_path}, import={node.module}.{alias.name}',
                        )


def _assert_application_import_allowed(*, file_path: Path, import_name: str) -> None:
    if import_name.startswith(FORBIDDEN_PREFIXES) or import_name in APPLICATION_FORBIDDEN_MODULES:
        raise AssertionError(
            'Application layer must not import outer layers or infrastructure archive libraries. '
            f'File={file_path}, import={import_name}',
        )
