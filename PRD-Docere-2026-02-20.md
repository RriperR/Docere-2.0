# PRD: Docere - Информационная система медицинских записей

Версия: 5.1
Дата: 2026-03-06
Статус: Draft for Review
Продукт: Docere (MVP для одной клиники, public cloud)

## 1. Смысл системы и контекст

Docere нужна для контролируемого обмена медицинскими данными внутри одной клиники.

Главная идея модели данных:

1. `MedicalRecord` - это медицинская информация (результат консультации/обследования/анализа), независимая от конкретного аккаунта пациента.
2. Персональные данные пациента хранятся отдельно в `PatientPassport`.
3. Данные врача-автора записи хранятся отдельно в `PractitionerPassport`.
4. Видимость записи конкретному пользователю задается связью `UserRecordLink`.
5. "Карточка пациента" в интерфейсе не хранится как отдельная сущность БД, а динамически собирается из доступных записей и связанных `PatientPassport`.

Это позволяет:

1. Давать доступ к одной и той же записи разным ролям без копирования медицинского содержания.
2. Работать с несколькими паспортами одного пациента у разных сотрудников, не смешивая персональные и медицинские данные.
3. Удерживать инвариант immutable для медицинского содержания записи.
4. Разделять автора записи в системе и врача-автора по смыслу медицинского документа.

## 2. Границы MVP

1. Одна клиника.
2. Публичное облако.
3. Пациенты регистрируются сами.
4. Врачей/админов создает админ.
5. Только in-app уведомления.
6. Без revoke доступа в MVP.
7. Без удаления записей.
8. Без редактирования медицинского содержания записи после создания.

## 3. Роли

1. `patient`
2. `doctor`
3. `admin`

## 4. Доменная модель и ключевые правила

### 4.1 MedicalRecord

`MedicalRecord` хранит медицинские данные, автора записи в системе и ссылку на врача-автора документа.

Обязательные атрибуты:

1. `creator_user_id` - кто создал запись в системе.
2. `author_practitioner_passport_id` - врач-автор документа по смыслу записи.
3. `event_date` - дата медицинского события.
4. `record_type` - тип записи.
5. `appointment_location` - место приема или проведения исследования (nullable).
6. `clinical_summary` - краткое клиническое резюме, видимое пациенту (nullable).
7. `payload_json` - типоспецифичное медицинское содержимое.

Правила:

1. Медицинское содержимое immutable после создания.
2. `creator_user_id`, `author_practitioner_passport_id`, `event_date`, `record_type`, `appointment_location`, `clinical_summary` и `payload_json` неизменяемы после создания.
3. Запись не удаляется.
4. Привязка к пациенту выполняется не полем в `MedicalRecord`, а через `UserRecordLink -> PatientPassport`.
5. Врач-автор может не иметь учетной записи в системе; в этом случае используется `PractitionerPassport` без `user_id`.

### 4.2 PractitionerPassport

`PractitionerPassport` хранит справочную информацию о враче-авторе записи.

Сценарии:

1. Если запись создает внутренний врач, система использует или создает его `PractitionerPassport(status=confirmed, user_id=<id пользователя>)`.
2. Если запись ссылается на внешнего врача, сотрудник или пациент может выбрать существующий `PractitionerPassport` или создать новый.
3. `creator_user_id` и `author_practitioner_passport_id` могут ссылаться на разные сущности.

Правила:

1. `PractitionerPassport` может существовать без `user_id`.
2. Для MVP справочные данные врача редактируемы и не снапшотятся внутрь `MedicalRecord`.
3. Одна запись ссылается только на одного врача через `author_practitioner_passport_id`.

### 4.3 PatientPassport

`PatientPassport` хранит персональные данные пациента.

Сценарии:

1. Паспорт создается врачом при внесении записи.
2. При регистрации пациента создается его собственный `PatientPassport` со `status=confirmed` и `patient_user_id=<id пользователя>`.
3. Паспорт не является объектом шаринга: врач делится только записью, не паспортом.

