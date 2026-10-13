# B1 — серверные страницы пациентов и истории

Дата: 13.10.2026. Изменения находятся в общей рабочей копии; commit/push выполняет интегратор.
Frontend и прежний fuzzy `/api/patients/search` в B1 не изменялись.

## Реализованный контракт

- `GET /api/patients/page`: `offset=0`, `limit=20` (1–100), необязательный `q` до 255 символов.
- `GET /api/patients/{patient_id}/records/page`: те же параметры, `record_type`,
  `confirmation_status`, `event_date_from`, `event_date_to`.
- Ответ `{items, total, offset, limit}`. Элементы переиспользуют прежние response schemas.
  `/api/patients` и `/api/patients/{id}/records` по-прежнему возвращают массивы.
- Пациенты сортируются `fio ASC, id ASC`. `q` — буквальная подстрока ФИО без учёта регистра.
- История сортируется `event_date DESC NULLS LAST, created_at DESC, id DESC`.
  `q` ищет только название, `clinical_summary` и filename вложения самой записи.
  Комментарии, их вложения, `payload_json`/PDF-текст и AI-сводки не участвуют.
- `%`, `_` и выбранный escape `/` экранируются; значения передаются bind parameters.
  Обратный слеш остаётся обычным символом, поскольку SQL escape — `/`.
- Типы и статусы проверяются существующими domain enum. Интервал дат включителен.
  Обратный интервал, неизвестные enum/параметры, неверные даты, offset/limit и длинный q →422.
- Несуществующая и недоступная карточка дают один и тот же существующий HTTP 404 mapping.
  Статический `/page` зарегистрирован раньше `/{patient_id}`.

## Слои и ACL

DTO фильтров/страниц и методы порта добавлены в `application/ports/repositories/patient_cards/`.
Существующие `ListPatientsUseCase` и `ListPatientRecordsUseCase` получили `execute_page`.
Use case истории проверяет доступность карточки до вызова страницы repository.
Query/response schemas и mapping находятся в presentation; SQL только в adapter.

ACL использует существующий `active_record_access`, включая сроки и права случая.
Одинаковая доступная и отфильтрованная SQL-выборка применяется до `count`, `offset`, `limit`.
`EXISTS` на access links и вложениях не размножает медицинские записи.
Никаких Python-срезов всей коллекции нет. Новый путь не вызывает старый массивный endpoint.

Статистика карточек считается одним запросом для ID текущей страницы, а не запросом на карточку.
История проецирует summary в SQL с автором, practitioner и count комментариев/вложений,
не выгружая тела комментариев, документы или весь набор accessible record DTO.
На repository-уровне проверено: 3 SQL-запроса для непустой страницы пациентов,
2 для страницы истории, независимо от числа элементов. Проверка доступности пациента
в use case истории добавляет прежнее чтение карточки и её ACL-статистики.

Миграции и индексы не добавлялись. `event_date` остаётся NOT NULL в существующей модели;
`NULLS LAST` явно задан в порядке SQL. Масштаб и EXPLAIN ANALYZE остаются задачей B4.

## Приватность query strings

API descriptions предупреждают, что q может содержать медицинский текст и должен маскироваться
в gateway/APM; клиент должен хранить свободный q только в памяти сессии.
Основной `docker-compose.yml` действительно монтирует `deploy/nginx/docere.conf`.
Его access log теперь содержит `$request_method $uri $server_protocol` вместо `$request`.
Nginx error log направлен в `/dev/null`, поскольку error context может включать query string.
Основной `server_runner.py` использует `access_log=False` для Uvicorn.
Существующий structured middleware пишет `request.url.path`, без q.
Pilot уже отключал access logs и Uvicorn handlers; его конфигурация не изменялась.

Из-за отключения proxy error log подробности upstream ошибок больше не сохраняются nginx.
Статус 502 и duration остаются в access log; диагностику proxy/фоновых ошибок предстоит оформить
в D6. Новая logging-система в B1 не вводилась. Внешний APM и прямой пользовательский запуск
`uvicorn ...` не проверялись: соответствующие access logs должны быть отключены/маскированы
на стороне выбранного запуска.

## Изолированное окружение

Python `.venv`: 3.12.14, SQLAlchemy 2.0.43. PostgreSQL 17.11, aarch64 Alpine, Docker Desktop.
Создан только собственный контейнер `docere-b1-postgres-20261013`,
`127.0.0.1:55433`, БД `b1_history`. DSN передавался через `DOCERE_TEST_POSTGRES_URL`.
Каждый PostgreSQL API тест создаёт и удаляет собственную `case_test_<uuid>` схему.
После тестов проверено отсутствие оставшихся временных схем.
Действующие проекты `docere-roadmap-a1-20261012` и `docere-pilot-d4-20261012` не менялись.
`seed-demo`, `demo-reset`, `down -v` не выполнялись.

