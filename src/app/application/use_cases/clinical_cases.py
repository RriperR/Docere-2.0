"""Сценарии создания случая, приглашения и управления доступом."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.ports.clinical_cases import CaseRepositoryPort
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.domain.clinical_cases import CaseError, CaseMember, ClinicalCase


@dataclass(frozen=True)
class CaseView:
    """Безопасная проекция: клинический контекст присутствует только при полном доступе."""

    id: UUID
    status: str
    membership_status: str
    coordinator_id: UUID
    coordinator_name: str
    material_count: int
    accessible: bool
    case: ClinicalCase | None
    invitation_terms: str = 'Координатор сможет добавлять новые материалы этого пациента в совместный разбор.'


class ClinicalCasesUseCase:
    """Оркестрация правил случая через репозитории в одной транзакции."""

    def __init__(self, repository: CaseRepositoryPort, records: MedicalRecordRepositoryPort) -> None:
        """Инициализировать зависимости сценария."""
        self.repository = repository
        self.records = records

    def require_doctor(self, user_id: UUID) -> None:
        """Проверить актуальный статус и роль, независимо от содержимого JWT.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if not self.repository.is_doctor(user_id):
            raise CaseError('Участие доступно активному врачу', 403)

    def load(self, case_id: UUID, user_id: UUID, *, lock: bool = False) -> ClinicalCase:
        """Получить случай только для координатора или известного участника.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        self.require_doctor(user_id)
        case = self.repository.get(case_id, lock=lock)
        if case is None:
            raise CaseError('Случай не найден', 404)
        member = case.member(user_id)
        if user_id != case.coordinator_id and (member is None or member.status not in {'pending', 'accepted'}):
            raise CaseError('Случай не найден', 404)
        return case

    def accessible(self, case: ClinicalCase, user_id: UUID) -> bool:
        """Проверить членство и доступ ко всем материалам без частичного раскрытия.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
        """
        member = case.member(user_id)
        return (
            self.repository.is_doctor(user_id)
            and self.repository.is_doctor(case.coordinator_id)
            and (case.coordinator_id == user_id or (member is not None and member.status == 'accepted'))
            and all(self.records.get_accessible_record(record_id, user_id) is not None for record_id in case.record_ids)
        )

    def require_context(self, case: ClinicalCase, user_id: UUID) -> None:
        """Защитить чтение, поиск и изменение всего клинического контекста.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if not self.accessible(case, user_id):
            raise CaseError('Клинический контекст недоступен', 403)

    def view(self, case: ClinicalCase, user_id: UUID) -> CaseView:
        """Не включать название, пациента, вопрос и документы в нейтральную карточку.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
        """
        accessible = self.accessible(case, user_id)
        member = case.member(user_id)
        return CaseView(
            case.id,
            case.status,
            'coordinator' if case.coordinator_id == user_id else (member.status if member else 'unavailable'),
            case.coordinator_id,
            self.repository.doctor_name(case.coordinator_id),
            len(case.record_ids),
            accessible,
            case if accessible else None,
        )

    def list_cases(
        self, user_id: UUID, *, scope: str, status: str | None, offset: int, limit: int
    ) -> dict[str, object]:
        """Вернуть страницу случаев с независимой проверкой каждой карточки.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
        """
        self.require_doctor(user_id)
        cases, total = self.repository.list_for(user_id, scope=scope, status=status, offset=offset, limit=limit)
        return {'items': [self.view(case, user_id) for case in cases], 'total': total}

    def validate_materials(self, case: ClinicalCase, record_ids: list[UUID]) -> None:
        """Проверить выбранные записи в проекции пациента координатора.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if not self.records.user_can_access_patient_passport(
            user_id=case.coordinator_id, user_role='doctor', patient_passport_id=case.patient_id
        ):
            raise CaseError('Пациент недоступен', 403)
        for record_id in record_ids:
            record = self.records.get_accessible_record(record_id, case.coordinator_id)
            if record is None or record.patient_passport_id != case.patient_id:
                raise CaseError('Материал недоступен или относится к другому пациенту', 403)

    def create(
        self,
        user_id: UUID,
        patient_id: UUID,
        title: str,
        question: str,
        record_ids: list[UUID],
        previous_case_id: UUID | None = None,
    ) -> CaseView:
        """Создать черновик одного пациента без эвристического объединения людей.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
        """
        self.require_doctor(user_id)
        if previous_case_id:
            self.require_context(self.load(previous_case_id, user_id), user_id)
        case = ClinicalCase(
            uuid4(),
            patient_id,
            user_id,
            title,
            question,
            previous_case_id=previous_case_id,
            record_ids=list(dict.fromkeys(record_ids)),
        )
        self.validate_materials(case, case.record_ids)
        self.repository.save(case)
        return self.view(case, user_id)

    def update_draft(
        self, case_id: UUID, user_id: UUID, version: int, title: str, question: str, record_ids: list[UUID]
    ) -> CaseView:
        """Изменить описание и набор материалов только в черновике.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        case = self.load(case_id, user_id, lock=True)
        case.require_coordinator(user_id)
        self.require_context(case, user_id)
        case.check_version(version)
        if case.status != 'draft':
            raise CaseError('Редактирование описания и удаление материалов доступно только в черновике')
        self.validate_materials(case, record_ids)
        case.title, case.question, case.record_ids = title, question, list(dict.fromkeys(record_ids))
        case.version += 1
        self.repository.save(case)
        return self.view(case, user_id)

    def add_materials(self, case_id: UUID, user_id: UUID, version: int, record_ids: list[UUID]) -> CaseView:
        """Добавить записи и выдать права участникам атомарно.

        Returns:
            Результат операции в контексте доступа текущего пользователя.
        """
        case = self.load(case_id, user_id, lock=True)
        case.require_coordinator(user_id)
        self.require_context(case, user_id)
        case.require_writable()
        case.check_version(version)
        self.validate_materials(case, record_ids)
        case.record_ids = list(dict.fromkeys([*case.record_ids, *record_ids]))
        case.version += 1
        self.repository.save(case)
        for member in case.members:
            if member.status == 'accepted' and self.repository.is_doctor(member.user_id):
                self.repository.grant(case, member.user_id)
        return self.view(case, user_id)

    def invite(self, case_id: UUID, user_id: UUID, target_id: UUID, version: int) -> CaseView:
        """Пригласить активного врача, не выдавая доступ до принятия.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        case = self.load(case_id, user_id, lock=True)
        case.require_coordinator(user_id)
        self.require_context(case, user_id)
        case.require_writable()
        case.check_version(version)
        self.require_doctor(target_id)
        if target_id == user_id:
            raise CaseError('Нельзя приглашать себя', 422)
        member = case.member(target_id)
        if member and member.status in {'pending', 'accepted'}:
            raise CaseError('У врача уже есть действующее приглашение или участие')
        if not case.record_ids:
            raise CaseError('Добавьте хотя бы один материал')
        if member:
            member.status = 'pending'
        else:
            case.members.append(CaseMember(target_id, name=self.repository.doctor_name(target_id)))
        case.status = 'active'
        case.version += 1
        self.repository.save(case)
        return self.view(case, user_id)

    def membership(self, case_id: UUID, user_id: UUID, action: str, target_id: UUID | None = None) -> CaseView:
        """Принять, отклонить, отозвать приглашение, исключить врача или выйти.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        case = self.load(case_id, user_id, lock=True)
        target_id = target_id or user_id
        if action in {'remove', 'cancel'}:
            case.require_coordinator(user_id)
        elif target_id != user_id:
            raise CaseError('Недоступное действие', 403)
        member = case.member(target_id)
        if member is None:
            raise CaseError('Приглашение не найдено', 404)
        if action == 'accept':
            if member.status == 'accepted':
                return self.view(case, user_id)
            if member.status != 'pending' or case.status != 'active':
                raise CaseError('Приглашение недействительно')
            self.require_doctor(case.coordinator_id)
            self.validate_materials(case, case.record_ids)
            member.status = 'accepted'
            member.share_request_id = self.repository.grant(case, target_id)
        elif action in {'decline', 'cancel'}:
            if member.status != 'pending':
                raise CaseError('Приглашение уже обработано')
            member.status = 'declined' if action == 'decline' else 'cancelled'
        elif action in {'leave', 'remove'}:
            if member.status != 'accepted':
                raise CaseError('Участие уже завершено')
            self.repository.revoke(case, target_id)
            member.status = 'left' if action == 'leave' else 'removed'
        else:
            raise CaseError('Неизвестное действие', 422)
        case.version += 1
        self.repository.save(case)
        return self.view(case, user_id)