Правила:

1. Паспорт может существовать без `patient_user_id` (например, создан врачом для локальной работы с записью).
2. В системе может быть несколько паспортов на похожие ФИО.
3. Подтвержденный паспорт (`status=confirmed` и `patient_user_id != null`) считается более приоритетным для отображения.
4. Если пациент принимает запись врача, создается `UserRecordLink` этой записи к подтвержденному паспорту пациента.

### 4.4 RecordComment

`RecordComment` - отдельная append-only сущность для обсуждения записи врачами.

Правила:

1. Комментарии не являются частью immutable-ядра `MedicalRecord`.
2. Создавать комментарии могут только `doctor` и `admin`.
3. Пациент может читать комментарии к доступной записи, но не может их создавать.
4. У одной записи может быть несколько комментариев от разных врачей.

### 4.5 FileAttachment

`FileAttachment` - отдельная сущность для вложений записи.

Правила:

1. Вложения не входят в immutable-ядро `MedicalRecord`.
2. У вложения есть категория: `lab|imaging|document|other`.
3. У вложения фиксируется `uploaded_by_user_id`.

### 4.6 Sharing (технический поток)

1. Отправитель инициирует share записи получателю.
2. Создается `RecordShare(status=pending)`.
3. Получатель выбирает `accepted` или `rejected`.
4. При `accepted` создается `UserRecordLink` для получателя к оригинальному `MedicalRecord` (копия записи не создается).
5. Если получатель - пациент и у него есть подтвержденный `PatientPassport`, создается `UserRecordLink` этой же записи к его подтвержденному паспорту.
6. Для пациента в MVP у записи должен быть актуальный `UserRecordLink` на его подтвержденный `PatientPassport`.
7. Конфликт нескольких `UserRecordLink` на одну запись относится к кейсам сотрудников (например, `врач -> врач`) и решается правилом приоритета отображения.
8. При `rejected` ссылка не создается.

Дополнительно:

1. Пациент может делиться записью, которую не создавал.
2. В MVP revoke отсутствует.

### 4.7 UserRecordLink и фактическая видимость

`UserRecordLink` - источник истины по доступу пользователя к записи и по контексту отображения в карточке.

Назначение:

1. Фиксирует, что пользователь видит конкретный `MedicalRecord`.
2. Хранит `patient_passport_id`, в контексте которого запись показывается пользователю.
3. Позволяет одной записи присутствовать у разных пользователей в разных контекстах паспорта.

### 4.8 Как формируется "карточка пациента" в UI

Алгоритм для текущего пользователя:

1. Берем все `UserRecordLink` пользователя.
2. Для каждой записи определяем релевантный `PatientPassport`.
3. Если для одной и той же `MedicalRecord` доступно несколько паспортов, приоритет:
   - сначала `PatientPassport` со `status=confirmed` и `patient_user_id != null`,
   - затем остальные варианты.
4. Группируем записи в карточки по выбранному паспорту.
5. Внутри карточки сортируем записи по `event_date DESC`, затем `created_at DESC`.

Следствие:

1. Карточка - это read-модель, а не отдельная таблица.
2. Одна и та же запись может отображаться у разных пользователей по разным карточкам (в зависимости от их `UserRecordLink`).

## 5. Функциональные требования

## 5.1 Authentication

### FR-AUTH-1 Регистрация пациента

Acceptance criteria:

1. Регистрация по `fio + email + phone + password`.
2. `email` уникален.
3. `date_of_birth` в `User` опционален.
4. При регистрации автоматически создается `PatientPassport(status=confirmed)` c `patient_user_id = User.id`.

### FR-AUTH-2 Вход

Acceptance criteria:

1. Вход по `email + password`.
2. Есть rate limiting на auth endpoints.

## 5.2 Patient Passport

### FR-PASS-1 Создание паспорта пациента сотрудником

