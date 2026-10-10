"""SQLAlchemy-хранилище клинических случаев и прав sharing."""

from uuid import UUID

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.application.use_cases.clinical_cases.dtos import (
    CaseActivityEntry,
    DoctorSummary,
    MaterialFilters,
    MaterialSummary,
    PageDTO,
)
from app.domain.case_drafts import DraftKind
from app.domain.clinical_cases import CaseConclusion, CaseError, CaseMember, CaseMessage, ClinicalCase, OpinionRequest
from app.domain.entities.medical_record import MedicalRecordStatus, MedicalRecordType
from app.infrastructure.adapters.repositories.share_requests.sqlalchemy_share_request_repository import (
    SqlAlchemyShareRequestRepositoryAdapter,
)
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.clinical_cases import (
    CaseConclusionRow,
    CaseDiscussionReadRow,
    CaseEventRow,
    CaseMaterialRow,
    CaseMemberRow,
    CaseMessageRow,
    CaseWorkDraftRow,
    ClinicalCaseRow,
    OpinionRequestRow,
)
from app.infrastructure.db.models.medical_records.file_attachment import FileAttachmentRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.record_share import (
    RecordShareRequestRow,
    RecordShareRow,
    RecordShareStatusRow,
)
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow, UserRecordLinkSourceRow
from app.infrastructure.db.record_access import active_record_access


