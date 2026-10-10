"""Версии итога, закрытие и явная публикация в медицинской истории."""

from dataclasses import asdict
from datetime import date
from uuid import UUID, uuid4

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.dtos import (
    CaseView,
    ClosurePreview,
    ConclusionView,
    MaterialSummary,
    PageDTO,
    PublicationPreview,
    PublicationResult,
)
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.domain.clinical_cases import CaseConclusion, CaseError


class CaseConclusionsUseCase:
    """Версии итога, закрытие и явная публикация в медицинской истории."""

    def __init__(self, context: CaseContext) -> None:
        """Использовать общую политику доступа в текущей транзакции.

        Args:
            context: Общая политика доступа и репозитории текущей транзакции.
        """
        self.context = context

    def list_conclusions(self, case_id: UUID, user_id: UUID, offset: int, limit: int) -> PageDTO[ConclusionView]:
        """Прочитать версии только при полном доступе к клиническому контексту.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница версий итога доступного случая, начиная с последней.

        Raises:
            CaseError: При утрате доступа к источнику или контексту случая.
        """
        self.context.require_context(self.context.load(case_id, user_id), user_id)
        items, total = self.context.repository.conclusions(case_id, offset, limit)
        views = []
        for item in items:
            sources = []
            for record_id in item.source_ids:
                record = self.context.records.get_accessible_record(record_id, user_id)
                if record is None:
                    raise CaseError('Источник недоступен', 403)
                sources.append(
                    MaterialSummary(
                        record.record.id,
                        record.record.title,
                        None,
                        record.record.event_date,
                        str(record.record.record_type),
                        str(record.record.status),
                    )
                )
            views.append(ConclusionView(**asdict(item), sources=sources))
        return PageDTO(views, total)

    def save_conclusion(
        self,
        case_id: UUID,
        user_id: UUID,
        version: int,
        summary: str,
        findings: str,
        next_actions: str,
        source_ids: list[UUID],
    ) -> CaseConclusion:
        """Сохранить новую версию итога координатором до завершения разбора.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            version: Версия случая, прочитанная клиентом перед изменением.
            summary: Краткое резюме обсуждения.
            findings: Выводы координатора, не подразумевающие согласие других участников.
            next_actions: Предложенные дальнейшие действия.
            source_ids: Выбранные материалы-источники итога.

        Returns:
            Новая неизменяемая версия итога координатора.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        case.require_coordinator(user_id)
        case.require_writable()
        case.check_version(version)
        for record_id in source_ids:
            self.context.reference(case, user_id, record_id)
        _, total = self.context.repository.conclusions(case.id, 0, 1)
        result = self.context.repository.add_conclusion(
            CaseConclusion(
                uuid4(), case.id, total + 1, user_id, summary, findings, next_actions, list(dict.fromkeys(source_ids))
            )
        )
        case.version += 1
        self.context.changed(case, user_id, 'conclusion_updated', result.id, self.context.participants(case))
        self.context.repository.consume_work_draft(case.id, user_id, 'conclusion')
        return result

    def closure_preview(self, case_id: UUID, user_id: UUID) -> ClosurePreview:
        """Показать незавершённые запросы до явного подтверждения закрытия.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Число открытых запросов и версия случая перед подтверждением закрытия.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        case.require_coordinator(user_id)
        return ClosurePreview(self.context.repository.open_opinions(case.id), case.version)

    def close(self, case_id: UUID, user_id: UUID, version: int, cancel_open_requests: bool) -> CaseView:
        """Зафиксировать итог и явно отменить незавершённые запросы при необходимости.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            version: Версия случая, прочитанная клиентом перед изменением.
            cancel_open_requests: Явное согласие отменить оставшиеся запросы мнения при закрытии.

        Returns:
            Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        case.require_coordinator(user_id)
        case.require_writable()
        case.check_version(version)
        conclusions, _ = self.context.repository.conclusions(case.id, 0, 1)
        if not conclusions or not conclusions[0].summary.strip():
            raise CaseError('Для завершения сохраните непустой итог', 422)
        if self.context.repository.open_opinions(case.id):
            if not cancel_open_requests:
                raise CaseError('Есть незавершённые запросы. Подтвердите их отмену при закрытии')
            self.context.repository.cancel_open_opinions(case.id)
        for member in case.members:
            if member.status == 'pending':
                member.status = 'cancelled'
        case.status = 'closed'
        case.version += 1
        self.context.changed(case, user_id, 'closed', recipients=self.context.participants(case))
        return self.context.view(case, user_id)

    def publication_preview(self, case_id: UUID, user_id: UUID) -> PublicationPreview:
        """Подготовить запись, не публикуя её и не подтверждая автоматически.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Текст будущей записи, версия итога, источники и существующая публикация, если она есть.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        case.require_coordinator(user_id)
        if case.status != 'closed':
            raise CaseError('Публикация доступна после завершения разбора')
        conclusions, _ = self.context.repository.conclusions(case.id, 0, 1)
        if not conclusions:
            raise CaseError('Итог отсутствует')
        result = conclusions[0]
        text = '\n\n'.join(
            [result.summary, 'Выводы:\n' + result.findings, 'Дальнейшие действия:\n' + result.next_actions]
        )
        return PublicationPreview(
            title=f'Совместный разбор: {case.title}'[:255],
            clinical_summary=text,
            conclusion_id=result.id,
            conclusion_version=result.number,
            source_ids=result.source_ids,
            published_record_id=case.published_record_id,
        )

    def publish(
        self, case_id: UUID, actor: AuthenticatedUserDTO, event_date: date, creator: CreateMedicalRecordUseCase
    ) -> PublicationResult:
        """Идемпотентно создать независимую медицинскую запись существующим сценарием.

        Args:
            case_id: Идентификатор клинического случая.
            actor: Аутентифицированный пользователь, выполняющий действие.
            event_date: Дата медицинского события, заданная координатором.
            creator: Существующий сценарий создания медицинской записи в той же транзакции.

        Returns:
            Идентификатор самостоятельной записи; created=False при повторной публикации.
        """
        case = self.context.load(case_id, actor.id, lock=True)
        self.context.require_context(case, actor.id)
        case.require_coordinator(actor.id)
        self.context.validate_materials(case, case.record_ids)
        preview = self.publication_preview(case.id, actor.id)
        if case.published_record_id:
            return PublicationResult(case.published_record_id, False)
        record = creator.execute(
            CreateMedicalRecordDTO(
                actor_user_id=actor.id,
                actor_role=actor.role,
                actor_fio=actor.fio,
                actor_email=actor.email,
                actor_phone=actor.phone,
                patient_passport_id=case.patient_id,
                author_practitioner_passport_id=None,
                author_practitioner_full_name=None,
                author_practitioner_specialty=None,
                author_practitioner_organization=None,
                author_practitioner_position=None,
                author_practitioner_email=None,
                author_practitioner_phone=None,
                record_type='consultation_result',
                event_date=event_date,
                title=preview.title,
                appointment_location=None,
                clinical_summary=preview.clinical_summary,
                payload_json={
                    'case_provenance': {
                        'case_id': str(case.id),
                        'conclusion_id': str(preview.conclusion_id),
                        'conclusion_version': preview.conclusion_version,
                        'source_record_ids': [str(record_id) for record_id in preview.source_ids],
                        'participation_is_not_endorsement': True,
                    }
                },
            )
        )
        case.published_record_id = record.id
        case.version += 1
        self.context.changed(case, actor.id, 'published', record.id)
        return PublicationResult(record.id, True)