Acceptance criteria:

1. Сотрудник может создать `PatientPassport` c `fio` и опциональными `date_of_birth/email/phone`.
2. Перед созданием показываются вероятные совпадения по паспортным полям.
3. Если совпадений нет или пользователь подтверждает выбор, создается новый паспорт.

### FR-PASS-2 Привязка принятой записи к паспорту пациента

Acceptance criteria:

1. Врач/сотрудник шарит только `MedicalRecord`.
2. При `accepted` записи пациентом система создает/обновляет `UserRecordLink` этой записи на подтвержденный `PatientPassport` пациента.
3. Отдельного сценария \"принять/подтвердить паспорт\" в MVP нет.
4. Для пациента после `accepted` запись отображается в его карточке через подтвержденный `PatientPassport`.
5. Сценарий конкурирующих `UserRecordLink` для одной записи в MVP учитывается для сотрудников (например, `врач -> врач`), а не для пациента.

## 5.3 Medical Records

### FR-REC-1 Создание записи

Acceptance criteria:

1. Запись создают врач или пациент.
2. Обязательные поля: `creator_user_id`, `author_practitioner_passport_id`, `event_date`, `record_type`, `payload_json`.
3. После создания запись не редактируется в медицинской части.
4. При создании записи создается `UserRecordLink` для автора.
5. Для patient/admin без внутреннего врача необходимо указать существующий `PractitionerPassport` или создать новый.

### FR-REC-2 Статусы записи

Acceptance criteria:

1. Статусы: `draft`, `unconfirmed`, `confirmed`, `rejected`.
2. Статус `confirmed` означает верификацию записи по бизнес-процессу, но не снимает ACL-проверки доступа.

### FR-REC-3 Комментарии к записи

Acceptance criteria:

1. Комментарий может создать только `doctor` или `admin`.
2. Комментарий append-only и не редактируется.
3. Пациент видит комментарии в detail view записи, если у него есть доступ к записи.
4. У одной записи может быть несколько комментариев.

## 5.4 Sharing

### FR-SHARE-1 Share одной записи

Acceptance criteria:

1. Отправитель выбирает запись и получателя.
2. Создается `RecordShare(status=pending)`.
3. Получатель принимает (`accepted`) или отклоняет (`rejected`).
4. При `accepted` создается `UserRecordLink` получателя к этой записи.
5. Если получатель - пациент, запись должна быть связана с его подтвержденным `PatientPassport` через `UserRecordLink`.
6. При `rejected` связь не создается.

### FR-SHARE-2 Кейс "врач -> пациент -> другой врач"

Acceptance criteria:

1. Врач A шарит запись пациенту.
2. Пациент принимает запись.
3. Пациент шарит ту же запись врачу B.
4. Врач B принимает запись.
5. У всех в аудите и UI сохраняется оригинальный `creator_user_id`.

### FR-SHARE-3 Без revoke в MVP

Acceptance criteria:

1. В MVP отсутствует операция revoke.
2. Статусы share: только `pending/accepted/rejected`.

## 5.5 Timeline и карточка пациента

### FR-TL-1 История карточки

Acceptance criteria:

1. Экран карточки показывает записи только из `UserRecordLink` текущего пользователя.
2. Для каждой записи выбирается один `PatientPassport` по правилу приоритета (подтвержденный с `patient_user_id` выше).
3. Сортировка записей: `event_date DESC`, вторично `created_at DESC`.
4. Для записи видно минимум: `creator`, `author_practitioner_passport`, `record_type`, `event_date`, `created_at`, `comments_count`, `attachments_count`.

## 5.6 Audit

### FR-AUD-1 Полный аудит

Acceptance criteria:

1. Логируются: create record, share, accept, reject, login, import.
2. Для события есть `actor`, `action`, `entity`, `timestamp`.

## 6. Концептуальная модель данных

### 6.1 Entities

`User`