class SqlAlchemyCaseRepository:
    """Персистентность агрегата; commit принадлежит HTTP boundary."""

    def __init__(self, session: Session) -> None:
        """Привязать хранение случаев и источников прав к текущей сессии.

        Args:
            session: SQLAlchemy-сессия текущей транзакции.
        """
        self.session = session

    def consume_work_draft(self, case_id: UUID, user_id: UUID, kind: DraftKind) -> None:
        """Очистить отправленный текст, сохранив версию для защиты другой вкладки.

        Args:
            case_id: Случай под блокировкой.
            user_id: Автор опубликованного текста.
            kind: Вид личной формы.
        """
        row = self.session.get(CaseWorkDraftRow, (case_id, user_id, kind))
        if row is not None:
            row.content = {}
            row.version += 1
            self.session.flush()

    def get(self, case_id: UUID, *, lock: bool = False) -> ClinicalCase | None:
        """Прочитать агрегат с блокировкой строки для сериализации изменений.

        Args:
            case_id: Идентификатор клинического случая.
            lock: Заблокировать строку случая до завершения транзакции изменения.

        Returns:
            Сохранённый агрегат или None, если идентификатор не существует.
        """
        query = select(ClinicalCaseRow).where(ClinicalCaseRow.id == case_id)
        if lock:
            query = query.with_for_update()
        row = self.session.scalar(query.execution_options(populate_existing=True))
        if row is None:
            return None
        members = self.session.scalars(select(CaseMemberRow).where(CaseMemberRow.case_id == case_id)).all()
        records = list(
            self.session.scalars(select(CaseMaterialRow.record_id).where(CaseMaterialRow.case_id == case_id))
        )
        return ClinicalCase(
            row.id,
            row.patient_id,
            row.coordinator_id,
            row.title,
            row.question,
            row.status,
            row.version,
            row.previous_case_id,
            records,
            [
                CaseMember(m.user_id, m.status, self.doctor_name(m.user_id), m.share_request_id, m.read_sequence)
                for m in members
            ],
            row.created_at,
            row.sequence,
            row.published_record_id,
        )

    def save(self, case: ClinicalCase) -> None:
        """Сохранить агрегат и ссылки на документы без изменения самих записей.

        Args:
            case: Агрегат текущего разбора.
        """
        row = self.session.get(ClinicalCaseRow, case.id)
        if row is None:
            row = ClinicalCaseRow(id=case.id, patient_id=case.patient_id, coordinator_id=case.coordinator_id)
            self.session.add(row)
        row.title = case.title
        row.question = case.question
        row.status = case.status
        row.version = case.version
        row.previous_case_id = case.previous_case_id
        row.sequence = case.sequence
        row.published_record_id = case.published_record_id
        self.session.flush()
        case.created_at = row.created_at
        old = self.session.scalars(select(CaseMaterialRow).where(CaseMaterialRow.case_id == case.id)).all()
        for material in old:
            if material.record_id not in case.record_ids:
                self.session.delete(material)
        existing = {m.record_id for m in old}
        for record_id in case.record_ids:
            if record_id not in existing:
                self.session.add(CaseMaterialRow(case_id=case.id, record_id=record_id))
        for member in case.members:
            m = self.session.get(CaseMemberRow, (case.id, member.user_id))
            if m is None:
                m = CaseMemberRow(case_id=case.id, user_id=member.user_id)
                self.session.add(m)
            m.status, m.share_request_id, m.read_sequence = member.status, member.share_request_id, member.read_sequence
        self.session.flush()

    def list_for(
        self, user_id: UUID, *, scope: str, status: str | None, offset: int, limit: int
    ) -> tuple[list[ClinicalCase], int]:
        """Пагинировать по членству без загрузки всей истории пациента.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            scope: Отбор всех случаев, координируемых или с участием пользователя.
            status: Состояние случая для фильтрации.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Случаи выбранной страницы и общее число случаев до пагинации.
        """
        member = select(CaseMemberRow.case_id).where(
            CaseMemberRow.user_id == user_id, CaseMemberRow.status.in_(['pending', 'accepted'])
        )
        condition = ClinicalCaseRow.coordinator_id == user_id
        if scope == 'participating':
            condition = ClinicalCaseRow.id.in_(member)
        elif scope == 'all':
            condition = or_(condition, ClinicalCaseRow.id.in_(member))
        query = select(ClinicalCaseRow.id).where(condition)
        if status:
            query = query.where(ClinicalCaseRow.status == status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        ids = self.session.scalars(
            query.order_by(ClinicalCaseRow.created_at.desc(), ClinicalCaseRow.id).offset(offset).limit(limit)
        )
        cases = [case for case_id in ids if (case := self.get(case_id)) is not None]
        return cases, total

    def is_doctor(self, user_id: UUID) -> bool:
        """Проверить актуальную роль и блокировку учётной записи.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            True только для зарегистрированного активного пользователя с ролью врача.
        """
        return (
            self.session.scalar(
                select(UserRow.id).where(
                    UserRow.id == user_id, UserRow.role == UserRole.DOCTOR, UserRow.status == UserStatus.ACTIVE
                )
            )
            is not None
        )

    def has_material_access(self, record_ids: list[UUID], user_id: UUID) -> bool:
        """Проверить ACL всех материалов одним запросом, не читая документы и комментарии.

        Args:
            record_ids: Идентификаторы выбранных записей.
            user_id: Пользователь, чей доступ проверяется.

        Returns:
            True, если каждая существующая запись имеет хотя бы одно действующее право.
        """
        selected = set(record_ids)
        if not selected:
            return True
        accessible = self.session.scalar(
            select(func.count(func.distinct(UserRecordLinkRow.record_id)))
            .join(MedicalRecordRow, MedicalRecordRow.id == UserRecordLinkRow.record_id)
            .where(
                UserRecordLinkRow.user_id == user_id, UserRecordLinkRow.record_id.in_(selected), active_record_access()
            )
        )
        return accessible == len(selected)

    def doctor_name(self, user_id: UUID) -> str:
        """Вернуть публичное имя врача без медицинских сведений.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Публичное имя врача либо нейтральная подпись, если профиль отсутствует.
        """
        return self.session.scalar(select(UserRow.fio).where(UserRow.id == user_id)) or 'Врач'

    def search_doctors(self, user_id: UUID, query: str) -> list[DoctorSummary]:
        """Найти только активных зарегистрированных врачей.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            query: Текст для поиска по разрешённым полям.

        Returns:
            Список активных врачей, соответствующих имени или email, кроме самого пользователя.
        """
        rows = self.session.scalars(
            select(UserRow)
            .where(
                UserRow.id != user_id,
                UserRow.role == UserRole.DOCTOR,
                UserRow.status == UserStatus.ACTIVE,
                or_(UserRow.fio.ilike(f'%{query}%'), UserRow.email.ilike(f'%{query}%')),
            )
            .order_by(UserRow.fio)
            .limit(10)
        )
        return [DoctorSummary(row.id, row.fio, row.email) for row in rows]

    def grant(self, case: ClinicalCase, user_id: UUID, record_ids: list[UUID] | None = None) -> UUID:
        """Выдать отдельный источник ACL для всех актуальных материалов случая.

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.
            record_ids: Выбранные записи одного пациента.

        Returns:
            Идентификатор принятого sharing-запроса, помеченного происхождением от случая.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        member = case.member(user_id)
        request = (
            self.session.get(RecordShareRequestRow, member.share_request_id)
            if member and member.share_request_id
            else None
        )
        if request is None or request.status != RecordShareStatusRow.ACCEPTED:
            request = RecordShareRequestRow(
                from_user_id=case.coordinator_id,
                to_user_id=user_id,
                clinical_case_id=case.id,
                status=RecordShareStatusRow.ACCEPTED,
            )
            self.session.add(request)
            self.session.flush()
        for record_id in case.record_ids if record_ids is None else record_ids:
            link = self.session.scalar(
                select(UserRecordLinkRow).where(
                    UserRecordLinkRow.user_id == user_id,
                    UserRecordLinkRow.record_id == record_id,
                    UserRecordLinkRow.clinical_case_id == case.id,
                )
            )
            if link is None:
                origin = self.session.scalar(
                    select(UserRecordLinkRow)
                    .where(
                        UserRecordLinkRow.user_id == case.coordinator_id,
                        UserRecordLinkRow.record_id == record_id,
                        active_record_access(),
                    )
                    .order_by(UserRecordLinkRow.expires_at.desc().nulls_first())
                    .limit(1)
                )
                if origin is None:
                    raise CaseError('Координатор потерял доступ к материалу', 403)
                share = RecordShareRow(
                    request_id=request.id,
                    record_id=record_id,
                    patient_passport_id=case.patient_id,
                    status=RecordShareStatusRow.ACCEPTED,
                )
                self.session.add(share)
                self.session.flush()
                self.session.add(
                    UserRecordLinkRow(
                        user_id=user_id,
                        record_id=record_id,
                        patient_passport_id=case.patient_id,
                        source=UserRecordLinkSourceRow.SHARE_ACCEPTED,
                        source_record_share_id=share.id,
                        clinical_case_id=case.id,
                        expires_at=origin.expires_at,
                    )
                )
        self.session.flush()
        return request.id

    def revoke(self, case: ClinicalCase, user_id: UUID) -> None:
        """Отозвать только права этого случая существующим каскадным механизмом.

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.
        """
        requests = self.session.scalars(
            select(RecordShareRequestRow.id).where(
                RecordShareRequestRow.clinical_case_id == case.id,
                RecordShareRequestRow.to_user_id == user_id,
                RecordShareRequestRow.status == RecordShareStatusRow.ACCEPTED,
            )
        )
        for request_id in list(requests):
            SqlAlchemyShareRequestRepositoryAdapter(self.session).revoke_case_request(
                request_id=request_id,
                user_id=case.coordinator_id,
            )

    def available_materials(
        self, patient_id: UUID, user_id: UUID, query: str, offset: int, limit: int
    ) -> PageDTO[MaterialSummary]:
        """Выбрать страницу доступных материалов пациента без загрузки полной истории.

        Args:
            patient_id: Идентификатор конкретного паспорта пациента.
            user_id: Пользователь, для которого выполняется операция.
            query: Текст для поиска по разрешённым полям.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница доступных врачу записей выбранного пациента и их общее число.
        """
        access = exists(
            select(UserRecordLinkRow.id).where(
                UserRecordLinkRow.user_id == user_id,
                UserRecordLinkRow.record_id == MedicalRecordRow.id,
                UserRecordLinkRow.patient_passport_id == patient_id,
                active_record_access(),
            )
        )
        statement = select(MedicalRecordRow).where(access)
        if query:
            statement = statement.where(
                or_(MedicalRecordRow.title.ilike(f'%{query}%'), MedicalRecordRow.clinical_summary.ilike(f'%{query}%'))
            )
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(
            statement.order_by(MedicalRecordRow.event_date, MedicalRecordRow.id).offset(offset).limit(limit)
        )
        return PageDTO([self._material(row) for row in rows], total)

    def message(self, message_id: UUID) -> CaseMessage | None:
        """Получить неизменяемое сообщение; доступ проверяет прикладной сценарий.

        Args:
            message_id: Идентификатор реплики в обсуждении случая.

        Returns:
            Реплика по идентификатору либо None; проверка контекста выполняется в use case.
        """
        row = self.session.get(CaseMessageRow, message_id)
        return self._message(row) if row else None

    def find_message(self, case_id: UUID, author_id: UUID, key: UUID) -> CaseMessage | None:
        """Найти результат идемпотентной отправки.

        Args:
            case_id: Идентификатор случая.
            author_id: Автор отправленного сообщения.
            key: Ключ повторной отправки.

        Returns:
            Ранее отправленная реплика с этим ключом либо None.
        """
        row = self.session.scalar(
            select(CaseMessageRow).where(
                CaseMessageRow.case_id == case_id,
                CaseMessageRow.author_id == author_id,
                CaseMessageRow.idempotency_key == key,
            )
        )
        return self._message(row) if row else None

    def add_message(self, message: CaseMessage) -> CaseMessage:
        """Сохранить новую реплику; обновлений и удалений сообщений нет.

        Args:
            message: Новая неизменяемая реплика со ссылками и ключом идемпотентности.

        Returns:
            Сохранённая реплика с временем создания и именем автора.
        """
        row = CaseMessageRow(
            id=message.id,
            case_id=message.case_id,
            author_id=message.author_id,
            body=message.body,
            idempotency_key=message.idempotency_key,
            sequence=message.sequence,
            parent_id=message.parent_id,
            record_id=message.record_id,
            attachment_id=message.attachment_id,
            opinion_id=message.opinion_id,
        )
        self.session.add(row)
        self.session.flush()
        return self._message(row)

    def _message(self, row: CaseMessageRow) -> CaseMessage:
        return CaseMessage(
            row.id,
            row.case_id,
            row.author_id,
            row.body,
            row.idempotency_key,
            row.sequence,
            row.parent_id,
            row.record_id,
            row.attachment_id,
            row.opinion_id,
            row.created_at,
            self.doctor_name(row.author_id),
        )

    def messages(self, case_id: UUID, offset: int, limit: int, query: str = '') -> tuple[list[CaseMessage], int]:
        """Пагинировать сообщения, не загружая весь чат в память клиента.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.
            query: Текст для поиска по разрешённым полям.

        Returns:
            Реплики выбранной страницы и общее число совпадений до пагинации.
        """
        statement = select(CaseMessageRow).where(CaseMessageRow.case_id == case_id)
        if query:
            statement = statement.where(CaseMessageRow.body.ilike(f'%{query}%'))
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(statement.order_by(CaseMessageRow.sequence.desc()).offset(offset).limit(limit))
        return [self._message(row) for row in rows], total

    def opinion(self, opinion_id: UUID) -> OpinionRequest | None:
        """Получить запрос мнения; ACL применяется в use case.

        Args:
            opinion_id: Идентификатор адресного запроса мнения.

        Returns:
            Адресный запрос либо None; проверка контекста выполняется в use case.
        """
        row = self.session.get(OpinionRequestRow, opinion_id)
        return self._opinion(row) if row else None

    @staticmethod
    def _opinion(row: OpinionRequestRow) -> OpinionRequest:
        return OpinionRequest(
            row.id,
            row.case_id,
            row.requester_id,
            row.assignee_id,
            row.question,
            row.status,
            row.record_id,
            row.reason,
            row.response_message_id,
            row.created_at,
        )

    def opinions(self, case_id: UUID, offset: int, limit: int) -> tuple[list[OpinionRequest], int]:
        """Выбрать страницу запросов мнения.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Запросы выбранной страницы и их общее число.
        """
        statement = select(OpinionRequestRow).where(OpinionRequestRow.case_id == case_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(
            statement.order_by(OpinionRequestRow.created_at.desc(), OpinionRequestRow.id).offset(offset).limit(limit)
        )
        return [self._opinion(row) for row in rows], total

    def save_opinion(self, opinion: OpinionRequest) -> None:
        """Сохранить запрос или его новое состояние.

        Args:
            opinion: Адресный запрос с обновлённым состоянием.
        """
        row = self.session.get(OpinionRequestRow, opinion.id)
        if row is None:
            row = OpinionRequestRow(
                id=opinion.id,
                case_id=opinion.case_id,
                requester_id=opinion.requester_id,
                assignee_id=opinion.assignee_id,
                question=opinion.question,
                record_id=opinion.record_id,
            )
            self.session.add(row)
        row.status, row.reason, row.response_message_id = opinion.status, opinion.reason, opinion.response_message_id
        self.session.flush()
        opinion.created_at = row.created_at

    def cancel_assignee_opinions(self, case_id: UUID, user_id: UUID) -> None:
        """Закрыть запросы вышедшему адресату с устойчивой причиной.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
        """
        self.session.execute(
            update(OpinionRequestRow)
            .where(
                OpinionRequestRow.case_id == case_id,
                OpinionRequestRow.assignee_id == user_id,
                OpinionRequestRow.status == 'open',
            )
            .values(status='cancelled', reason='assignee_left')
        )

    def emit(
        self, case: ClinicalCase, actor_id: UUID, event_type: str, subject_id: UUID | None, recipients: list[UUID]
    ) -> None:
        """Сохранить событие и адресатов без текста пациента, документов и обсуждения.

        Args:
            case: Агрегат текущего разбора.
            actor_id: Автор действия для журнала событий.
            event_type: Тип изменения без медицинского текста.
            subject_id: Объект, связанный с событием.
            recipients: Адресаты уведомления; автор исключается при сохранении события.
        """
        self.session.add(
            CaseEventRow(
                case_id=case.id,
                sequence=case.sequence,
                actor_id=actor_id,
                event_type=event_type,
                subject_id=subject_id,
                recipients=[str(u) for u in recipients],
            )
        )
        self.session.flush()

    def activity(self, case_id: UUID, offset: int, limit: int) -> PageDTO[CaseActivityEntry]:
        """Прочитать страницу журнала действий.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница событий с авторами и ссылками без копирования клинического текста.
        """
        statement = select(CaseEventRow).where(CaseEventRow.case_id == case_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(statement.order_by(CaseEventRow.sequence.desc()).offset(offset).limit(limit))
        return PageDTO(
            [
                CaseActivityEntry(
                    row.id,
                    row.sequence,
                    row.event_type,
                    row.actor_id,
                    self.doctor_name(row.actor_id),
                    row.subject_id,
                    row.created_at,
                )
                for row in rows
            ],
            total,
        )

    def conclusions(self, case_id: UUID, offset: int, limit: int) -> tuple[list[CaseConclusion], int]:
        """Выбрать страницу неизменяемых версий итога.

        Args:
            case_id: Идентификатор клинического случая.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Версии итога, начиная с последней, и их общее число.
        """
        statement = select(CaseConclusionRow).where(CaseConclusionRow.case_id == case_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(statement.order_by(CaseConclusionRow.number.desc()).offset(offset).limit(limit))
        return [self._conclusion(row) for row in rows], total

    @staticmethod
    def _conclusion(row: CaseConclusionRow) -> CaseConclusion:
        return CaseConclusion(
            row.id,
            row.case_id,
            row.number,
            row.author_id,
            row.summary,
            row.findings,
            row.next_actions,
            [UUID(value) for value in row.source_ids],
            row.created_at,
        )

    def add_conclusion(self, conclusion: CaseConclusion) -> CaseConclusion:
        """Добавить строку новой версии без перезаписи предыдущих.

        Args:
            conclusion: Новая версия итога со ссылками на материалы.

        Returns:
            Сохранённая новая версия итога с временем создания.
        """
        row = CaseConclusionRow(
            id=conclusion.id,
            case_id=conclusion.case_id,
            number=conclusion.number,
            author_id=conclusion.author_id,
            summary=conclusion.summary,
            findings=conclusion.findings,
            next_actions=conclusion.next_actions,
            source_ids=[str(value) for value in conclusion.source_ids],
        )
        self.session.add(row)
        self.session.flush()
        return self._conclusion(row)

    def open_opinions(self, case_id: UUID) -> int:
        """Посчитать открытые запросы перед закрытием случая.

        Args:
            case_id: Идентификатор клинического случая.

        Returns:
            Число запросов в состоянии open.
        """
        return (
            self.session.scalar(
                select(func.count())
                .select_from(OpinionRequestRow)
                .where(OpinionRequestRow.case_id == case_id, OpinionRequestRow.status == 'open')
            )
            or 0
        )

    def cancel_open_opinions(self, case_id: UUID) -> None:
        """Отменить запросы с зафиксированной причиной завершения обсуждения.

        Args:
            case_id: Идентификатор клинического случая.
        """
        self.session.execute(
            update(OpinionRequestRow)
            .where(OpinionRequestRow.case_id == case_id, OpinionRequestRow.status == 'open')
            .values(status='cancelled', reason='case_closed')
        )

    def case_materials(
        self, case_id: UUID, filters: MaterialFilters, offset: int, limit: int
    ) -> PageDTO[MaterialSummary]:
        """Поиск только по ссылкам выбранного случая, с пагинацией в SQL.

        Args:
            case_id: Идентификатор клинического случая.
            filters: Поиск по метаданным и фильтры типа, даты события и подтверждения.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница выбранных материалов, удовлетворяющих фильтрам, и общее число совпадений.
        """
        statement = select(MedicalRecordRow).join(CaseMaterialRow, CaseMaterialRow.record_id == MedicalRecordRow.id)
        statement = statement.where(CaseMaterialRow.case_id == case_id)
        if filters.query:
            pattern = f'%{filters.query}%'
            filename = exists(
                select(FileAttachmentRow.id).where(
                    FileAttachmentRow.record_id == MedicalRecordRow.id, FileAttachmentRow.filename.ilike(pattern)
                )
            )
            statement = statement.where(
                or_(MedicalRecordRow.title.ilike(pattern), MedicalRecordRow.clinical_summary.ilike(pattern), filename)
            )
        if filters.record_type:
            statement = statement.where(MedicalRecordRow.record_type == MedicalRecordType(filters.record_type))
        if filters.status:
            statement = statement.where(MedicalRecordRow.status == MedicalRecordStatus(filters.status))
        if filters.date_from:
            statement = statement.where(MedicalRecordRow.event_date >= filters.date_from)
        if filters.date_to:
            statement = statement.where(MedicalRecordRow.event_date <= filters.date_to)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(
            statement.order_by(MedicalRecordRow.event_date, MedicalRecordRow.id).offset(offset).limit(limit)
        )
        return PageDTO([self._material(row) for row in rows], total)

    def unread_messages(self, case_id: UUID, user_id: UUID) -> int:
        """Посчитать чужие сообщения после позиции прочтения.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Число чужих реплик после сохранённой позиции прочтения.
        """
        marker = self.session.get(CaseDiscussionReadRow, (case_id, user_id))
        return (
            self.session.scalar(
                select(func.count())
                .select_from(CaseMessageRow)
                .where(
                    CaseMessageRow.case_id == case_id,
                    CaseMessageRow.author_id != user_id,
                    CaseMessageRow.sequence > (marker.sequence if marker else 0),
                )
            )
            or 0
        )

    def mark_discussion_read(self, case_id: UUID, user_id: UUID, sequence: int) -> None:
        """Продвинуть курсор без уменьшения при повторе или старом ответе.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            sequence: Последовательность событий, до которой пользователь прочитал обсуждение.
        """
        marker = self.session.get(CaseDiscussionReadRow, (case_id, user_id))
        if marker is None:
            self.session.add(CaseDiscussionReadRow(case_id=case_id, user_id=user_id, sequence=sequence))
        else:
            marker.sequence = max(marker.sequence, sequence)

    def cases_for_user(self, user_id: UUID) -> list[UUID]:
        """Найти владение и действующие участия, включая непринятые приглашения.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Идентификаторы координируемых случаев и действующих приглашений/участий.
        """
        memberships = select(CaseMemberRow.case_id).where(
            CaseMemberRow.user_id == user_id, CaseMemberRow.status.in_(['pending', 'accepted'])
        )
        return list(
            self.session.scalars(
                select(ClinicalCaseRow.id)
                .where(or_(ClinicalCaseRow.coordinator_id == user_id, ClinicalCaseRow.id.in_(memberships)))
                .order_by(ClinicalCaseRow.id)
            )
        )

    def inactive_users(self, limit: int) -> list[UUID]:
        """Найти недействующих врачей, всё ещё участвующих в разборе.

        Args:
            limit: Максимальное число элементов страницы.

        Returns:
            Не более limit заблокированных или утративших роль врачей с незавершённым участием.
        """
        members = select(CaseMemberRow.user_id).where(CaseMemberRow.status.in_(['pending', 'accepted']))
        coordinators = select(ClinicalCaseRow.coordinator_id).where(
            ClinicalCaseRow.id.in_(
                select(CaseMemberRow.case_id).where(CaseMemberRow.status.in_(['pending', 'accepted']))
            )
        )
        return list(
            self.session.scalars(
                select(UserRow.id)
                .where(
                    or_(UserRow.id.in_(members), UserRow.id.in_(coordinators)),
                    or_(UserRow.role != UserRole.DOCTOR, UserRow.status != UserStatus.ACTIVE),
                )
                .order_by(UserRow.id)
                .limit(limit)
            )
        )

    @staticmethod
    def _material(row: MedicalRecordRow) -> MaterialSummary:
        return MaterialSummary(
            row.id, row.title, row.clinical_summary, row.event_date, row.record_type.value, row.status.value
        )
