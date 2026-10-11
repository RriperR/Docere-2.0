"""Проверка применённых предложений и происхождения перед сохранением записи."""

from uuid import UUID

from app.application.ports.import_jobs.ai import ImportAiRepositoryPort
from app.application.use_cases.import_jobs.documents import import_file_id
from app.application.use_cases.import_jobs.use_cases import _as_dict_list
from app.domain.import_ai import AI_FIELDS, AiDocument, ImportAiError


class ReviewImportAiUseCase:
    """Не доверять присланным клиентом источникам и не объединять разных пациентов."""

    def __init__(self, repository: ImportAiRepositoryPort) -> None:
        """Связать проверку с защищёнными результатами анализа."""
        self.repository = repository

    def provenance(
        self,
        job_id: UUID,
        user_id: UUID,
        role: str,
        report: dict[str, object],
        decisions: list[dict[str, object]],
        final: bool,
    ) -> dict[str, list[dict[str, object]]]:
        """Проверить выбранные источники и сформировать серверное происхождение.

        Args:
            job_id: Проверяемый импорт.
            user_id: Действующий пользователь.
            role: Его роль.
            report: Актуальные группы файлов.
            decisions: Проверенные врачом поля.
            final: Требовать разрешения конфликтов перед созданием записей.

        Returns:
            Происхождение применённых предложений по group_id.

        Raises:
            ImportAiError: Подмена источника или неразрешённый конфликт пациента.
        """
        runs = self.repository.latest_documents(job_id, user_id, role)
        latest: dict[str, AiDocument] = {}
        by_id = {run.id: run for run in runs}
        for previous_run in runs:
            for previous_document in previous_run.documents:
                if previous_document.status == 'completed':
                    latest.setdefault(previous_document.file_id, previous_document)
        groups = {
            str(g['group_id']): g
            for p in _as_dict_list(report.get('patients'))
            for g in _as_dict_list(p.get('record_groups'))
        }
        result: dict[str, list[dict[str, object]]] = {}
        for patient in decisions:
            if patient.get('action') == 'skip':
                continue
            for decision in _as_dict_list(patient.get('record_groups')):
                if decision.get('action') == 'skip':
                    continue
                gid = str(decision['group_id'])
                files = {import_file_id(str(f['path'])) for f in _as_dict_list(groups[gid].get('files'))}
                for fid in files:
                    document = latest.get(fid)
                    if document is None or not final:
                        continue
                    if document.result.get('multiple_patients') is True:
                        raise ImportAiError('multiple_patients_document')
                    fields = document.result.get('fields')
                    has_identity = isinstance(fields, dict) and any(name in fields for name in {'fio', 'date_of_birth'})
                    if (has_identity or document.result.get('patient_conflict')) and decision.get(
                        'patient_identity_confirmed'
                    ) is not True:
                        raise ImportAiError('patient_identity_confirmation_required')
                applied = []
                for reference in _as_dict_list(decision.get('applied_ai')):
                    run = by_id.get(str(reference.get('run_id')))
                    fid = str(reference.get('file_id'))
                    names = reference.get('fields')
                    if run is None or fid not in files or not isinstance(names, list) or not names:
                        raise ImportAiError('invalid_ai_source')
                    document = next((d for d in run.documents if d.file_id == fid and d.status == 'completed'), None)
                    fields = document.result.get('fields') if document else None
                    if not isinstance(fields, dict) or any(
                        name not in AI_FIELDS or name not in fields for name in names
                    ):
                        raise ImportAiError('invalid_ai_source')
                    for name in names:
                        field = fields[name]
                        if not isinstance(field, dict):
                            raise ImportAiError('invalid_ai_source')
                        actual = patient.get(name) if name in {'fio', 'date_of_birth'} else decision.get(name)
                        applied.append(
                            {
                                'run_id': run.id,
                                'file_id': fid,
                                'field': name,
                                'suggested_value': field.get('value'),
                                'sources': field.get('sources'),
                                'edited_by_reviewer': actual != field.get('value'),
                                'model': run.model,
                                'prompt_version': run.prompt_version,
                                'checksum': document.checksum if document else None,
                            }
                        )
                result[gid] = applied
        return result