1. `id: uuid`
2. `fio: string`
3. `email: string (unique)`
4. `phone: string`
5. `date_of_birth: date (nullable)`
6. `password_hash: string`
7. `role: enum(patient|doctor|admin)`
8. `status: enum(active|blocked)`
9. `created_at: timestamp`
10. `updated_at: timestamp`

`PatientPassport`

1. `id: uuid`
2. `created_by_user_id: uuid (fk -> User.id)`
3. `patient_user_id: uuid (nullable, fk -> User.id)`
4. `fio: string`
5. `date_of_birth: date (nullable)`
6. `email: string (nullable)`
7. `phone: string (nullable)`
8. `status: enum(draft|confirmed)`
9. `confirmed_at: timestamp (nullable)`
10. `created_at: timestamp`
11. `updated_at: timestamp`

`PractitionerPassport`

1. `id: uuid`
2. `created_by_user_id: uuid (nullable, fk -> User.id)`
3. `user_id: uuid (nullable, fk -> User.id)`
4. `full_name: string`
5. `specialty: string (nullable)`
6. `organization: string (nullable)`
7. `position: string (nullable)`
8. `email: string (nullable)`
9. `phone: string (nullable)`
10. `status: enum(draft|confirmed)`
11. `confirmed_at: timestamp (nullable)`
12. `created_at: timestamp`
13. `updated_at: timestamp`

`MedicalRecord`

1. `id: uuid`
2. `creator_user_id: uuid (fk -> User.id, indexed)`
3. `author_practitioner_passport_id: uuid (nullable, fk -> PractitionerPassport.id, indexed)`
4. `status: enum(draft|unconfirmed|confirmed|rejected)`
5. `record_type: enum(consultation_result|exam_result|lab_result|other)`
6. `event_date: date (indexed)`
7. `title: string`
8. `appointment_location: string (nullable)`
9. `clinical_summary: text (nullable)`
10. `payload_json: jsonb`
11. `created_at: timestamp`
12. `updated_at: timestamp`

`RecordShare`

1. `id: uuid`
2. `record_id: uuid (fk -> MedicalRecord.id, indexed)`
3. `granted_by_user_id: uuid (fk -> User.id)`
4. `granted_to_user_id: uuid (fk -> User.id)`
5. `status: enum(pending|accepted|rejected)`
6. `created_at: timestamp`
7. `responded_at: timestamp (nullable)`

`UserRecordLink`

1. `id: uuid`
2. `user_id: uuid (fk -> User.id, indexed)`
3. `record_id: uuid (fk -> MedicalRecord.id, indexed)`
4. `patient_passport_id: uuid (nullable, fk -> PatientPassport.id, indexed)`
5. `source: enum(creator|share_accepted|imported|manual_attach)`
6. `source_record_share_id: uuid (nullable, fk -> RecordShare.id)`
7. `created_at: timestamp`

`FileAttachment`

1. `id: uuid`
2. `record_id: uuid (fk -> MedicalRecord.id, indexed)`
3. `uploaded_by_user_id: uuid (fk -> User.id)`
4. `category: enum(lab|imaging|document|other)`
5. `storage_key: string (unique)`
6. `mime_type: string`
7. `size_bytes: bigint`
8. `uploaded_at: timestamp`

`RecordComment`

1. `id: uuid`
2. `record_id: uuid (fk -> MedicalRecord.id, indexed)`
3. `author_user_id: uuid (fk -> User.id, indexed)`
4. `body: text`
5. `created_at: timestamp`

`ImportJob`

1. `id: uuid`
2. `uploaded_by_user_id: uuid (fk -> User.id)`
3. `status: enum(queued|running|completed|failed|completed_with_warnings)`
4. `report_json: jsonb`
5. `created_at: timestamp`
6. `finished_at: timestamp (nullable)`

`AuditEvent`

