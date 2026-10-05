"""SQLAlchemy-хранилище клинических случаев и прав sharing."""

from uuid import UUID

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.orm import Session

from app.domain.clinical_cases import CaseConclusion, CaseMember, CaseMessage, ClinicalCase, OpinionRequest
from app.infrastructure.adapters.repositories.share_requests.sqlalchemy_share_request_repository import (
    SqlAlchemyShareRequestRepositoryAdapter,
)
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.clinical_cases import (
    CaseConclusionRow,
    CaseEventRow,
    CaseMaterialRow,
    CaseMemberRow,
    CaseMessageRow,
    ClinicalCaseRow,
    OpinionRequestRow,
)
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
        """Инициализировать зависимости сценария.

        Args:
            session: Текущая транзакционная сессия.
        """
        self.session = session

    def get(self, case_id: UUID, *, lock: bool = False) -> ClinicalCase | None:
        """Прочитать агрегат с блокировкой строки для сериализации изменений.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            case_id: Идентификатор случая.
            lock: Параметр операции.
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
        for name in ('title', 'question', 'status', 'version', 'previous_case_id', 'sequence', 'published_record_id'):
            setattr(row, name, getattr(case, name))
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

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            user_id: Текущий пользователь.
            scope: Параметр операции.
            status: Параметр операции.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
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

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            user_id: Текущий пользователь.
        """
        return (
            self.session.scalar(
                select(UserRow.id).where(
                    UserRow.id == user_id, UserRow.role == UserRole.DOCTOR, UserRow.status == UserStatus.ACTIVE
                )
            )
            is not None
        )

    def doctor_name(self, user_id: UUID) -> str:
        """Вернуть публичное имя врача без медицинских сведений.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            user_id: Текущий пользователь.
        """
        return self.session.scalar(select(UserRow.fio).where(UserRow.id == user_id)) or 'Врач'

    def search_doctors(self, user_id: UUID, query: str) -> list[dict[str, str]]:
        """Найти только активных зарегистрированных врачей.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            user_id: Текущий пользователь.
            query: Поисковая строка.
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
        return [{'id': str(row.id), 'name': row.fio, 'email': row.email} for row in rows]

    def grant(self, case: ClinicalCase, user_id: UUID) -> UUID:
        """Выдать отдельный источник ACL для всех актуальных материалов случая.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
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
        for record_id in case.record_ids:
            link = self.session.scalar(
                select(UserRecordLinkRow).where(
                    UserRecordLinkRow.user_id == user_id,
                    UserRecordLinkRow.record_id == record_id,
                    UserRecordLinkRow.clinical_case_id == case.id,
                )
            )
            if link is None:
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
                    )
                )
        self.session.flush()
        return request.id

    def revoke(self, case: ClinicalCase, user_id: UUID) -> None:
        """Отозвать только права этого случая существующим каскадным механизмом.

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
        """
        member = case.member(user_id)
        if member and member.share_request_id:
            SqlAlchemyShareRequestRepositoryAdapter(self.session).revoke_case_request(
                request_id=member.share_request_id,
                user_id=case.coordinator_id,
            )

    def available_materials(
        self, patient_id: UUID, user_id: UUID, query: str, offset: int, limit: int
    ) -> dict[str, object]:
        """Выбрать страницу доступных материалов пациента без загрузки полной истории.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            patient_id: Параметр операции.
            user_id: Текущий пользователь.
            query: Поисковая строка.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
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
        return {
            'items': [
                {
                    'id': row.id,
                    'title': row.title,
                    'clinical_summary': row.clinical_summary,
                    'event_date': row.event_date,
                    'record_type': row.record_type.value,
                    'status': row.status.value,
                }
                for row in rows
            ],
            'total': total,
        }

    def message(self, message_id: UUID) -> CaseMessage | None:
        """Получить неизменяемое сообщение; доступ проверяет прикладной сценарий.

        Args:
            message_id: Параметр операции.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        row = self.session.get(CaseMessageRow, message_id)
        return self._message(row) if row else None

    def find_message(self, case_id: UUID, author_id: UUID, key: UUID) -> CaseMessage | None:
        """Найти результат идемпотентной отправки.

        Args:
            case_id: Идентификатор случая.
            author_id: Параметр операции.
            key: Ключ повторной отправки.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            message: Неизменяемая реплика.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
            query: Поисковая строка.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            opinion_id: Адресный запрос.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            opinion: Адресный запрос.
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
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
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
            actor_id: Автор действия.
            event_type: Тип доменного действия.
            subject_id: Целевой объект события.
            recipients: Получатели события.
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

    def activity(self, case_id: UUID, offset: int, limit: int) -> dict[str, object]:
        """Прочитать страницу журнала действий.

        Args:
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        statement = select(CaseEventRow).where(CaseEventRow.case_id == case_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.scalars(statement.order_by(CaseEventRow.sequence.desc()).offset(offset).limit(limit))
        return {
            'items': [
                {
                    'id': row.id,
                    'sequence': row.sequence,
                    'event_type': row.event_type,
                    'actor_id': row.actor_id,
                    'actor_name': self.doctor_name(row.actor_id),
                    'subject_id': row.subject_id,
                    'created_at': row.created_at,
                }
                for row in rows
            ],
            'total': total,
        }

    def conclusions(self, case_id: UUID, offset: int, limit: int) -> tuple[list[CaseConclusion], int]:
        """Выбрать страницу неизменяемых версий итога.

        Args:
            case_id: Идентификатор случая.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            conclusion: Параметр операции.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            case_id: Идентификатор случая.

        Returns:
            Результат сценария в контексте текущего пользователя.
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
            case_id: Идентификатор случая.
        """
        self.session.execute(
            update(OpinionRequestRow)
            .where(OpinionRequestRow.case_id == case_id, OpinionRequestRow.status == 'open')
            .values(status='cancelled', reason='case_closed')
        )
