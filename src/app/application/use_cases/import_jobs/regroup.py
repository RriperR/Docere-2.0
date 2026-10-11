"""Ручное распределение документов по пациентам без догадок AI."""

from copy import deepcopy
from uuid import UUID, uuid4

from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.application.use_cases.import_jobs.dtos import ImportJobDTO
from app.application.use_cases.import_jobs.errors import (
    ImportJobNotFoundError,
    ImportJobValidationError,
    ImportReviewConflictError,
)
from app.application.use_cases.import_jobs.use_cases import _as_dict_list, _to_dto, _validate_review_draft


class RegroupImportUseCase:
    """Перенести группу и введённые значения в одной транзакции."""

    def __init__(self, jobs: ImportJobRepositoryPort) -> None:
        """Связать операцию с репозиторием проверяемого импорта."""
        self.jobs = jobs

    def execute(
        self,
        job_id: UUID,
        user_id: UUID,
        role: str,
        group_id: str,
        target_id: str | None,
        version: int,
        decisions: list[dict[str, object]],
    ) -> ImportJobDTO:
        """Сохранить правки и изменить пациента одной выбранной группы.

        Returns:
            Новая версия отчёта и формы.

        Raises:
            ImportJobNotFoundError: Импорт недоступен.
            ImportJobValidationError: Группа или пациент не относятся к импорту.
            ImportReviewConflictError: Версия формы устарела.
        """
        job = self.jobs.lock_job(job_id=job_id, requested_by_user_id=user_id, requested_by_role=role)
        if job is None:
            raise ImportJobNotFoundError
        if job.version != version or job.status.value != 'needs_review':
            raise ImportReviewConflictError
        _validate_review_draft(job.report_json, decisions)
        report = deepcopy(job.report_json)
        patients = _as_dict_list(report.get('patients'))
        source = next(
            (p for p in patients if any(g.get('group_id') == group_id for g in _as_dict_list(p.get('record_groups')))),
            None,
        )
        target = next((p for p in patients if p.get('candidate_id') == target_id), None)
        if source is None or (target_id is not None and target is None):
            raise ImportJobValidationError
        if target == source:
            return _to_dto(job)
        if target is None:
            target = {
                'candidate_id': 'patient-' + uuid4().hex,
                'fio': None,
                'date_of_birth': None,
                'sources': [],
                'existing_matches': [],
                'record_groups': [],
            }
            patients.append(target)
        group = next(g for g in _as_dict_list(source.get('record_groups')) if g.get('group_id') == group_id)
        source['record_groups'] = [
            g for g in _as_dict_list(source.get('record_groups')) if g.get('group_id') != group_id
        ]
        target['record_groups'] = [*_as_dict_list(target.get('record_groups')), group]
        form = deepcopy(decisions)
        source_form = next((p for p in form if p.get('candidate_id') == source['candidate_id']), None)
        if source_form is None:
            raise ImportJobValidationError
        moved = next(
            (g for g in _as_dict_list(source_form.get('record_groups')) if g.get('group_id') == group_id), None
        )
        if moved is None:
            raise ImportJobValidationError
        moved['patient_identity_confirmed'] = False
        source_form['record_groups'] = [
            g for g in _as_dict_list(source_form.get('record_groups')) if g.get('group_id') != group_id
        ]
        target_form = next((p for p in form if p.get('candidate_id') == target['candidate_id']), None)
        if target_form is None:
            target_form = {
                'candidate_id': target['candidate_id'],
                'action': 'create',
                'fio': target.get('fio'),
                'date_of_birth': target.get('date_of_birth'),
                'record_groups': [],
            }
            form.append(target_form)
        target_form['record_groups'] = [*_as_dict_list(target_form.get('record_groups')), moved]
        report['patients'] = [p for p in patients if _as_dict_list(p.get('record_groups'))]
        form = [p for p in form if _as_dict_list(p.get('record_groups'))]
        _validate_review_draft(report, form)
        return _to_dto(self.jobs.replace_review(job_id, report, form))