1. `id: uuid`
2. `actor_user_id: uuid (nullable, fk -> User.id)`
3. `event_type: string`
4. `entity_type: string`
5. `entity_id: uuid`
6. `metadata_json: jsonb`
7. `created_at: timestamp`

### 6.2 Ключевые связи

1. `User 1..N -> PatientPassport (created_by_user_id)`.
2. `User 1..N -> PatientPassport (patient_user_id)`.
3. `User 1..N -> PractitionerPassport (created_by_user_id)`.
4. `User 1..N -> PractitionerPassport (user_id)`.
5. `User 1..N -> MedicalRecord (creator_user_id)`.
6. `PractitionerPassport 1..N -> MedicalRecord`.
7. `MedicalRecord 1..N -> RecordShare`.
8. `User 1..N -> UserRecordLink`.
9. `MedicalRecord 1..N -> UserRecordLink`.
10. `PatientPassport 1..N -> UserRecordLink`.
11. `MedicalRecord 1..N -> FileAttachment`.
12. `MedicalRecord 1..N -> RecordComment`.
13. `User 1..N -> RecordComment`.
14. `User 1..N -> AuditEvent`.

## 7. UX-принципы

1. "Карточка пациента" - это динамический вид доступных пользователю записей.
2. На экране явно показывать, из какого `PatientPassport` собрана карточка.
3. Входящие share-запросы отображаются отдельно и требуют `accept/reject`.
4. При наличии подтвержденного паспорта отображение автоматически приоритизирует его.

## 8. Нефункциональные требования

1. P95 `GET /timeline` <= 700 ms.
2. P95 операций share/accept <= 2 s.
3. Импорт архива до 200 MB <= 2 минут асинхронной обработки.

## 9. Milestones

### Milestone 0 (Foundation)

1. Auth + роли + `PatientPassport` + `PractitionerPassport` + immutable `MedicalRecord`.
2. Базовая модель `UserRecordLink`.

### Milestone 1 (Sharing)

1. `RecordShare` и входящие `accept/reject`.
2. Построение карточки пациента из `UserRecordLink`.
3. Правило приоритета подтвержденного `PatientPassport`.

### Milestone 2 (Import + Audit)

1. Импорт архивов.
2. Полный аудит цепочки доступа.

## 10. Риски

1. Риск: дубли/конфликты паспортов на одного пациента.
2. Митигация: приоритизировать `confirmed + patient_user_id` и явно показывать источник паспорта в UI.

1. Риск: ошибочное принятие чужой записи.
2. Митигация: отдельный экран подтверждения с ключевыми метаданными перед `accept`.

## 11. Технические ограничения и архитектура (обязательно)

### 11.1 Backend stack

1. Язык и фреймворк API: Python + FastAPI.
2. Валидация входных/выходных DTO: `Pydantic`.
3. ORM: SQLAlchemy.
4. СУБД для MVP и production: `PostgreSQL 16`.
5. Миграции: `Alembic`.

### 11.2 Асинхронная обработка импорта архивов

1. Воркеры: `Celery`.
2. Брокер очередей: `Redis`.
3. Импорт архивов выполняется асинхронно через pipeline `API -> Celery task -> worker processing -> ImportJob status/report`.

### 11.3 Развертывание

1. Обязательная контейнеризация в `Docker`.
2. Для локальной разработки и CI используется `docker compose` (минимум: api, postgres, redis, celery-worker).
3. Production развертывание допускается в публичном облаке только в контейнерах.

### 11.4 Архитектурный подход

1. Архитектурный стиль: `DDD + Clean Architecture`.
2. Обязательные слои:
   - `domain` (entities, value objects, domain services, invariants),
   - `application` (use cases),
   - `infrastructure` (db, broker, storage, external adapters),
   - `presentation` (HTTP/API handlers, serializers).
3. Domain слой не зависит от infrastructure/framework кода.
4. Правила доступа и инварианты (`immutable MedicalRecord`, ACL) проверяются в use cases/domain, а не только в контроллерах.
