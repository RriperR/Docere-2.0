"""Загрузка демонстрационных данных в базу.

Модуль содержит единый источник правды для наполнения базы связным набором
демо-данных. Логика используется management-командой `seed-demo`.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.application.ports.security.password_hasher import PasswordHasherPort
from app.domain.entities.file_attachment import FileAttachmentCategory
from app.domain.entities.medical_record import MedicalRecordStatus, MedicalRecordType
from app.domain.entities.patient_passport import PatientPassportStatus
from app.domain.entities.practitioner_passport import PractitionerPassportStatus
from app.infrastructure.db.models import (
    FileAttachmentRow,
    MedicalRecordRow,
    PatientPassportRow,
    PractitionerPassportRow,
    RecordCommentRow,
    UserRecordLinkRow,
    UserRecordLinkSourceRow,
    UserRole,
    UserRow,
    UserStatus,
)
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.medical_records.record_share import (
    RecordShareRequestRow,
    RecordShareRow,
    RecordShareStatusRow,
)

DEFAULT_DEMO_PASSWORD = 'DemoPass123'  # noqa: S105 — общий пароль демо-учёток

# Таблицы очищаются в порядке, обратном зависимостям внешних ключей.
_TABLES_IN_DELETE_ORDER = (
    UserRecordLinkRow,
    RecordShareRow,
    RecordShareRequestRow,
    FileAttachmentRow,
    RecordCommentRow,
    MedicalRecordRow,
    PatientPassportRow,
    PractitionerPassportRow,
    UserRow,
)


def reset_demo_data(session: Session) -> None:
    """Удалить ранее засеянные данные, делая сидинг идемпотентным.

    Args:
        session: Активная SQLAlchemy-сессия.
    """
    for table in _TABLES_IN_DELETE_ORDER:
        session.execute(delete(table))


def seed_demo_data(
    *,
    session: Session,
    password_hasher: PasswordHasherPort,
    password: str = DEFAULT_DEMO_PASSWORD,
) -> dict[str, int]:
    """Наполнить базу связным набором демонстрационных данных.

    Перед вставкой имеющиеся демо-сущности удаляются, поэтому повторный запуск
    приводит базу к одному и тому же состоянию. Метод не коммитит транзакцию —
    управление ею остаётся за вызывающим кодом.

    Args:
        session: Активная SQLAlchemy-сессия.
        password_hasher: Сервис хеширования паролей.
        password: Пароль в открытом виде для всех демо-учёток.

    Returns:
        Словарь с количеством созданных сущностей по группам.
    """
    password_hash = password_hasher.hash_password(plain_password=password)
    now = utc_now()

    reset_demo_data(session)

    # --- Пользователи ---
    admin = UserRow(
        fio='Орлова Светлана Игоревна',
        email='admin@docere.demo',
        phone='+79990000001',
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        password_hash=password_hash,
    )
    doctor_cardio = UserRow(
        fio='Соколов Дмитрий Андреевич',
        email='dr.sokolov@docere.demo',
        phone='+79990000002',
        date_of_birth=date(1980, 4, 12),
        role=UserRole.DOCTOR,
        status=UserStatus.ACTIVE,
        password_hash=password_hash,
    )
    doctor_neuro = UserRow(
        fio='Ким Анна Сергеевна',
        email='dr.kim@docere.demo',
        phone='+79990000003',
        date_of_birth=date(1985, 9, 30),
        role=UserRole.DOCTOR,
        status=UserStatus.ACTIVE,
        password_hash=password_hash,
    )
    patient_ivanov = UserRow(
        fio='Иванов Пётр Васильевич',
        email='ivanov@docere.demo',
        phone='+79991112233',
        date_of_birth=date(1990, 1, 15),
        role=UserRole.PATIENT,
        status=UserStatus.ACTIVE,
        password_hash=password_hash,
    )
    patient_petrova = UserRow(
        fio='Петрова Мария Алексеевна',
        email='petrova@docere.demo',
        phone='+79994445566',
        date_of_birth=date(1978, 6, 3),
        role=UserRole.PATIENT,
        status=UserStatus.ACTIVE,
        password_hash=password_hash,
    )
    patient_blocked = UserRow(
        fio='Кузнецов Олег Николаевич',
        email='kuznetsov@docere.demo',
        phone='+79997778899',
        date_of_birth=date(1965, 11, 22),
        role=UserRole.PATIENT,
        status=UserStatus.BLOCKED,
        password_hash=password_hash,
    )
    users = [admin, doctor_cardio, doctor_neuro, patient_ivanov, patient_petrova, patient_blocked]
    session.add_all(users)
    session.flush()

    # --- Паспорта врачей ---
    passport_sokolov = PractitionerPassportRow(
        created_by_user_id=admin.id,
        user_id=doctor_cardio.id,
        full_name='Соколов Дмитрий Андреевич',
        specialty='Кардиолог',
        organization='ГКБ №1 им. Н.И. Пирогова',
        position='Врач-кардиолог высшей категории',
        email=doctor_cardio.email,
        phone=doctor_cardio.phone,
        status=PractitionerPassportStatus.CONFIRMED,
        confirmed_at=now,
    )
    passport_kim = PractitionerPassportRow(
        created_by_user_id=admin.id,
        user_id=doctor_neuro.id,
        full_name='Ким Анна Сергеевна',
        specialty='Невролог',
        organization='Клиника «Нейромед»',
        position='Врач-невролог',
        email=doctor_neuro.email,
        phone=doctor_neuro.phone,
        status=PractitionerPassportStatus.CONFIRMED,
        confirmed_at=now,
    )
    session.add_all([passport_sokolov, passport_kim])
    session.flush()

    # --- Паспорта пациентов ---
    passport_ivanov = PatientPassportRow(
        created_by_user_id=patient_ivanov.id,
        patient_user_id=patient_ivanov.id,
        fio=patient_ivanov.fio,
        date_of_birth=patient_ivanov.date_of_birth,
        email=patient_ivanov.email,
        phone=patient_ivanov.phone,
        status=PatientPassportStatus.CONFIRMED,
        confirmed_at=now,
    )
    passport_petrova = PatientPassportRow(
        created_by_user_id=patient_petrova.id,
        patient_user_id=patient_petrova.id,
        fio=patient_petrova.fio,
        date_of_birth=patient_petrova.date_of_birth,
        email=patient_petrova.email,
        phone=patient_petrova.phone,
        status=PatientPassportStatus.CONFIRMED,
        confirmed_at=now,
    )
    # Черновик паспорта, заведённый врачом для пациента без учётной записи.
    passport_draft = PatientPassportRow(
        created_by_user_id=doctor_cardio.id,
        patient_user_id=None,
        fio='Сидорова Галина Петровна',
        date_of_birth=date(1955, 2, 8),
        phone='+79990001020',
        status=PatientPassportStatus.DRAFT,
    )
    session.add_all([passport_ivanov, passport_petrova, passport_draft])
    session.flush()

    # --- Медицинские записи ---
    record_cardio = MedicalRecordRow(
        creator_user_id=doctor_cardio.id,
        author_practitioner_passport_id=passport_sokolov.id,
        status=MedicalRecordStatus.CONFIRMED,
        record_type=MedicalRecordType.CONSULTATION_RESULT,
        event_date=date.today() - timedelta(days=14),
        title='Первичный приём кардиолога',
        appointment_location='ГКБ №1, кабинет 312',
        clinical_summary=(
            'Жалобы на одышку при физической нагрузке. АД 140/90 мм рт. ст. '
            'Рекомендован контроль давления и ЭКГ-мониторинг.'
        ),
        payload_json={
            'blood_pressure': '140/90',
            'pulse': 82,
            'recommendations': ['Контроль АД дважды в день', 'Холтер-мониторинг ЭКГ'],
        },
    )
    record_lab = MedicalRecordRow(
        creator_user_id=patient_ivanov.id,
        author_practitioner_passport_id=None,
        status=MedicalRecordStatus.UNCONFIRMED,
        record_type=MedicalRecordType.LAB_RESULT,
        event_date=date.today() - timedelta(days=10),
        title='Общий анализ крови',
        appointment_location='Лаборатория «Гемотест»',
        clinical_summary='Гемоглобин 138 г/л, лейкоциты 6.2, СОЭ 9 мм/ч — в пределах нормы.',
        payload_json={
            'hemoglobin': 138,
            'leukocytes': 6.2,
            'esr': 9,
            'units': {'hemoglobin': 'г/л', 'esr': 'мм/ч'},
        },
    )
    record_neuro = MedicalRecordRow(
        creator_user_id=doctor_neuro.id,
        author_practitioner_passport_id=passport_kim.id,
        status=MedicalRecordStatus.CONFIRMED,
        record_type=MedicalRecordType.EXAM_RESULT,
        event_date=date.today() - timedelta(days=5),
        title='МРТ головного мозга',
        appointment_location='Клиника «Нейромед»',
        clinical_summary='Очаговых и объёмных образований не выявлено. Заключение без патологии.',
        payload_json={'modality': 'МРТ', 'contrast': False, 'conclusion': 'Без патологии'},
    )
    record_draft = MedicalRecordRow(
        creator_user_id=patient_petrova.id,
        author_practitioner_passport_id=None,
        status=MedicalRecordStatus.UNCONFIRMED,
        record_type=MedicalRecordType.OTHER,
        event_date=date.today() - timedelta(days=2),
        title='Черновик: выписка из стационара',
        clinical_summary=None,
        payload_json={'note': 'Ожидает заполнения данных'},
    )
    records = [record_cardio, record_lab, record_neuro, record_draft]
    session.add_all(records)
    session.flush()

    # --- Вложения ---
    session.add_all(
        [
            FileAttachmentRow(
                record_id=record_lab.id,
                uploaded_by_user_id=patient_ivanov.id,
                category=FileAttachmentCategory.LAB,
                storage_key='demo/records/lab/oak-ivanov.pdf',
                mime_type='application/pdf',
                size_bytes=248_512,
            ),
            FileAttachmentRow(
                record_id=record_neuro.id,
                uploaded_by_user_id=doctor_neuro.id,
                category=FileAttachmentCategory.IMAGING,
                storage_key='demo/records/imaging/mrt-petrova.dcm',
                mime_type='application/dicom',
                size_bytes=15_728_640,
            ),
        ]
    )

    # --- Комментарии ---
    session.add_all(
        [
            RecordCommentRow(
                record_id=record_cardio.id,
                author_user_id=patient_ivanov.id,
                body='Спасибо, начал измерять давление утром и вечером.',
            ),
            RecordCommentRow(
                record_id=record_cardio.id,
                author_user_id=doctor_cardio.id,
                body='Хорошо, жду результаты Холтера на повторном приёме.',
            ),
        ]
    )

    # --- Фактические доступы создателей к своим записям ---
    session.add_all(
        [
            UserRecordLinkRow(
                user_id=record_cardio.creator_user_id,
                record_id=record_cardio.id,
                patient_passport_id=passport_ivanov.id,
                source=UserRecordLinkSourceRow.CREATOR,
            ),
            UserRecordLinkRow(
                user_id=record_lab.creator_user_id,
                record_id=record_lab.id,
                patient_passport_id=passport_ivanov.id,
                source=UserRecordLinkSourceRow.CREATOR,
            ),
            UserRecordLinkRow(
                user_id=record_neuro.creator_user_id,
                record_id=record_neuro.id,
                patient_passport_id=passport_petrova.id,
                source=UserRecordLinkSourceRow.CREATOR,
            ),
            UserRecordLinkRow(
                user_id=record_draft.creator_user_id,
                record_id=record_draft.id,
                patient_passport_id=passport_petrova.id,
                source=UserRecordLinkSourceRow.CREATOR,
            ),
        ]
    )

    # --- Sharing-flow: принятый запрос (врач поделился записью с пациентом) ---
    accepted_request = RecordShareRequestRow(
        from_user_id=doctor_cardio.id,
        to_user_id=patient_ivanov.id,
        status=RecordShareStatusRow.ACCEPTED,
        message='Делюсь заключением по результатам приёма.',
        responded_at=now,
    )
    session.add(accepted_request)
    session.flush()

    accepted_share = RecordShareRow(
        request_id=accepted_request.id,
        record_id=record_cardio.id,
        patient_passport_id=passport_ivanov.id,
        status=RecordShareStatusRow.ACCEPTED,
        responded_at=now,
    )
    session.add(accepted_share)
    session.flush()

    # Принятый share порождает фактический доступ получателя к записи.
    session.add(
        UserRecordLinkRow(
            user_id=patient_ivanov.id,
            record_id=record_cardio.id,
            patient_passport_id=passport_ivanov.id,
            source=UserRecordLinkSourceRow.SHARE_ACCEPTED,
            source_record_share_id=accepted_share.id,
        )
    )

    # --- Sharing-flow: ожидающий ответа запрос (пациент делится с неврологом) ---
    pending_request = RecordShareRequestRow(
        from_user_id=patient_ivanov.id,
        to_user_id=doctor_neuro.id,
        status=RecordShareStatusRow.PENDING,
        message='Прошу посмотреть мой анализ крови перед консультацией.',
    )
    session.add(pending_request)
    session.flush()

    session.add(
        RecordShareRow(
            request_id=pending_request.id,
            record_id=record_lab.id,
            patient_passport_id=passport_ivanov.id,
            status=RecordShareStatusRow.PENDING,
        )
    )

    return {
        'users': len(users),
        'practitioner_passports': 2,
        'patient_passports': 3,
        'medical_records': len(records),
        'file_attachments': 2,
        'record_comments': 2,
        'share_requests': 2,
    }
