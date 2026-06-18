"""Management CLI для одноразовых административных задач."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.application.use_cases.auth.create_admin_user.use_case import CreateAdminUserUseCase
from app.application.use_cases.auth.errors import EmailAlreadyExistsError
from app.infrastructure.adapters.repositories.auth.sqlalchemy_auth_repository import SqlAlchemyAuthRepositoryAdapter
from app.infrastructure.adapters.security.pbkdf2_password_hasher import Pbkdf2PasswordHasherAdapter
from app.infrastructure.db.seed import DEFAULT_DEMO_PASSWORD, seed_demo_data
from app.infrastructure.db.session import close_db_connections, get_session_factory
from app.presentation.webserver.server_runner import run_http_server

DEFAULT_ADMIN_FIO = 'Администратор сервиса'
DEFAULT_ADMIN_PHONE = '+70000000000'


def build_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов management CLI.

    Returns:
        Настроенный парсер командной строки.
    """
    parser = argparse.ArgumentParser(prog='docere')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('serve')
    subparsers.add_parser('migrate')

    create_admin_parser = subparsers.add_parser('create-admin')
    create_admin_parser.add_argument('--email', required=True)
    create_admin_parser.add_argument('--password', required=True)
    create_admin_parser.add_argument('--fio', default=DEFAULT_ADMIN_FIO)
    create_admin_parser.add_argument('--phone', default=DEFAULT_ADMIN_PHONE)

    seed_demo_parser = subparsers.add_parser('seed-demo')
    seed_demo_parser.add_argument('--password', default=DEFAULT_DEMO_PASSWORD)

    return parser


def run_migrations() -> None:
    """Применить миграции Alembic до последней ревизии."""
    alembic_config = Config(str(Path('alembic.ini')))
    command.upgrade(alembic_config, 'head')


def create_admin_user(*, email: str, password: str, fio: str, phone: str) -> None:
    """Создать администратора в базе данных.

    Args:
        email: Email администратора.
        password: Пароль администратора.
        fio: ФИО администратора.
        phone: Телефон администратора.

    Raises:
        ValueError: Если пользователь с таким email уже существует.
    """
    session_factory = get_session_factory()
    with session_factory() as session:
        use_case = CreateAdminUserUseCase(
            repository=SqlAlchemyAuthRepositoryAdapter(session=session),
            password_hasher=Pbkdf2PasswordHasherAdapter(),
        )
        try:
            use_case.execute(
                fio=fio,
                email=email,
                phone=phone,
                password=password,
            )
            session.commit()
        except EmailAlreadyExistsError as error:
            session.rollback()
            raise ValueError('User with this email already exists') from error
        except Exception:
            session.rollback()
            raise


def seed_demo(*, password: str) -> None:
    """Загрузить демонстрационные данные в базу.

    Сидинг идемпотентен: ранее созданные демо-сущности удаляются перед вставкой.

    Args:
        password: Пароль в открытом виде для всех демо-учёток.
    """
    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            counts = seed_demo_data(
                session=session,
                password_hasher=Pbkdf2PasswordHasherAdapter(),
                password=password,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise

    print('Демо-данные загружены:')
    for name, value in counts.items():
        print(f'  - {name}: {value}')
    print(f'Пароль демо-учёток: {password}')


def main(argv: Sequence[str] | None = None) -> int:
    """Запустить management CLI.

    Args:
        argv: Последовательность аргументов командной строки.

    Returns:
        Код завершения процесса.
    """
    args = build_parser().parse_args(argv)

    try:
        if args.command == 'serve':
            run_http_server()
            return 0

        if args.command == 'migrate':
            run_migrations()
            return 0

        if args.command == 'create-admin':
            create_admin_user(
                email=args.email,
                password=args.password,
                fio=args.fio,
                phone=args.phone,
            )
            return 0

        if args.command == 'seed-demo':
            seed_demo(password=args.password)
            return 0
    except Exception as error:
        print(f'Command failed: {error}', file=sys.stderr)
        return 1
    finally:
        close_db_connections()

    return 1


if __name__ == '__main__':
    raise SystemExit(main())
