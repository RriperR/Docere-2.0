"""DTO сценария получения медицинской записи."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GetMedicalRecordDTO:
    """Входной DTO для получения медицинской записи."""

    record_id: UUID
    user_id: UUID
