# PRD: Docere - Информационная система медицинских записей

Версия: 5.0
Дата: 2026-02-20
Статус: Draft for Review
Продукт: Docere (MVP для одной клиники, public cloud)

## 1. Обзор продукта

Docere - это система обмена медицинскими записями.
Базовая единица данных: `MedicalRecord` (как пост в соцсети).

Ключевая модель:

1. Понятия постоянной "карточки" нет.
2. У записи есть обязательные поля: `creator` (кто внес) и `patient` (о ком запись).
3. Любой пользователь видит историю пациента как динамически собранную ленту доступных записей.
4. Лента сортируется по `event_date` (дата события), а не по дате создания записи.

## 2. Границы MVP

1. Одна клиника.
2. Публичное облако.
3. Пациенты регистрируются сами.
4. Врачей/лаборантов/админов создает админ.
5. Только in-app уведомления.
6. Без revoke доступа в MVP.
7. Без удаления записей.
8. Без редактирования записей после создания.

## 3. Роли

1. `patient`
2. `doctor`
3. `lab_technician`
4. `admin`

## 4. Доменная модель и правила

### 4.1 MedicalRecord

Обязательные атрибуты записи:

1. `creator_user_id` - кто внес запись (врач, лаборант или пациент).
2. `patient_id` - пациент, к которому относится запись.

Дополнительно:

1. `event_date` - дата медицинского события.
2. `created_at` - дата создания записи в системе.
3. `record_type`, `title`, `payload_json`, `attachments`.

Правила:

1. `creator_user_id` неизменяем.
2. `patient_id` неизменяем.
3. Запись immutable после создания.
4. Запись не удаляется.

### 4.2 Пациент как субъект записи

1. Используется сущность `Patient` (субъект медицинской информации).
2. `Patient` может быть связан с аккаунтом (`linked_user_id`) или существовать без него.
3. Все записи объединяются по `patient_id`.

### 4.3 Sharing

1. Любой записью можно поделиться.
2. Share проходит через статусы `pending -> accepted/rejected`.
3. Принятие share не копирует запись, а дает доступ к оригиналу.
4. Пациент может делиться записью, которую сам не создавал.

### 4.4 История пациента у конечного пользователя

История строится запросом:

1. выбрать записи с нужным `patient_id`;
2. оставить только записи, доступные текущему пользователю;
3. сортировать по `event_date DESC`, затем `created_at DESC`.

Следствие:

1. У разных пользователей история одного пациента может отличаться по составу записей (из-за прав доступа).
2. Если запись принята через share, она появляется в истории получателя по этому пациенту.
3. Если получатель раньше не работал с этим пациентом, при первом `accepted` создается рабочая связь пользователя с пациентом (для отображения в списке пациентов).

## 5. Функциональные требования

## 5.1 Authentication

### FR-AUTH-1 Регистрация пациента

Acceptance criteria:

1. Регистрация по `fio + email + phone + password`.
2. `email` уникален.
3. `date_of_birth` в `User` опционален.

### FR-AUTH-2 Вход

Acceptance criteria:

1. Вход по `email + password`.
2. Есть rate limiting на auth endpoints.

## 5.2 Patient Entity

### FR-PAT-1 Создание пациента сотрудником

Acceptance criteria:

1. Перед созданием показываются вероятные совпадения по `fio + date_of_birth + email + phone`.
2. Если совпадений нет, создается новый `Patient`.

### FR-PAT-2 Привязка пациента к аккаунту

Acceptance criteria:

1. Пациент может запросить привязку существующего `Patient` к своему `User`.
2. Подтверждение выполняется админом.
3. После подтверждения заполняется `Patient.linked_user_id`.

## 5.3 Medical Records

### FR-REC-1 Создание записи

Acceptance criteria:

1. Запись создают врач, лаборант или пациент.
2. Обязательные поля: `creator_user_id`, `patient_id`, `event_date`.
3. После создания запись не редактируется.

### FR-REC-2 Статусы записи

Acceptance criteria:

1. Статусы: `draft`, `unconfirmed`, `confirmed`, `rejected`.
2. Переход в `confirmed` блокирует любые изменения.

## 5.4 Sharing

### FR-SHARE-1 Share одной записи

Acceptance criteria:

