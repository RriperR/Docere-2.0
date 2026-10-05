"""SQLAlchemy-хранилище клинических случаев и прав sharing."""

from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.domain.clinical_cases import CaseMember, ClinicalCase
from app.infrastructure.adapters.repositories.share_requests.sqlalchemy_share_request_repository import (
    SqlAlchemyShareRequestRepositoryAdapter,
)
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.clinical_cases import CaseMaterialRow, CaseMemberRow, ClinicalCaseRow
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
        """Инициализировать зависимости сценария."""
        self.session = session

    def get(self, case_id: UUID, *, lock: bool = False) -> ClinicalCase | None:
        """Прочитать агрегат с блокировкой строки для сериализации изменений.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
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
        """Сохранить агрегат и ссылки на документы без изменения самих записей."""
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
        """
        return self.session.scalar(select(UserRow.fio).where(UserRow.id == user_id)) or 'Врач'

    def search_doctors(self, user_id: UUID, query: str) -> list[dict[str, str]]:
        """Найти только активных зарегистрированных врачей.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
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
        """Отозвать только права этого случая существующим каскадным механизмом."""
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
