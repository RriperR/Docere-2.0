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

## Запуск frontend

```bash
cd frontend
npm install
npm run dev
```

## Основные команды проверки

```bash
make lint
make format-check
make type-check
make test
make project-check
```

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
