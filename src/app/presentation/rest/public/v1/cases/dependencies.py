"""DI и транзакционная граница клинических случаев."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.use_cases.clinical_cases.conclusions import CaseConclusionsUseCase
from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.discussion import CaseDiscussionUseCase
from app.application.use_cases.clinical_cases.management import ClinicalCasesUseCase
from app.application.use_cases.clinical_cases.materials import CaseMaterialsUseCase
from app.application.use_cases.clinical_cases.work_drafts import CaseWorkDraftsUseCase
from app.domain.clinical_cases import CaseError
from app.infrastructure.adapters.repositories.case_drafts import SqlAlchemyCaseDraftRepository
from app.infrastructure.adapters.repositories.clinical_cases import SqlAlchemyCaseRepository
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.presentation.rest.public.v1.records.dependencies import db_session_dependency


def get_case_context(session: Session = db_session_dependency) -> CaseContext:
    """Собрать прикладные сценарии в одной SQLAlchemy-сессии.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Прикладная зависимость, использующая репозитории текущей SQLAlchemy-сессии.
    """
    return CaseContext(SqlAlchemyCaseRepository(session), SqlAlchemyMedicalRecordRepositoryAdapter(session))


def get_cases_use_case(session: Session = db_session_dependency) -> ClinicalCasesUseCase:
    """Собрать управление случаем в текущей транзакции.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Прикладная зависимость, использующая репозитории текущей SQLAlchemy-сессии.
    """
    return ClinicalCasesUseCase(get_case_context(session))


def get_discussion_use_case(session: Session = db_session_dependency) -> CaseDiscussionUseCase:
    """Собрать обсуждение в текущей транзакции.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Сценарии сообщений, запросов мнения и журнала.
    """
    return CaseDiscussionUseCase(get_case_context(session))


def get_conclusions_use_case(session: Session = db_session_dependency) -> CaseConclusionsUseCase:
    """Собрать итог и публикацию в текущей транзакции.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Сценарии сохранения версий, закрытия и публикации итога.
    """
    return CaseConclusionsUseCase(get_case_context(session))


def get_materials_use_case(session: Session = db_session_dependency) -> CaseMaterialsUseCase:
    """Собрать поиск и просмотр материалов в текущей транзакции.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Сценарии материалов с полной проверкой контекста случая.
    """
    return CaseMaterialsUseCase(get_case_context(session))


def get_work_drafts(session: Session = db_session_dependency) -> CaseWorkDraftsUseCase:
    """Собрать сценарий формы в текущей транзакции.

    Args:
        session: Сессия HTTP-запроса.

    Returns:
        Сценарий с общей политикой случая и личным хранилищем.
    """
    return CaseWorkDraftsUseCase(get_case_context(session), SqlAlchemyCaseDraftRepository(session))


drafts_dependency = Depends(get_work_drafts)


cases_dependency = Depends(get_cases_use_case)
discussion_dependency = Depends(get_discussion_use_case)
conclusions_dependency = Depends(get_conclusions_use_case)
materials_dependency = Depends(get_materials_use_case)


@contextmanager
def case_transaction(session: Session) -> Iterator[None]:
    """Зафиксировать операцию целиком или вернуть безопасную HTTP-ошибку.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Yields:
        Управление телу операции в текущей транзакции.

    Raises:
        HTTPException: Если доступ запрещён, ссылка недействительна или возник конфликт изменения.
    """
    try:
        yield
        session.commit()
    except CaseError as exc:
        session.rollback()
        raise HTTPException(exc.status, str(exc)) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, 'Конкурирующее изменение. Обновите данные') from exc
