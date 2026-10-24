# Запуск и разработка Docere

Для первого знакомства и демонстрации используйте [DEMO.md](DEMO.md): отдельный стенд
на `localhost:8012`, новые синтетические данные без сброса существующих.
Этот документ описывает обычное окружение разработки на `localhost:8000` и его обновление.

## Требования

- Docker Engine и Compose с поддержкой `!override`/`!reset` для изолированного демостенда.
- Node.js 22.12+ и npm для frontend-разработки; зависимости ставятся через `npm ci`.
- Python 3.12–3.13 и `uv` для backend вне Docker. Docker и CI используют Python 3.13.
- `make` для команд репозитория. Полные версии зависимостей зафиксированы lock-файлами.

## Обычное локальное окружение без сброса

В новом checkout:

```sh
docker compose build api frontend celery-worker import-dispatcher
docker compose up -d postgres redis minio createbuckets
docker compose wait createbuckets
docker compose run --rm --no-deps api migrate
docker compose up -d api frontend gateway celery-worker import-dispatcher
docker compose ps
```

Приложение: [localhost:8000](http://localhost:8000), OpenAPI: [localhost:8000/docs](http://localhost:8000/docs),
MinIO: [localhost:9001](http://localhost:9001). Настройки Compose предназначены для разработки;
подготовка внешнего окружения описана в [PILOT.md](PILOT.md) и [SECURITY.md](SECURITY.md).

Регистрация создаёт пациента. Первого администратора создайте CLI:

```sh
docker compose exec api python -m app.presentation.cli create-admin --help
```

Заявку врача одобряет администратор либо два подтверждённых врача соответствующей специализации.
Не меняйте роль прямым редактированием БД для демонстрации пользовательского сценария.

## Обновление существующего стенда

Сохраните имя проекта и те же Compose-файлы: от них зависят используемые volumes.
Сначала посмотрите `docker compose ls`. Ниже пример обычного проекта `docere-20`;
для стенда 8012 команды приведены в [DEMO.md](DEMO.md).

```sh
export COMPOSE_PROJECT_NAME=docere-20
docker compose build api frontend celery-worker import-dispatcher
docker compose stop gateway api celery-worker import-dispatcher
docker compose run --rm --no-deps api migrate
docker compose up -d
docker compose exec api alembic check
```

Перед миграциями нужна согласованная копия БД и хранилища. Не вызывайте `seed-demo`,
`make demo-up`, `make demo-reset` или `docker compose down -v` для обновления существующей базы.
Downgrade ряда миграций удаляет соответствующие данные; выполнять его можно только после
проверки конкретной миграции и при остановленных прикладных процессах.

## Разработка с hot reload

```sh
uv sync --all-groups
cd frontend
npm ci
npm run dev
```

Vite открывается на `localhost:5173` и проксирует `/api` на `localhost:8000`.
Для изолированного backend: `DOCERE_DEV_API_URL=http://localhost:8012 npm run dev`.
Если API тоже запускается вне Docker, задайте серверные настройки и выполните
`make dev-backend`. Конфигурация определена в `src/app/infrastructure/config/`.

Кроме API фоновым операциям нужны worker и dispatcher. В Compose они запускаются отдельно;
для dispatcher вне Compose:

```sh
PYTHONPATH=src uv run python -m app.infrastructure.adapters.queue.recover_import_jobs --loop
```

Dispatcher доставляет импорт, AI-запуски и события случаев, восстанавливает просроченные попытки.
Без него наличие доступного API ещё не означает работающую фоновую обработку.
Настройка модели и внешнего API: [AI.md](AI.md).

## Проверки

```sh
make project-check
make frontend-check
```

Первый запускает backend gates: pre-commit, Ruff, mypy, pytest. Второй — TypeScript,
frontend production build, ESLint и Vitest. Для точечной проверки:

```sh
make test ARGS='tests/critical/test_clinical_cases.py -q'
cd frontend
npm test -- src/pages/upload/UploadReviewPage.test.tsx
```

Конкурентные сценарии и цикл миграций требуют отдельной PostgreSQL с правом создавать
временные схемы. Не подставляйте рабочую БД:

```sh
DOCERE_TEST_POSTGRES_URL=postgresql+psycopg://USER:PASSWORD@HOST/TEST_DB \
  make test ARGS='tests/critical/test_clinical_cases.py tests/integration/test_schema_migrations.py -q'
```

E2E создаёт синтетические записи и меняет состояние случаев; используйте отдельный набор.
Команды, артефакты и границы измерений: [VALIDATION.md](VALIDATION.md).

## Старый фиксированный demo-набор

`make demo-up` и `make demo-reset` создают старые фиксированные аккаунты (`DemoPass123`)
и архив `docere-demo-archive.zip`, **очищая прикладные таблицы выбранного проекта**.
Этот режим нужен существующим regression E2E и benchmark, но не является рекомендуемым
первым запуском. [DEMO.md](DEMO.md) описывает добавление новых синтетических наборов.

## Навигация по коду

`src/app/domain` — правила; `application` — сценарии и ports; `infrastructure` — адаптеры;
`presentation` — HTTP/CLI. `frontend/src` — React; `migrations/versions` — Alembic.
API-контракт смотрите в OpenAPI работающей версии, инварианты — в [ARCHITECTURE.md](../ARCHITECTURE.md).
Процесс изменений и коммитов: [CONTRIBUTING.md](../CONTRIBUTING.md).
