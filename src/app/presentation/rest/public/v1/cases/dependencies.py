"""DI и транзакционная граница клинических случаев."""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.use_cases.clinical_cases import ClinicalCasesUseCase
from app.domain.clinical_cases import CaseError
from app.infrastructure.adapters.repositories.clinical_cases import SqlAlchemyCaseRepository
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.presentation.rest.public.v1.records.dependencies import db_session_dependency


def get_cases_use_case(session: Session = db_session_dependency) -> ClinicalCasesUseCase:
    """Собрать прикладные сценарии в одной SQLAlchemy-сессии.

    Returns:
        Результат операции в контексте доступа текущего пользователя.
    """
    return ClinicalCasesUseCase(SqlAlchemyCaseRepository(session), SqlAlchemyMedicalRecordRepositoryAdapter(session))


cases_dependency = Depends(get_cases_use_case)


@contextmanager
def case_transaction(session: Session) -> Iterator[None]:
    """Зафиксировать операцию целиком или вернуть безопасную HTTP-ошибку.

    Raises:
        HTTPException: При нарушении условий операции.
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
