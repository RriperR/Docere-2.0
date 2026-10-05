"""Сценарии создания случая, приглашения и управления доступом."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.ports.clinical_cases import CaseRepositoryPort
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.domain.clinical_cases import CaseError, CaseMember, CaseMessage, ClinicalCase, OpinionRequest


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
        """Инициализировать зависимости сценария.

        Args:
            repository: Параметр операции.
            records: Параметр операции.
        """
        self.repository = repository
        self.records = records

    def require_doctor(self, user_id: UUID) -> None:
        """Проверить актуальный статус и роль, независимо от содержимого JWT.

        Raises:
            CaseError: При нарушении условий операции.

        Args:
            user_id: Текущий пользователь.
        """
        if not self.repository.is_doctor(user_id):
            raise CaseError('Участие доступно активному врачу', 403)

    def load(self, case_id: UUID, user_id: UUID, *, lock: bool = False) -> ClinicalCase:
        """Получить случай только для координатора или известного участника.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            lock: Параметр операции.
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

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
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

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
        """
        if not self.accessible(case, user_id):
            raise CaseError('Клинический контекст недоступен', 403)

    def view(self, case: ClinicalCase, user_id: UUID) -> CaseView:
        """Не включать название, пациента, вопрос и документы в нейтральную карточку.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
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

        Args:
            user_id: Текущий пользователь.
            scope: Параметр операции.
            status: Параметр операции.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
        """
        self.require_doctor(user_id)
        cases, total = self.repository.list_for(user_id, scope=scope, status=status, offset=offset, limit=limit)
        return {'items': [self.view(case, user_id) for case in cases], 'total': total}

    def validate_materials(self, case: ClinicalCase, record_ids: list[UUID]) -> None:
        """Проверить выбранные записи в проекции пациента координатора.

        Raises:
            CaseError: При нарушении условий операции.

        Args:
            case: Агрегат текущего разбора.
            record_ids: Выбранные записи одного пациента.
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

        Args:
            user_id: Текущий пользователь.
            patient_id: Параметр операции.
            title: Параметр операции.
            question: Параметр операции.
            record_ids: Выбранные записи одного пациента.
            previous_case_id: Параметр операции.
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
        self.changed(case, user_id, 'case_created' if case.version == 1 else 'draft_updated')
        return self.view(case, user_id)

    def update_draft(
        self, case_id: UUID, user_id: UUID, version: int, title: str, question: str, record_ids: list[UUID]
    ) -> CaseView:
        """Изменить описание и набор материалов только в черновике.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            version: Версия, прочитанная клиентом.
            title: Параметр операции.
            question: Параметр операции.
            record_ids: Выбранные записи одного пациента.
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
        self.changed(case, user_id, 'case_created' if case.version == 1 else 'draft_updated')
        return self.view(case, user_id)

    def add_materials(self, case_id: UUID, user_id: UUID, version: int, record_ids: list[UUID]) -> CaseView:
        """Добавить записи и выдать права участникам атомарно.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            version: Версия, прочитанная клиентом.
            record_ids: Выбранные записи одного пациента.
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
        self.changed(case, user_id, 'materials_added', recipients=self.participants(case))
        return self.view(case, user_id)

    def invite(self, case_id: UUID, user_id: UUID, target_id: UUID, version: int) -> CaseView:
        """Пригласить активного врача, не выдавая доступ до принятия.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            target_id: Параметр операции.
            version: Версия, прочитанная клиентом.
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
        self.changed(case, user_id, 'invitation', subject_id=target_id, recipients=[target_id])
        return self.view(case, user_id)

    def membership(self, case_id: UUID, user_id: UUID, action: str, target_id: UUID | None = None) -> CaseView:
        """Принять, отклонить, отозвать приглашение, исключить врача или выйти.

        Returns:
            Результат операции в контексте доступа текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            action: Параметр операции.
            target_id: Параметр операции.
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
            self.repository.cancel_assignee_opinions(case.id, target_id)
            member.status = 'left' if action == 'leave' else 'removed'
        else:
            raise CaseError('Неизвестное действие', 422)
        case.version += 1
        self.changed(case, user_id, action, subject_id=target_id, recipients=[case.coordinator_id])
        return self.view(case, user_id)

    @staticmethod
    def participants(case: ClinicalCase) -> list[UUID]:
        """Вернуть адресатов общих изменений; рассылка исключает автора.

        Args:
            case: Агрегат текущего разбора.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        return [case.coordinator_id, *[m.user_id for m in case.members if m.status == 'accepted']]

    def changed(
        self,
        case: ClinicalCase,
        actor_id: UUID,
        event_type: str,
        subject_id: UUID | None = None,
        recipients: list[UUID] | None = None,
    ) -> None:
        """Сохранить агрегат и событие атомарно; событие не содержит клинического текста.

        Args:
            case: Агрегат текущего разбора.
            actor_id: Автор действия.
            event_type: Тип доменного действия.
            subject_id: Целевой объект события.
            recipients: Получатели события.
        """
        case.sequence += 1
        self.repository.save(case)
        self.repository.emit(
            case, actor_id, event_type, subject_id, [u for u in dict.fromkeys(recipients or []) if u != actor_id]
        )

    def reference(
        self, case: ClinicalCase, user_id: UUID, record_id: UUID | None, attachment_id: UUID | None = None
    ) -> None:
        """Проверить принадлежность записи случаю и вложения этой записи.

        Args:
            case: Агрегат текущего разбора.
            user_id: Текущий пользователь.
            record_id: Ссылка на выбранный материал.
            attachment_id: Вложение указанного материала.

        Raises:
            CaseError: При нарушении условий операции.
        """
        if attachment_id and not record_id:
            raise CaseError('Для вложения укажите материал', 422)
        if record_id:
            if record_id not in case.record_ids:
                raise CaseError('Материал не входит в случай', 404)
            if self.records.get_accessible_record(record_id, user_id) is None:
                raise CaseError('Материал недоступен', 403)
        if attachment_id:
            attachment = self.records.get_attachment(attachment_id=attachment_id)
            if attachment is None or attachment.record_id != record_id:
                raise CaseError('Вложение не найдено в указанном материале', 404)

    def discussion(self, case_id: UUID, user_id: UUID, offset: int, limit: int, query: str = '') -> dict[str, object]:
        """Прочитать страницу обсуждения только при полном доступе к контексту.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.
            query: Поисковая строка.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        case = self.load(case_id, user_id)
        self.require_context(case, user_id)
        items, total = self.repository.messages(case.id, offset, limit, query)
        return {'items': items, 'total': total, 'sequence': case.sequence}

    def send_message(
        self,
        case_id: UUID,
        user_id: UUID,
        body: str,
        key: UUID,
        parent_id: UUID | None = None,
        record_id: UUID | None = None,
        attachment_id: UUID | None = None,
        opinion_id: UUID | None = None,
    ) -> CaseMessage:
        """Отправить сообщение или ответ без изменения уже опубликованных реплик.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            body: Текст сообщения.
            key: Ключ повторной отправки.
            parent_id: Сообщение первого уровня.
            record_id: Ссылка на выбранный материал.
            attachment_id: Вложение указанного материала.
            opinion_id: Адресный запрос.

        Returns:
            Результат сценария в контексте текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        case = self.load(case_id, user_id, lock=True)
        self.require_context(case, user_id)
        existing = self.repository.find_message(case.id, user_id, key)
        if existing:
            if (existing.body, existing.parent_id, existing.record_id, existing.attachment_id, existing.opinion_id) != (
                body,
                parent_id,
                record_id,
                attachment_id,
                opinion_id,
            ):
                raise CaseError('Ключ повторного запроса уже использован для другого сообщения')
            return existing
        case.require_writable()
        self.reference(case, user_id, record_id, attachment_id)
        recipients: list[UUID] = []
        if parent_id:
            parent = self.repository.message(parent_id)
            if parent is None or parent.case_id != case.id or parent.parent_id is not None:
                raise CaseError('Можно ответить только на сообщение первого уровня', 422)
            recipients = [parent.author_id]
        opinion = self.repository.opinion(opinion_id) if opinion_id else None
        if opinion_id:
            if opinion is None or opinion.case_id != case.id:
                raise CaseError('Запрос мнения не найден', 404)
            if opinion.assignee_id != user_id:
                raise CaseError('Ответить может только адресат', 403)
            if opinion.status != 'open':
                raise CaseError('Запрос уже завершён')
            recipients.append(opinion.requester_id)
        message = self.repository.add_message(
            CaseMessage(
                uuid4(), case.id, user_id, body, key, case.sequence + 1, parent_id, record_id, attachment_id, opinion_id
            )
        )
        if opinion:
            opinion.status, opinion.response_message_id = 'answered', message.id
            self.repository.save_opinion(opinion)
        self.changed(
            case,
            user_id,
            'opinion_answered' if opinion else ('message_reply' if parent_id else 'message'),
            subject_id=message.id,
            recipients=recipients,
        )
        return message

    def request_opinion(
        self, case_id: UUID, user_id: UUID, assignee_id: UUID, question: str, record_id: UUID | None = None
    ) -> OpinionRequest:
        """Адресовать вопрос другому действующему участнику.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            assignee_id: Параметр операции.
            question: Параметр операции.
            record_id: Ссылка на выбранный материал.

        Returns:
            Результат сценария в контексте текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        case = self.load(case_id, user_id, lock=True)
        self.require_context(case, user_id)
        case.require_writable()
        self.require_context(case, assignee_id)
        if user_id == assignee_id:
            raise CaseError('Выберите другого участника', 422)
        self.reference(case, user_id, record_id)
        opinion = OpinionRequest(uuid4(), case.id, user_id, assignee_id, question, record_id=record_id)
        self.repository.save_opinion(opinion)
        self.changed(case, user_id, 'opinion_requested', opinion.id, [assignee_id])
        return opinion

    def cancel_opinion(self, case_id: UUID, user_id: UUID, opinion_id: UUID) -> OpinionRequest:
        """Отменить открытый запрос автором или координатором.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            opinion_id: Адресный запрос.

        Returns:
            Результат сценария в контексте текущего пользователя.

        Raises:
            CaseError: При нарушении условий операции.
        """
        case = self.load(case_id, user_id, lock=True)
        self.require_context(case, user_id)
        case.require_writable()
        opinion = self.repository.opinion(opinion_id)
        if opinion is None or opinion.case_id != case.id:
            raise CaseError('Запрос не найден', 404)
        if user_id not in {case.coordinator_id, opinion.requester_id}:
            raise CaseError('Отмена доступна автору или координатору', 403)
        if opinion.status != 'open':
            raise CaseError('Запрос уже завершён')
        opinion.status, opinion.reason = 'cancelled', 'cancelled_by_user'
        self.repository.save_opinion(opinion)
        self.changed(case, user_id, 'opinion_cancelled', opinion.id)
        return opinion

    def list_opinions(self, case_id: UUID, user_id: UUID, offset: int, limit: int) -> dict[str, object]:
        """Прочитать страницу запросов при доступе ко всему контексту.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        self.require_context(self.load(case_id, user_id), user_id)
        items, total = self.repository.opinions(case_id, offset, limit)
        return {'items': items, 'total': total}

    def activity(self, case_id: UUID, user_id: UUID, offset: int, limit: int) -> dict[str, object]:
        """Прочитать журнал только участнику с полным доступом.

        Args:
            case_id: Идентификатор случая.
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        self.require_context(self.load(case_id, user_id), user_id)
        return self.repository.activity(case_id, offset, limit)
