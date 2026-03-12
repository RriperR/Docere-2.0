"""ORM-модели инфраструктурного слоя."""

from app.infrastructure.db.models.medical_record import MedicalRecordRow
from app.infrastructure.db.models.patient_passport import PatientPassportRow
from app.infrastructure.db.models.user import UserRow
from app.infrastructure.db.models.user_record_link import UserRecordLinkRow

__all__ = ['MedicalRecordRow', 'PatientPassportRow', 'UserRecordLinkRow', 'UserRow']
