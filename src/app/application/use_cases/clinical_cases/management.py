"""Создание случая, состав материалов и жизненный цикл участия."""

from uuid import UUID, uuid4

from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.dtos import CaseView, DoctorSummary, PageDTO
from app.domain.clinical_cases import CaseError, CaseMember, ClinicalCase


class ClinicalCasesUseCase:
    """Создание случая, состав материалов и жизненный цикл участия."""

    def __init__(self, context: CaseContext) -> None:
        """Использовать общую политику доступа в текущей транзакции.

        Args:
            context: Общая политика доступа и репозитории текущей транзакции.
        """
        self.context = context

    def list_cases(
        self, user_id: UUID, *, scope: str, status: str | None, offset: int, limit: int
    ) -> PageDTO[CaseView]:
        """Вернуть страницу случаев с независимой проверкой каждой карточки.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            scope: Отбор всех случаев, координируемых или с участием пользователя.
            status: Состояние случая для фильтрации.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница безопасных карточек, проверенных для текущего пользователя.
        """
        self.context.require_doctor(user_id)
        cases, total = self.context.repository.list_for(user_id, scope=scope, status=status, offset=offset, limit=limit)
        return PageDTO([self.context.view(case, user_id) for case in cases], total)

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

        Args:
            user_id: Пользователь, для которого выполняется операция.
            patient_id: Идентификатор конкретного паспорта пациента.
            title: Название клинического разбора.
            question: Вопрос, адресованный участникам разбора.
            record_ids: Выбранные записи одного пациента.
            previous_case_id: Предыдущий случай того же пациента; его доступ проверяется отдельно.

        Returns:
            Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        self.context.require_doctor(user_id)
        if previous_case_id:
            previous = self.context.load(previous_case_id, user_id)
            self.context.require_context(previous, user_id)
            if previous.patient_id != patient_id:
                raise CaseError('Продолжение должно относиться к тому же пациенту', 422)
        case = ClinicalCase(
            uuid4(),
            patient_id,
            user_id,
            title,
            question,
            previous_case_id=previous_case_id,
            record_ids=list(dict.fromkeys(record_ids)),
        )
        self.context.validate_materials(case, case.record_ids)
        self.context.changed(case, user_id, 'case_created')
        return self.context.view(case, user_id)

    def update_draft(
        self, case_id: UUID, user_id: UUID, version: int, title: str, question: str, record_ids: list[UUID]
    ) -> CaseView:
        """Изменить описание и набор материалов только в черновике.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            version: Версия случая, прочитанная клиентом перед изменением.
            title: Название клинического разбора.
            question: Вопрос, адресованный участникам разбора.
            record_ids: Выбранные записи одного пациента.

        Returns:
            Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
        case.require_coordinator(user_id)
        self.context.require_context(case, user_id)
        case.check_version(version)
        if case.status != 'draft':
            raise CaseError('Редактирование описания и удаление материалов доступно только в черновике')
        self.context.validate_materials(case, record_ids)
        case.title, case.question, case.record_ids = title, question, list(dict.fromkeys(record_ids))
        case.version += 1
        self.context.changed(case, user_id, 'draft_updated')
        return self.context.view(case, user_id)

    def add_materials(self, case_id: UUID, user_id: UUID, version: int, record_ids: list[UUID]) -> CaseView:
        """Добавить записи и выдать права участникам атомарно.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            version: Версия случая, прочитанная клиентом перед изменением.
            record_ids: Выбранные записи одного пациента.

        Returns:
            Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
        """
        case = self.context.load(case_id, user_id, lock=True)
        case.require_coordinator(user_id)
        self.context.require_context(case, user_id)
        case.require_writable()
        case.check_version(version)
        self.context.validate_materials(case, record_ids)
        added = list(dict.fromkeys(record_id for record_id in record_ids if record_id not in case.record_ids))
        case.record_ids.extend(added)
        case.version += 1
        self.context.repository.save(case)
        for member in case.members:
            if added and member.status == 'accepted' and self.context.repository.is_doctor(member.user_id):
                member.share_request_id = self.context.repository.grant(case, member.user_id, added)
        self.context.changed(case, user_id, 'materials_added', recipients=self.context.participants(case))
        return self.context.view(case, user_id)

    def invite(self, case_id: UUID, user_id: UUID, target_id: UUID, version: int) -> CaseView:
        """Пригласить активного врача, не выдавая доступ до принятия.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            target_id: Врач, которого приглашают или чьё участие изменяют.
            version: Версия случая, прочитанная клиентом перед изменением.

        Returns:
            Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
        case.require_coordinator(user_id)
        self.context.require_context(case, user_id)
        case.require_writable()
        case.check_version(version)
        self.context.require_doctor(target_id)
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
            case.members.append(CaseMember(target_id, name=self.context.repository.doctor_name(target_id)))
        case.status = 'active'
        case.version += 1
        self.context.changed(case, user_id, 'invitation', subject_id=target_id, recipients=[target_id])
        return self.context.view(case, user_id)

    def membership(self, case_id: UUID, user_id: UUID, action: str, target_id: UUID | None = None) -> CaseView:
        """Принять, отклонить, отозвать приглашение, исключить врача или выйти.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            action: Действие с приглашением или членством.
            target_id: Врач, которого приглашают или чьё участие изменяют.

        Returns:
            Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
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
                return self.context.view(case, user_id)
            if member.status != 'pending' or case.status != 'active':
                raise CaseError('Приглашение недействительно')
            self.context.require_doctor(case.coordinator_id)
            self.context.validate_materials(case, case.record_ids)
            member.status = 'accepted'
            member.share_request_id = self.context.repository.grant(case, target_id)
        elif action in {'decline', 'cancel'}:
            if member.status != 'pending':
                raise CaseError('Приглашение уже обработано')
            member.status = 'declined' if action == 'decline' else 'cancelled'
        elif action in {'leave', 'remove'}:
            if member.status != 'accepted':
                raise CaseError('Участие уже завершено')
            self.context.repository.revoke(case, target_id)
            self.context.repository.cancel_assignee_opinions(case.id, target_id)
            member.status = 'left' if action == 'leave' else 'removed'
        else:
            raise CaseError('Неизвестное действие', 422)
        case.version += 1
        self.context.changed(case, user_id, action, subject_id=target_id, recipients=[case.coordinator_id])
        return self.context.view(case, user_id)

    def terminate_user(self, user_id: UUID, actor_id: UUID) -> None:
        """Прекратить участие и каскадно отозвать права без восстановления при разблокировке.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            actor_id: Автор действия для журнала событий.
        """
        for case_id in self.context.repository.cases_for_user(user_id):
            case = self.context.repository.get(case_id, lock=True)
            if case is None:
                continue
            targets = (
                case.members if case.coordinator_id == user_id else [m for m in case.members if m.user_id == user_id]
            )
            changed = False
            for member in targets:
                if member.status == 'accepted':
                    self.context.repository.revoke(case, member.user_id)
                    self.context.repository.cancel_assignee_opinions(case.id, member.user_id)
                    member.status = 'removed'
                    changed = True
                elif member.status == 'pending':
                    member.status = 'cancelled'
                    changed = True
            if case.coordinator_id == user_id:
                self.context.repository.cancel_open_opinions(case.id)
            if changed:
                case.version += 1
                self.context.changed(case, actor_id, 'participation_terminated', user_id, [case.coordinator_id])

    def search_doctors(self, user_id: UUID, query: str) -> list[DoctorSummary]:
        """Найти активных коллег после проверки роли текущего пользователя.

        Args:
            user_id: Пользователь, для которого выполняется операция.
            query: Текст для поиска по разрешённым полям.

        Returns:
            Список активных врачей, соответствующих имени или email, кроме самого пользователя.
        """
        self.context.require_doctor(user_id)
        return self.context.repository.search_doctors(user_id, query)
