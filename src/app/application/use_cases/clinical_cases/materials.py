"""Поиск выбранных материалов и проверка ссылок на документы."""

from uuid import UUID

from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.dtos import MaterialFilters, MaterialSummary, PageDTO
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.common.mappers import to_medical_record_dto
from app.domain.clinical_cases import CaseError


class CaseMaterialsUseCase:
    """Поиск выбранных материалов и проверка ссылок на документы."""

    def __init__(self, context: CaseContext) -> None:
        """Использовать общую политику доступа в текущей транзакции.

        Args:
            context: Общая политика доступа и репозитории текущей транзакции.
        """
        self.context = context

    def materials(
        self, case_id: UUID, user_id: UUID, filters: MaterialFilters, offset: int, limit: int
    ) -> PageDTO[MaterialSummary]:
        """Выбрать материалы; потеря одного источника блокирует весь поиск.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            filters: Поиск по метаданным и фильтры типа, даты события и подтверждения.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница найденных материалов без чтения содержимого PDF и сканов.
        """
        self.context.require_context(self.context.load(case_id, user_id), user_id)
        return self.context.repository.case_materials(case_id, filters, offset, limit)

    def material_details(self, case_id: UUID, user_id: UUID, record_id: UUID) -> MedicalRecordDTO:
        """Открыть запись только в контексте полностью доступного случая.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            record_id: Идентификатор записи, включённой в материалы случая.

        Returns:
            Доступная медицинская запись с её вложениями и комментариями.

        Raises:
            CaseError: Если действие запрещено ролью, членством, составом материалов или состоянием случая.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        self.context.reference(case, user_id, record_id)
        record = self.context.records.get_accessible_record(record_id, user_id)
        if record is None:
            raise CaseError('Материал недоступен', 403)
        return to_medical_record_dto(record)

    def authorize_attachment(self, case_id: UUID, user_id: UUID, record_id: UUID, attachment_id: UUID) -> None:
        """Проверить все материалы случая и соответствие вложения указанной записи.

        Args:
            case_id: Идентификатор клинического случая.
            user_id: Пользователь, для которого выполняется операция.
            record_id: Идентификатор записи, включённой в материалы случая.
            attachment_id: Вложение указанной медицинской записи.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        self.context.reference(case, user_id, record_id, attachment_id)

    def available_materials(
        self, patient_id: UUID, user_id: UUID, query: str, offset: int, limit: int
    ) -> PageDTO[MaterialSummary]:
        """Выбрать доступные врачу записи указанного пациента для включения в разбор.

        Args:
            patient_id: Идентификатор конкретного паспорта пациента.
            user_id: Пользователь, для которого выполняется операция.
            query: Текст для поиска по разрешённым полям.
            offset: Число элементов, пропускаемых перед страницей.
            limit: Максимальное число элементов страницы.

        Returns:
            Страница доступных врачу записей выбранного пациента и их общее число.
        """
        self.context.require_doctor(user_id)
        return self.context.repository.available_materials(patient_id, user_id, query, offset, limit)
