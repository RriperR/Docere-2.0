"""Сценарии создания и чтения ImportJob."""

from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from app.application.ports.import_jobs.archive_reader import ArchiveReaderPort
from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort
from app.application.ports.storage.file_storage import FileStoragePort
from app.application.use_cases.import_jobs.dtos import ImportJobDTO, ImportReviewDraftDTO
from app.application.use_cases.import_jobs.errors import (
    ArchiveExtractionError,
    ImportJobDuplicateConfirmationRequiredError,
    ImportJobEventDateRequiredError,
    ImportJobNotFoundError,
    ImportJobValidationError,
)
from app.domain.entities.file_attachment import FileAttachmentCategory
from app.domain.entities.import_job import ImportJob

_FINAL_STATUSES = {'completed', 'completed_with_warnings', 'failed'}


class CreateImportJobUseCase:
    """Сохранить ZIP-архив и создать ImportJob."""

    def __init__(self, repository: ImportJobRepositoryPort, storage: FileStoragePort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий ImportJob.
            storage: Файловое хранилище архивов.
        """
        self._repository = repository
        self._storage = storage

    def execute(
        self,
        *,
        uploaded_by_user_id: UUID,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> ImportJobDTO:
        """Создать ImportJob из загруженного ZIP-архива.

        Args:
            uploaded_by_user_id: Пользователь, загрузивший архив.
            original_filename: Исходное имя файла.
            content: Бинарное содержимое архива.
            content_type: MIME-тип файла.

        Returns:
            Созданный ImportJob.

        Raises:
            ImportJobValidationError: Если файл не похож на ZIP-архив.
        """
        if not original_filename.lower().endswith('.zip') or not content.startswith(b'PK'):
            raise ImportJobValidationError

        storage_key = f'import-jobs/{uploaded_by_user_id}/{uuid4()}.zip'
        self._storage.upload(key=storage_key, content=content, content_type=content_type)
        job = self._repository.create_job(
            uploaded_by_user_id=uploaded_by_user_id,
            original_filename=original_filename,
            archive_storage_key=storage_key,
            size_bytes=len(content),
        )
        return _to_dto(job)


class GetImportJobUseCase:
    """Вернуть статус ImportJob."""

    def __init__(
        self,
        repository: ImportJobRepositoryPort,
        medical_records: MedicalRecordRepositoryPort | None = None,
    ) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий ImportJob.
            medical_records: Репозиторий записей для обогащения review-кандидатов.
        """
        self._repository = repository
        self._medical_records = medical_records

    def execute(self, *, job_id: UUID, requested_by_user_id: UUID, requested_by_role: str) -> ImportJobDTO:
        """Вернуть ImportJob, если он доступен пользователю.

        Args:
            job_id: Идентификатор ImportJob.
            requested_by_user_id: Идентификатор текущего пользователя.
            requested_by_role: Роль текущего пользователя.

        Returns:
            ImportJob.

        Raises:
            ImportJobNotFoundError: Если задание не найдено или недоступно.
        """
        job = self._repository.get_job(
            job_id=job_id,
            requested_by_user_id=requested_by_user_id,
            requested_by_role=requested_by_role,
        )
        if job is None:
            raise ImportJobNotFoundError
        return _to_dto(
            job,
            report_json=self._enrich_report_for_review(job, actor_user_id=requested_by_user_id),
        )

    def _enrich_report_for_review(self, job: ImportJob, *, actor_user_id: UUID) -> dict[str, object]:
        if self._medical_records is None or job.status.value != 'needs_review':
            return job.report_json
        patients = []
        for patient in _as_dict_list(job.report_json.get('patients')):
            patients.append(self._enrich_patient_duplicates(patient, actor_user_id=actor_user_id))
        return {**job.report_json, 'patients': patients}

    def _enrich_patient_duplicates(
        self,
        patient: dict[str, object],
        *,
        actor_user_id: UUID,
    ) -> dict[str, object]:
        if self._medical_records is None:
            return patient
        medical_records = self._medical_records
        matches = _as_dict_list(patient.get('existing_matches'))
        matched_patient_ids = []
        for match in matches:
            raw_id = match.get('id')
            if raw_id is None:
                continue
            try:
                matched_patient_ids.append(UUID(str(raw_id)))
            except ValueError:
                continue

        record_groups = []
        for group in _as_dict_list(patient.get('record_groups')):
            duplicate_candidates: list[dict[str, object]] = []
            for patient_id in matched_patient_ids:
                for candidate in medical_records.find_duplicate_candidates(
                    actor_user_id=actor_user_id,
                    patient_passport_id=patient_id,
                    record_type=str(group.get('record_type') or 'other'),
                    event_date=_parse_date(str(group.get('event_date') or '')),
                    title=str(group.get('title') or '') or None,
                ):
                    if any(item['record_id'] == str(candidate.record_id) for item in duplicate_candidates):
                        continue
                    duplicate_candidates.append(
                        {
                            'record_id': str(candidate.record_id),
                            'patient_passport_id': str(candidate.patient_passport_id),
                            'title': candidate.title,
                            'record_type': candidate.record_type,
                            'event_date': candidate.event_date.isoformat(),
                            'status': candidate.status,
                            'match_reason': candidate.match_reason,
                        },
                    )
            record_groups.append({**group, 'duplicate_candidates': duplicate_candidates})
        return {**patient, 'record_groups': record_groups}


class ListImportJobsUseCase:
    """Вернуть список доступных ImportJob."""

    def __init__(self, repository: ImportJobRepositoryPort) -> None:
        """Инициализировать use case."""
        self._repository = repository

    def execute(
        self,
        *,
        requested_by_user_id: UUID,
        requested_by_role: str,
        limit: int = 50,
    ) -> tuple[ImportJobDTO, ...]:
        """Вернуть последние задания импорта.

        Returns:
            Доступные задания импорта.
        """
        jobs = self._repository.list_jobs(
            requested_by_user_id=requested_by_user_id,
            requested_by_role=requested_by_role,
            limit=limit,
        )
        return tuple(_to_dto(job) for job in jobs)


class SaveImportReviewDraftUseCase:
    """Сохранить промежуточные решения пользователя по импорту."""

    def __init__(self, repository: ImportJobRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий заданий импорта.
        """
        self._repository = repository

    def execute(
        self,
        *,
        job_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        decisions: list[dict[str, object]],
    ) -> ImportReviewDraftDTO:
        """Проверить и сохранить черновик review.

        Returns:
            Сохраненные решения и время обновления.

        Raises:
            ImportJobNotFoundError: Если job не найден или недоступен.
            ImportJobValidationError: Если job не ожидает review или решения не относятся к отчету.
        """
        job = self._repository.get_job(
            job_id=job_id,
            requested_by_user_id=actor_user_id,
            requested_by_role=actor_role,
        )
        if job is None:
            raise ImportJobNotFoundError
        if job.status.value != 'needs_review':
            raise ImportJobValidationError
        _validate_review_draft(job.report_json, decisions)

        updated = self._repository.save_review_draft(job_id=job_id, decisions=decisions)
        if updated is None:
            raise ImportJobNotFoundError
        return ImportReviewDraftDTO(
            decisions=updated.review_decisions,
            updated_at=updated.review_updated_at,
        )


class ResolveImportJobUseCase:
    """Создать медицинские сущности из подтвержденного черновика ImportJob."""

    def __init__(
        self,
        *,
        import_jobs: ImportJobRepositoryPort,
        patient_cards: PatientCardRepositoryPort,
        medical_records: MedicalRecordRepositoryPort,
        storage: FileStoragePort,
        archive_reader: ArchiveReaderPort,
    ) -> None:
        """Инициализировать use case."""
        self._import_jobs = import_jobs
        self._patient_cards = patient_cards
        self._medical_records = medical_records
        self._storage = storage
        self._archive_reader = archive_reader

    def execute(
        self,
        *,
        job_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        actor_fio: str,
        decisions: list[dict[str, object]],
    ) -> ImportJobDTO:
        """Финализировать ImportJob по решениям пользователя.

        Returns:
            Обновленный ImportJob.

        Raises:
            ImportJobNotFoundError: Если job не найден или недоступен.
            ImportJobValidationError: Если job не готов к resolve или решение некорректно.
            ImportJobDuplicateConfirmationRequiredError: Если найдена похожая запись без подтверждения.
            ImportJobEventDateRequiredError: Если для создаваемой записи не определена дата события.
        """
        job = self._import_jobs.get_job(
            job_id=job_id,
            requested_by_user_id=actor_user_id,
            requested_by_role=actor_role,
        )
        if job is None or not job.archive_storage_key:
            raise ImportJobNotFoundError
        if job.status.value in _FINAL_STATUSES:
            return _to_dto(job)
        if job.status.value != 'needs_review':
            raise ImportJobValidationError

        report = job.report_json
        patients = {
            str(patient.get('candidate_id')): patient
            for patient in _as_dict_list(report.get('patients'))
            if patient.get('candidate_id')
        }
        decision_by_candidate = {
            str(decision.get('candidate_id')): decision for decision in decisions if decision.get('candidate_id')
        }

        archive_content = self._storage.download(key=job.archive_storage_key)
        created_patients = 0
        created_records = 0
        created_attachments = 0
        duplicate_overrides: list[dict[str, object]] = []
        warnings = list(_as_str_list(report.get('warnings')))

        for candidate_id, patient in patients.items():
            decision = decision_by_candidate.get(candidate_id)
            if decision is None or decision.get('action') == 'skip':
                continue
            patient_id = self._resolve_patient_id(
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                patient=patient,
                decision=decision,
            )
            if decision.get('action') == 'create':
                created_patients += 1

            record_decisions = {
                str(item.get('group_id')): item
                for item in _as_dict_list(decision.get('record_groups'))
                if item.get('group_id')
            }
            for group in _as_dict_list(patient.get('record_groups')):
                group_id = str(group.get('group_id'))
                group_decision = record_decisions.get(group_id, {})
                if group_decision.get('action') == 'skip':
                    continue

                record_type = str(group_decision.get('record_type') or group.get('record_type') or 'other')
                event_date = _parse_date(str(group_decision.get('event_date') or group.get('event_date') or ''))
                if event_date is None:
                    raise ImportJobEventDateRequiredError(group_id=group_id)
                title = str(
                    group_decision.get('title') or group.get('title') or 'Импортированная запись',
                )[:255]
                duplicate_candidates = self._medical_records.find_duplicate_candidates(
                    actor_user_id=actor_user_id,
                    patient_passport_id=patient_id,
                    record_type=record_type,
                    event_date=event_date,
                    title=title,
                )
                if duplicate_candidates:
                    if group_decision.get('allow_possible_duplicate') is not True:
                        raise ImportJobDuplicateConfirmationRequiredError(group_id=group_id)
                    duplicate_overrides.append(
                        {
                            'group_id': group_id,
                            'matched_record_ids': [str(candidate.record_id) for candidate in duplicate_candidates],
                        },
                    )

                record = self._medical_records.create_record(
                    creator_user_id=actor_user_id,
                    patient_passport_id=patient_id,
                    author_practitioner_passport_id=None,
                    record_type=record_type,
                    event_date=event_date,
                    title=title,
                    appointment_location=None,
                    clinical_summary='Создано из импортированного архива.',
                    payload_json=_payload_json(
                        group=group,
                        job_id=job.id,
                        source_archive=job.original_filename,
                        resolved_by_user_id=actor_user_id,
                    ),
                )
                created_records += 1
                for file_info in _as_dict_list(group.get('files')):
                    path = str(file_info.get('path') or '')
                    try:
                        archive_file = self._archive_reader.read_file(archive_content=archive_content, path=path)
                    except ArchiveExtractionError:
                        warnings.append(f'Archive became unreadable during resolve: {path}')
                        continue
                    if archive_file is None:
                        warnings.append(f'File disappeared from archive during resolve: {path}')
                        continue
                    storage_key = f'records/{record.record.id}/{uuid4().hex}/{file_info.get("filename") or "file"}'
                    mime_type = str(file_info.get('mime_type') or archive_file.mime_type)
                    self._storage.upload(key=storage_key, content=archive_file.content, content_type=mime_type)
                    self._medical_records.add_attachment(
                        record_id=record.record.id,
                        comment_id=None,
                        uploaded_by_user_id=actor_user_id,
                        uploaded_by_fio=actor_fio,
                        category=_attachment_category(mime_type, str(group.get('record_type') or 'other')).value,
                        filename=str(file_info.get('filename') or archive_file.filename),
                        storage_key=storage_key,
                        mime_type=mime_type,
                        size_bytes=len(archive_file.content),
                    )
                    created_attachments += 1

        final_report = {
            **report,
            'message': 'Import resolved and medical records created',
            'patients_created': created_patients,
            'records_created': created_records,
            'attachments_created': created_attachments,
            'duplicate_overrides': duplicate_overrides,
            'warnings': warnings,
            'resolved_at': date.today().isoformat(),
        }
        updated = (
            self._import_jobs.mark_completed_with_warnings(job_id=job_id, report_json=final_report)
            if warnings
            else self._import_jobs.mark_completed(job_id=job_id, report_json=final_report)
        )
        if updated is None:
            raise ImportJobNotFoundError
        return _to_dto(updated)

    def _resolve_patient_id(
        self,
        *,
        actor_user_id: UUID,
        actor_role: str,
        patient: dict[str, object],
        decision: dict[str, object],
    ) -> UUID:
        action = decision.get('action')
        if action == 'existing':
            raw_patient_id = decision.get('patient_passport_id')
            if raw_patient_id is None:
                raise ImportJobValidationError
            try:
                patient_id = UUID(str(raw_patient_id))
            except ValueError as exc:
                raise ImportJobValidationError from exc
            existing = self._patient_cards.get_accessible_patient(
                patient_id=patient_id,
                user_id=actor_user_id,
                user_role=actor_role,
            )
            if existing is None:
                raise ImportJobValidationError
            return existing.id
        if action == 'create':
            created = self._patient_cards.create_patient_passport(
                created_by_user_id=actor_user_id,
                fio=str(decision.get('fio') or patient.get('fio') or 'Неизвестный пациент'),
                date_of_birth=_parse_date(str(decision.get('date_of_birth') or patient.get('date_of_birth') or '')),
                email=None,
                phone=None,
            )
            return created.id
        raise ImportJobValidationError


def _to_dto(job: ImportJob, report_json: dict[str, object] | None = None) -> ImportJobDTO:
    return ImportJobDTO(
        id=job.id,
        uploaded_by_user_id=job.uploaded_by_user_id,
        status=job.status.value,
        original_filename=job.original_filename,
        archive_storage_key=job.archive_storage_key,
        size_bytes=job.size_bytes,
        report_json=report_json if report_json is not None else job.report_json,
        review_decisions=job.review_decisions,
        review_updated_at=job.review_updated_at,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


def _as_dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _validate_review_draft(report: dict[str, object], decisions: list[dict[str, object]]) -> None:
    if len(decisions) > 500:
        raise ImportJobValidationError
    report_patients = {
        str(patient.get('candidate_id')): patient
        for patient in _as_dict_list(report.get('patients'))
        if patient.get('candidate_id')
    }
    seen_candidates: set[str] = set()
    for decision in decisions:
        candidate_id = str(decision.get('candidate_id') or '')
        if not candidate_id or candidate_id in seen_candidates or candidate_id not in report_patients:
            raise ImportJobValidationError
        seen_candidates.add(candidate_id)
        if decision.get('action') not in {'existing', 'create', 'skip'}:
            raise ImportJobValidationError

        report_groups = {
            str(group.get('group_id'))
            for group in _as_dict_list(report_patients[candidate_id].get('record_groups'))
            if group.get('group_id')
        }
        draft_groups = _as_dict_list(decision.get('record_groups'))
        if len(draft_groups) > 2_000:
            raise ImportJobValidationError
        seen_groups: set[str] = set()
        for group in draft_groups:
            group_id = str(group.get('group_id') or '')
            if not group_id or group_id in seen_groups or group_id not in report_groups:
                raise ImportJobValidationError
            seen_groups.add(group_id)
            if group.get('action') not in {'create', 'skip'}:
                raise ImportJobValidationError


def _payload_json(
    *,
    group: dict[str, object],
    job_id: UUID,
    source_archive: str | None,
    resolved_by_user_id: UUID,
) -> dict[str, object]:
    payload = group.get('payload_json')
    result = dict(payload) if isinstance(payload, dict) else {}
    result['import_provenance'] = {
        'source': 'archive',
        'import_job_id': str(job_id),
        'source_archive': source_archive,
        'resolved_by_user_id': str(resolved_by_user_id),
        'group_id': str(group.get('group_id') or ''),
        'event_date_candidates': [str(item) for item in _as_str_list(group.get('event_date_candidates'))],
        'files': [
            {
                'path': str(file_info.get('path') or ''),
                'filename': str(file_info.get('filename') or ''),
                'mime_type': str(file_info.get('mime_type') or ''),
                'size_bytes': _as_int(file_info.get('size_bytes')),
                'is_dicom': bool(file_info.get('is_dicom') or False),
            }
            for file_info in _as_dict_list(group.get('files'))
        ],
    }
    return result


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _attachment_category(mime_type: str, record_type: str) -> FileAttachmentCategory:
    if mime_type == 'application/dicom' or record_type == 'exam_result':
        return FileAttachmentCategory.IMAGING
    if record_type == 'lab_result':
        return FileAttachmentCategory.LAB
    if mime_type in {'application/pdf', 'image/jpeg', 'image/png'}:
        return FileAttachmentCategory.DOCUMENT
    return FileAttachmentCategory.OTHER
