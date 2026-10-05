"""Неизменяемые реплики, запросы мнения и журнал клинического разбора."""

from uuid import UUID, uuid4

from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.dtos import CaseActivityEntry, DiscussionPage, PageDTO
from app.domain.clinical_cases import CaseError, CaseMessage, OpinionRequest


class CaseDiscussionUseCase:
    """Неизменяемые реплики, запросы мнения и журнал клинического разбора."""

    def __init__(self, context: CaseContext) -> None:
        """Использовать общую политику доступа в текущей транзакции.

        Args:
            context: Общая политика доступа и репозитории текущей транзакции.
        """
        self.context = context

    def discussion(self, case_id: UUID, user_id: UUID, offset: int, limit: int, query: str = '') -> DiscussionPage:
        """Прочитать страницу обсуждения только при полном доступе к контексту.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.
            query: Текст для поиска по разрешённым полям.

        Returns:
            Страница реплик с последовательностью событий случая для позиции чтения.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        items, total = self.context.repository.messages(case.id, offset, limit, query)
        return DiscussionPage(items, total, case.sequence)

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
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            body: Текст новой неизменяемой реплики.
            key: Ключ идемпотентной отправки сообщения.
            parent_id: Сообщение первого уровня, на которое дан ответ.
            record_id: Идентификатор записи, включённой в материалы случая.
            attachment_id: Вложение указанной медицинской записи.
            opinion_id: Идентификатор адресного запроса мнения.

        Returns:
            Новая реплика либо ранее созданный результат запроса с тем же ключом.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        existing = self.context.repository.find_message(case.id, user_id, key)
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
        self.context.reference(case, user_id, record_id, attachment_id)
        recipients: list[UUID] = []
        if parent_id:
            parent = self.context.repository.message(parent_id)
            if parent is None or parent.case_id != case.id or parent.parent_id is not None:
                raise CaseError('Можно ответить только на сообщение первого уровня', 422)
            recipients = [parent.author_id]
        opinion = self.context.repository.opinion(opinion_id) if opinion_id else None
        if opinion_id:
            if opinion is None or opinion.case_id != case.id:
                raise CaseError('Запрос мнения не найден', 404)
            if opinion.assignee_id != user_id:
                raise CaseError('Ответить может только адресат', 403)
            if opinion.status != 'open':
                raise CaseError('Запрос уже завершён')
            recipients.append(opinion.requester_id)
        message = self.context.repository.add_message(
            CaseMessage(
                uuid4(), case.id, user_id, body, key, case.sequence + 1, parent_id, record_id, attachment_id, opinion_id
            )
        )
        if opinion:
            opinion.status, opinion.response_message_id = 'answered', message.id
            self.context.repository.save_opinion(opinion)
        self.context.changed(
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
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            assignee_id: Другой действующий участник, которому адресован вопрос.
            question: Вопрос, адресованный участникам разбора.
            record_id: Идентификатор записи, включённой в материалы случая.

        Returns:
            Созданный открытый запрос назначенному участнику.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        case.require_writable()
        self.context.require_context(case, assignee_id)
        if user_id == assignee_id:
            raise CaseError('Выберите другого участника', 422)
        self.context.reference(case, user_id, record_id)
        opinion = OpinionRequest(uuid4(), case.id, user_id, assignee_id, question, record_id=record_id)
        self.context.repository.save_opinion(opinion)
        self.context.changed(case, user_id, 'opinion_requested', opinion.id, [assignee_id])
        return opinion

    def cancel_opinion(self, case_id: UUID, user_id: UUID, opinion_id: UUID) -> OpinionRequest:
        """Отменить открытый запрос автором или координатором.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            opinion_id: Идентификатор адресного запроса мнения.

        Returns:
            Отменённый запрос с зафиксированной причиной.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        case.require_writable()
        opinion = self.context.repository.opinion(opinion_id)
        if opinion is None or opinion.case_id != case.id:
            raise CaseError('Запрос не найден', 404)
        if user_id not in {case.coordinator_id, opinion.requester_id}:
            raise CaseError('Отмена доступна автору или координатору', 403)
        if opinion.status != 'open':
            raise CaseError('Запрос уже завершён')
        opinion.status, opinion.reason = 'cancelled', 'cancelled_by_user'
        self.context.repository.save_opinion(opinion)
        self.context.changed(case, user_id, 'opinion_cancelled', opinion.id)
        return opinion

    def list_opinions(self, case_id: UUID, user_id: UUID, offset: int, limit: int) -> PageDTO[OpinionRequest]:
        """Прочитать страницу запросов при доступе ко всему контексту.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница запросов мнения доступного случая.
        """
        self.context.require_context(self.context.load(case_id, user_id), user_id)
        items, total = self.context.repository.opinions(case_id, offset, limit)
        return PageDTO(items, total)

    def activity(self, case_id: UUID, user_id: UUID, offset: int, limit: int) -> PageDTO[CaseActivityEntry]:
        """Прочитать журнал только участнику с полным доступом.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница событий с авторами и ссылками без копирования клинического текста.
        """
        self.context.require_context(self.context.load(case_id, user_id), user_id)
        return self.context.repository.activity(case_id, offset, limit)

    def get_message(self, case_id: UUID, user_id: UUID, message_id: UUID) -> CaseMessage:
        """Открыть исходную реплику или целевое уведомление без обхода ACL.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            message_id: Идентификатор реплики в обсуждении случая.

        Returns:
            Реплика проверенного случая либо ошибка, если ссылка относится к другому случаю.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        message = self.context.repository.message(message_id)
        if message is None or message.case_id != case.id:
            raise CaseError('Сообщение не найдено', 404)
        return message

    def mark_read(self, case_id: UUID, user_id: UUID, sequence: int) -> None:
        """Прочитать обсуждение независимо от отметок уведомлений.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            sequence: Последовательность событий, до которой пользователь прочитал обсуждение.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        self.context.repository.mark_discussion_read(case.id, user_id, min(sequence, case.sequence))
