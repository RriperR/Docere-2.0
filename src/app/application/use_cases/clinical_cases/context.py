"""Общие проверки доступа и транзакционные операции клинического разбора."""

from uuid import UUID

from app.application.ports.clinical_cases import CaseRepositoryPort
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.clinical_cases.dtos import CaseView
from app.domain.clinical_cases import CaseError, ClinicalCase


class CaseContext:
    """Единая политика доступа, ссылок и записи событий для сценариев случая."""

    def __init__(self, repository: CaseRepositoryPort, records: MedicalRecordRepositoryPort) -> None:
        """Связать политику случая с хранилищами текущей транзакции.

        Args:
            repository: Хранилище случаев, членства и событий в текущей транзакции.
            records: Репозиторий медицинских записей для проверки пациента, источников и вложений.
        """
        self.repository = repository
        self.records = records

    def require_doctor(self, user_id: UUID) -> None:
        """Проверить актуальный статус и роль, независимо от содержимого JWT.

        Args:
            user_id: Пользователь, для которого выполняется операция.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        if not self.repository.is_doctor(user_id):
            raise CaseError('Участие доступно активному врачу', 403)

    def load(self, case_id: UUID, user_id: UUID, *, lock: bool = False) -> ClinicalCase:
        """Получить случай только для координатора или известного участника.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            lock: Заблокировать строку случая до завершения транзакции изменения.

        Returns:
            Агрегат известного случая; чтение клинического содержимого требует отдельного require_context.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
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

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            True, если врач имеет действующее членство и доступ ко всем материалам при активном координаторе.
        """
        member = case.member(user_id)
        return (
            self.repository.is_doctor(user_id)
            and self.repository.is_doctor(case.coordinator_id)
            and (case.coordinator_id == user_id or (member is not None and member.status == 'accepted'))
            and self.repository.has_material_access(case.record_ids, user_id)
        )

    def require_context(self, case: ClinicalCase, user_id: UUID) -> None:
        """Защитить чтение, поиск и изменение всего клинического контекста.

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        if not self.accessible(case, user_id):
            raise CaseError('Клинический контекст недоступен', 403)

    def view(self, case: ClinicalCase, user_id: UUID) -> CaseView:
        """Не включать название, пациента, вопрос и документы в нейтральную карточку.

        Args:
            case: Агрегат текущего разбора.
            user_id: Пользователь, для которого выполняется операция.

        Returns:
            Карточка с клиническим контекстом либо нейтральными метаданными без пациента и текста.
        """
        accessible = self.accessible(case, user_id)
        member = case.member(user_id)
        patient = self.records.get_patient_passport(patient_passport_id=case.patient_id) if accessible else None
        return CaseView(
            case.id,
            case.status,
            'coordinator' if case.coordinator_id == user_id else (member.status if member else 'unavailable'),
            case.coordinator_id,
            self.repository.doctor_name(case.coordinator_id),
            len(case.record_ids),
            accessible,
            case if accessible else None,
            self.repository.unread_messages(case.id, user_id) if accessible else 0,
            patient.fio if patient else None,
            tuple(case.members) if user_id == case.coordinator_id else (),
        )

    def validate_materials(self, case: ClinicalCase, record_ids: list[UUID]) -> None:
        """Проверить выбранные записи в проекции пациента координатора.

        Args:
            case: Агрегат текущего разбора.
            record_ids: Выбранные записи одного пациента.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        if not self.records.user_can_access_patient_passport(
            user_id=case.coordinator_id, user_role='doctor', patient_passport_id=case.patient_id
        ):
            raise CaseError('Пациент недоступен', 403)
        for record_id in record_ids:
            record = self.records.get_accessible_record(record_id, case.coordinator_id)
            if record is None or record.patient_passport_id != case.patient_id:
                raise CaseError('Материал недоступен или относится к другому пациенту', 403)

    @staticmethod
    def participants(case: ClinicalCase) -> list[UUID]:
        """Вернуть адресатов общих изменений; рассылка исключает автора.

        Args:
            case: Агрегат текущего разбора.

        Returns:
            Координатор и принявшие приглашение участники; автор исключается при записи события.
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
            actor_id: Автор действия для журнала событий.
            event_type: Тип изменения без медицинского текста.
            subject_id: Объект, связанный с событием.
            recipients: Адресаты уведомления; автор исключается при сохранении события.
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
            user_id: Пользователь, для которого выполняется операция.
            record_id: Идентификатор записи, включённой в материалы случая.
            attachment_id: Вложение указанной медицинской записи.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
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