Для gateway smoke создан отдельный `docere-b1-nginx-20261013` на `127.0.0.1:55434`.
Реальные HTTP запросы с синтетическим q дали 200 на `/nginx-health` и 502 без upstream
на `/api/patients/page`. Обе строки access log содержат только путь, приватный sentinel отсутствует.
`nginx -t` подтвердил синтаксис. Лог: `/tmp/docere-b1-nginx.log`.
Контейнер nginx после QA удалён. PostgreSQL оставлен для интеграционного gate;
после него можно удалить только `docere-b1-postgres-20261013` и его собственный volume.

## Проверки

Команды запускались из корня проекта, с существующей `.venv`; DSN содержит только тестовые
учётные данные локального изолированного контейнера. Первый запуск PostgreSQL под sandbox
не имел сетевого доступа; повтор с escalation подключился к собственной БД.

```bash
DOCERE_TEST_POSTGRES_URL=<isolated-B1-DSN> PYTHONPATH=src TMPDIR=/tmp \
  .venv/bin/pytest tests/critical/test_patient_pagination.py \
  tests/critical/test_query_log_privacy.py tests/critical/test_architecture_layers.py \
  -q -p no:cacheprovider
UV_NO_SYNC=1 DOCERE_TEST_POSTGRES_URL=<isolated-B1-DSN> make test-critical
.venv/bin/ruff check src tests/critical/test_patient_pagination.py tests/critical/test_query_log_privacy.py
.venv/bin/ruff format --check src tests/critical/test_patient_pagination.py tests/critical/test_query_log_privacy.py
.venv/bin/mypy --config-file mypy.ini src
git diff --check
```

- До двух дополнительных финальных регрессий: `make test-critical` →239 passed,
  119 deselected, 128.93s. Включает реальные PostgreSQL проверки миграций.
- Финальные целевые PostgreSQL/приватность/архитектурные тесты →49 passed, 28.98s
  (40 пагинации, 3 приватности, 6 архитектуры).
- Ruff check passed; format check →299 files already formatted.
- Strict mypy →Success, 297 source files.
- `git diff --check` по путям B1 passed. Общая копия после этого показала CRLF/whitespace
  в ещё редактируемом A2 PatientDashboard; эти чужие изменения не исправлялись агентом B1.
- Логи: `/tmp/docere-b1-targeted.log`, `/tmp/docere-b1-critical.log`,
  `/tmp/docere-b1-ruff.log`, `/tmp/docere-b1-format.log`, `/tmp/docere-b1-mypy.log`.

Тесты покрывают пустую, последнюю и следующую страницу, default shape и старые массивы,
равные ФИО/даты/created_at, приоритет created_at над ID, буквальный поиск и bind,
несколько вложений одной записи, разные права на записи одного пациента,
просроченный sharing, реальное принятие/отзыв sharing, сохранение владельческого доступа,
чужого/несуществующего пациента, фильтры и отрицательные значения, постоянное число запросов.

`make project-check` не запускался по указанию интегратора: mutating pre-commit --all-files
может менять ещё редактируемые файлы A2/E2 в общей рабочей копии. Общую приёмку выполнит интегратор.
Frontend gates относятся к A2/B2; B1 не переводит потребителей на страницы.

## Текст для общих документов (интегратор)

README, описание API пациентов:

> Для больших коллекций доступны `GET /api/patients/page` и
> `GET /api/patients/{id}/records/page` с ответом `{items,total,offset,limit}`.
> По умолчанию offset=0, limit=20 (максимум 100). История поддерживает q, record_type,
> confirmation_status и включительный интервал event_date_from/event_date_to.
> Старые массивные endpoints пока сохраняются; миграция UI выполняется в B2.
> Свободный q хранится только в памяти сессии и должен маскироваться в gateway/APM логах.

ARCHITECTURE, карточки пациента/доступ:

> Новые коллекции пациентов и истории вычисляют count и страницу в repository после ACL
> и фильтров. Поиск — буквальный ILIKE с bind parameters и escape, вложения проверяются
> через EXISTS без дублей. Пациенты сортируются fio/id ASC; история — event_date DESC NULLS LAST,
> created_at/id DESC. Права, включая expired sharing и актуальность прав случая,
> проверяются до total/offset/limit. Summary страницы строятся без выгрузки всей истории.

SECURITY/VALIDATION, если интегратор считает раздел подходящим:

> Свободный медицинский q не записывается structured HTTP middleware, основным nginx access log
> и CLI Uvicorn access log. Nginx error log отключён из-за full request context; подробная
> диагностика proxy errors остаётся D6. При подключении APM и других HTTP runners необходимо
> отдельно маскировать query strings и отключать стандартные request logs с q.