1. Отправитель выбирает запись и получателя.
2. Создается `RecordShare(status=pending)`.
3. Получатель принимает (`accepted`) или отклоняет (`rejected`).
4. При `accepted` запись появляется в истории получателя по соответствующему пациенту.
5. При `rejected` запись не появляется у получателя.
6. Если у получателя нет связи с этим `patient_id`, она создается автоматически при `accepted`.

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
2. Статусы доступа: только `pending/accepted/rejected`.

## 5.5 Timeline View

### FR-TL-1 История пациента

Acceptance criteria:

1. Экран "История пациента" отображает доступные записи по выбранному `patient_id`.
2. Сортировка: `event_date DESC`, вторично `created_at DESC`.
3. Для каждой записи видно минимум: `creator`, `record_type`, `event_date`, `created_at`.
4. Пациент появляется в списке "Мои пациенты" у пользователя, если есть хотя бы одна запись, которую пользователь создал по этому `patient_id` или принял по share.

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
7. `role: enum(patient|doctor|lab_technician|admin)`
8. `status: enum(active|blocked)`
9. `created_at: timestamp`
10. `updated_at: timestamp`

`Patient`

1. `id: uuid`
2. `linked_user_id: uuid (nullable, fk -> User.id, unique)`
3. `fio: string`
4. `date_of_birth: date (nullable, indexed)`
5. `email: string (nullable)`
6. `phone: string (nullable)`
7. `created_by_user_id: uuid (nullable, fk -> User.id)`
8. `created_at: timestamp`
9. `updated_at: timestamp`

`MedicalRecord`

1. `id: uuid`
2. `patient_id: uuid (fk -> Patient.id, indexed)`
3. `creator_user_id: uuid (fk -> User.id)`
4. `status: enum(draft|unconfirmed|confirmed|rejected)`
5. `record_type: enum(consultation_result|exam_result|lab_result|other)`
6. `event_date: date`
7. `title: string`
8. `payload_json: jsonb`
9. `created_at: timestamp`
10. `updated_at: timestamp`

`RecordShare`

1. `id: uuid`
2. `record_id: uuid (fk -> MedicalRecord.id, indexed)`
3. `granted_by_user_id: uuid (fk -> User.id)`
4. `granted_to_user_id: uuid (fk -> User.id)`
5. `status: enum(pending|accepted|rejected)`
6. `created_at: timestamp`
7. `responded_at: timestamp (nullable)`

`UserPatientAccess`

1. `id: uuid`
2. `user_id: uuid (fk -> User.id, indexed)`
3. `patient_id: uuid (fk -> Patient.id, indexed)`
4. `source: enum(self_created|share_accepted|imported)`
5. `source_record_share_id: uuid (nullable, fk -> RecordShare.id)`
6. `created_at: timestamp`

`FileAttachment`

1. `id: uuid`
2. `record_id: uuid (fk -> MedicalRecord.id, indexed)`
3. `storage_key: string (unique)`
4. `mime_type: string`
5. `size_bytes: bigint`
6. `uploaded_at: timestamp`

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

1. `Patient 1..N -> MedicalRecord`.
2. `MedicalRecord 1..N -> RecordShare`.
3. `User 1..N -> UserPatientAccess`.
4. `Patient 1..N -> UserPatientAccess`.
5. `MedicalRecord 1..N -> FileAttachment`.
6. `User 1..N -> AuditEvent`.

## 7. UX-принципы

1. Нет раздела "карточка" как отдельной сущности хранения.
2. Основной экран - "История пациента" (динамическая лента записей).
3. Входящие share-запросы отображаются отдельно и требуют `accept/reject`.
4. При первом `accept` записи нового пациента этот пациент автоматически появляется в "Мои пациенты".

## 8. Нефункциональные требования

1. P95 `GET /patients/{id}/timeline` <= 700 ms.
2. P95 операций share/accept <= 2 s.
3. Импорт архива до 200 MB <= 2 минут асинхронной обработки.

## 9. Milestones

### Milestone 0 (Foundation)

1. Auth + роли + `Patient` + immutable `MedicalRecord`.

### Milestone 1 (Sharing)

1. `RecordShare` и входящие `accept/reject`.
2. История пациента, собранная из доступных записей.

### Milestone 2 (Import + Audit)

1. Импорт архивов.
2. Полный аудит цепочки доступа.

## 10. Риски

1. Дубли по содержанию.
2. Митигация: показывать автора, дату события и тип; не объединять автоматически.

1. Ошибочное принятие чужой записи.
2. Митигация: отдельный экран подтверждения с ключевыми метаданными.

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
