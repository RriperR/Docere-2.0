# Docere

Сервис с backend на FastAPI и frontend на React.
В backend используется единый Quality Gate: `ruff`, `mypy`, `pytest`, `pre-commit`, `pre-push`, `Makefile`, `uv`.

## Структура репозитория

```text
.
├─ src/app/            # Backend (DDD + Clean Architecture)
├─ tests/              # Backend tests
├─ frontend/           # Frontend (Vite + React + TypeScript)
└─ конфиги качества    # pyproject.toml, Makefile, pre-commit, mypy, ruff
```

### Backend-слои

```text
src/app/
  domain/
  application/
  infrastructure/
  presentation/
```

Направление зависимостей:

- `domain` ни от кого не зависит
- `application` зависит только от `domain`
- `infrastructure` зависит от `application` и `domain`
- `presentation` зависит от `application`; инфраструктура подключается через композицию/DI

## Требования

- Python `3.12+`
- `uv`
- Node.js `18+` и `npm` (для frontend)

## Быстрый старт (backend)

```bash
uv sync --all-groups
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
make dev
```

## Конфигурация backend

Сервис использует централизованные `Pydantic Settings` с префиксом `APP_`.
Критичные переменные обязательны, без них приложение не стартует.

По умолчанию backend читает `.env` из корня репозитория.
Пример конфигурации: `.env.example`.

Обязательные переменные:

- `APP_DATABASE__URL`
- `APP_AUTH__SECRET_KEY`
- `APP_STORAGE__ENDPOINT`
- `APP_STORAGE__BUCKET`
- `APP_QUEUE__BROKER_URL`

## Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

## Запуск backend в Docker

```bash
docker compose up -d --build
docker compose ps
```

Сервисы в compose:

- `gateway` (`nginx`, точка входа с хоста на `localhost:8000`)
- `api` (FastAPI)
- `postgres` (`PostgreSQL 16`)
- `redis` (broker для Celery)
- `celery-worker`

Для локальной проверки проксирования и масштабирования backend можно поднять gateway и несколько backend-реплик:

```bash
docker compose up -d --build --scale api=2 gateway
docker compose ps
```

При таком запуске внешний трафик идёт через `nginx`, а `api` остаётся доступен только внутри docker-сети.

## Основные команды проверки

```bash
make lint
make format-check
make type-check
make test
make project-check
```

## Миграции БД (Alembic)

```bash
make migrate-up
make migrate-down
```

Для миграций должна быть задана переменная `APP_DATABASE__URL`.

Создание новой ревизии:

```bash
uv run alembic revision --autogenerate -m "describe_change"
```

Перед коммитом ревизию нужно проверить и при необходимости отредактировать вручную.

Обычный workflow:

- миграции запускаются отдельным шагом деплоя, а не на старте API
- сначала `expand`: новые таблицы, nullable-колонки, совместимые ограничения и индексы
- затем выкатывается код, который совместим со старой и новой схемой
- backfill больших объемов данных выполняется отдельной задачей, не внутри startup приложения
- после переключения трафика выполняется `contract`: удаление старых колонок, таблиц и legacy-ограничений

Для Docker Compose миграции лучше запускать явно:

```bash
docker compose run --rm api migrate
docker compose up -d api celery-worker
```

Для одноразового контейнера из того же образа можно запускать management-команды напрямую:

```bash
docker run --rm --env-file .env docere-api:latest migrate
docker run --rm --env-file .env docere-api:latest create-admin \
  --email admin@example.com \
  --password VeryStrongPass123 \
  --fio "Главный администратор" \
  --phone +79990000001
```

Это удобно для CI/CD и административных задач: не нужно заходить внутрь работающего контейнера и менять состояние вручную.

## CI/CD и деплой

В репозитории есть пример `.gitlab-ci.yml` для цикла:

- `project-check`
- сборка и публикация нового образа
- одноразовый контейнер `migrate` перед деплоем
- деплой новой версии на `staging`
- smoke-проверка `/api/health`
- ручной rollback через смену тега образа

Ключевая идея: миграции выполняются отдельным одноразовым контейнером из того же образа, который затем деплоится в `staging`.

## Установка групп зависимостей backend

```bash
uv sync                  # базовые зависимости
uv sync --group dev      # dev-инструменты
uv sync --group lint     # линт/типизация
uv sync --group test     # тесты
uv sync --all-groups     # все группы
```

## Для участников разработки

Правила ветвления, коммитов, Merge Request и обязательных проверок: `CONTRIBUTING.md`.
