# Реестр выполнения

Исходная точка: master 76e83e0. Реестр инженерного пакета: 13.10.2026.
Это датированное состояние задач A–F; текущие UX-изменения отражены в
[UX-плане](../UX-IMPROVEMENT-PLAN.md), а не в этой таблице.
Первый параллельный пакет A1/D4/E1 выполнен и прошёл интеграционное ревью.
Если существующий код уже выполняет требование, сначала проверить и записать доказательство.

Состояния:
- ready — можно начать при соблюдении рекомендуемого порядка;
- pending — не завершены перечисленные зависимости;
- in_progress — назначен один владелец;
- done — выполнены критерии и записаны проверки;
- blocked_external — конкретное действие требует внешних данных/решения;
- prepared_external — подготовка закончена, реальная внешняя проверка ещё не выполнена;
- deferred — не входит в текущую реализацию без отдельного решения.

| ID | Задача | Зависимости | Статус |
|---|---|---|---|
| A1 | Сценарий нового пользователя и baseline | — | done |
| A2 | Первый вход и пустой dashboard | A1 | done |
| A3 | Пациент → импорт → запись → случай | A2 | done |
| B1 | Серверная пагинация и поиск | A1 | done |
| B2 | Потребители страниц и навигация | B1 | ready |
| B3 | Provenance и выбор материалов | B2 | pending |
| B4 | Проверка масштаба | B3 | pending |
| B5 | Предупреждение о дубле карточки | B1 | ready |
| C1 | Объяснение своего доступа | B1 | ready |
| C2 | Предпросмотр последствий отзыва | C1 | pending |
| C3 | UI доступа и передача через пациента | C2, A3 | pending |
| C4 | ADR привязки аккаунта, без реализации | A1 | ready |
| D1 | Сессии, refresh rotation, отзыв | — | ready |
| D2 | Восстановление пароля | D1 | pending |
| D3 | Общий rate limiter | D1, D2 | pending |
| D4 | Отдельная конфигурация стенда | — | done |
| D5 | Backup и настоящее restore | D4 | ready |
| D6 | Диагностика фоновых работ | D4 | ready |
| E1 | Синтетические документы и эталоны | — | done |
| E2 | Оценка извлечения | E1 | prepared_external |
| E3 | Пробелы UI/диагностики AI | E2 | pending |
| E4 | Сводка истории вне случая | Решение владельца после E2/F2 | deferred |
| F1 | Сквозная приёмка | A3, B3–B5, C3, D1–D6, E3 | pending |
| F2 | Реальные пользовательские сессии | A3 ранние / F1 итоговые, участники | pending |
| F3 | ВКР и demo | F1, реальные результаты F2 для итогового исследования | pending |

Следующий приоритет: показать продукт врачам и проверить полезность; затем B2/B3 и адресные UI/AI улучшения по наблюдениям. D1/D5/D6 отложены решением владельца. E2 ожидает реальный opt-in прогон и ручную оценку.

## Назначения при параллельной работе

Завершённый пакет (GPT-6.1 Sol, без вложенного делегирования):

- A1 — a1_onboarding, medium: frontend/e2e/onboarding.spec.ts, свои fixtures, docs/reviews/onboarding-baseline.md.
- D4 — d4_pilot, high: compose.pilot.yaml, deploy/pilot/, scripts/pilot*, docs/PILOT.md, собственные config tests. Отдельные Docker project/ports/volumes.
- E1 — e1_fixtures, high: scripts/evaluate_import_ai.py, scripts/import_ai*, tests/fixtures/import_ai/, собственные dataset tests.
- Интегратор: ревью, STATUS.md, общие документы и локальные коммиты. Исполнители не коммитят.
- Запрещены пересекающиеся production edits, общие lockfiles/configs, reset существующего стенда и push.

## Продуктовые и внешние зависимости

- C4: способ подтверждения личности и связывания карточки с аккаунтом требует решения.
  Проектирование ADR можно завершить; саму привязку не реализовывать.
- D2: реальные SMTP-реквизиты не заданы этим планом. Разработка с локальным mail sink доступна.
- D4: VPS/домен/внешний запуск не разрешены этим планом. Локальная конфигурация доступна.
- E2: наличие действующего AI-провайдера проверяется перед opt-in прогоном.
  Нельзя переписывать или публиковать секрет из существующего .env.
- F2: реальные врачи ещё не назначены. Протокол можно подготовить без них.
- E4: новая функция не запускается автоматически.

## Журнал результатов

### A1 — done (baseline, без исправлений A2/A3)

- docs/reviews/onboarding-baseline.md и frontend/e2e/onboarding.spec.ts.
- Реальный Playwright: 1 passed (19.8s), регистрация пяти пользователей, две роли,
  импорт PNG без AI, ручная проверка, просмотр и цепочка врач → пациент → врач.
- TypeScript/lint/build и целевой ESLint прошли у исполнителя.
- Отрицательные API-запросы возвращают действующий контракт 403, не предполагавшийся 404.
- Новый врач уже имеет собственную карточку: A2 должен определять отсутствие добавленных
  пациентов с учётом этой карточки, а не только total == 0.
- Принятая запись доступна из приглашения/карточки, но не видна после полной навигации
  на пациентский dashboard. Исправление остаётся A3, не скрывать этот пробел.

### E1 — done

- 24 синтетических документа: 15 development / 9 holdout; генератор и эталон,
  mixed ZIP с DICOM, прежние пять примеров сохранены.
- По ревью исправлена изоляция split: несовместимый повторный каталог отклоняется
  до записи; чужие файлы не удаляются; holdout manifest без development ZIP.
- Реальные AI-вызовы только с --live-ai; прежняя инструкция обновлена.
- Целевые тесты E1: 69 passed, Ruff и точечный mypy прошли. Реальный AI не вызывался.

### D4 — done в локальном объёме

- compose.pilot.yaml, deploy/pilot/, scripts/pilot.py, scripts/pilot_smoke.py,
  docs/PILOT.md, tests/test_pilot_config.py.
- Изолированный HTTPS localhost:18443; build, config, миграции/head, health и
  реальный auth/import review+skip smoke прошли.
- Переключение двух frontend images: прежние assets возвращают 200 и прежний SHA-256.
- По ревью исправлены opaque AI token validation и повторное включение access logger.
- Конфигурационные тесты: 26 passed. Объединённый финальный прогон D4+E1 интегратором:
  95 passed, Ruff passed, git diff --check passed.
- D1–D3/D5–D6 ещё отсутствуют. Внешний deploy, реальный SMTP/AI, backup restore и
  продолжение редактирования в старой вкладке не проверены. Публичный пилот не готов.

Работа пережила исчерпание лимита: изменения были в общей рабочей копии, агенты
продолжили их после возобновления. Интегратор просмотрел diff и исправления ревью.
Локальные коммиты перечислены в git log; push не выполнялся.

## Текущий пакет A2 / B1 / E2 (13.10.2026)

Три GPT-6.1 Sol high, без вложенных агентов. Только интегратор коммитит и меняет STATUS.md.
- A2 / a2_onboarding: frontend dashboard, role-request UI, собственные тесты и docs/reviews/onboarding-a2.md. Вход: существующие API. Выход: первый вход и состояния заявки; frontend gates, адаптивность. Не менять backend, stores пагинации, lockfiles.
- B1 / b1_pagination: backend patient collections по слоям, собственные PostgreSQL tests и docs/reviews/history-pagination-b1.md. Выход: новые /page endpoints без изменения старых; ACL/count/filter tests. API schemas пациентов принадлежат только этому агенту; миграции и общие конфиги только после согласования с интегратором. Не менять frontend.
- E2 / e2_evaluation: scripts/import_ai evaluation, собственные tests, docs/reviews/import-ai-evaluation-e2.md. Выход: machine-readable metrics и ручная таблица источников, offline controlled adapter. Реальные платные вызовы не запускать в этом пакете; явно записать непроверенную часть. Не менять production AI, fixtures holdout, общие зависимости.
- Общие README/ARCHITECTURE: исполнители передают необходимые правки интегратору. Изолированные БД/compose project; не сбрасывать существующие данные и не использовать seed-demo. Push запрещён.

## Результат пакета A2 / B1 / E2

- A2: первый вход, статусы заявки и CTA врача реализованы; 20 unit, 1 настоящий E2E,
  type-check/lint/build прошли. 390/768/1440 и клавиатура проверены, native 200% zoom
  не подтверждён (проверен эквивалентный reflow). Отчёт docs/reviews/onboarding-a2.md.
- B1: SQL страницы и фильтры с ACL до count/offset/limit; старые endpoints сохранены.
  49 targeted PostgreSQL/privacy/architecture passed; critical gate 239 passed;
  strict mypy 297 source files и Ruff clean. Отчёт docs/reviews/history-pagination-b1.md.
  Query исключены из gateway/Uvicorn logs; proxy error diagnostics ограничены до D6.
- E2: offline evaluator, машинные метрики и ручная таблица подготовлены.
  91 unit, 36 import/dataset, 7 case security tests passed; scoped strict mypy clean.
  Реальных AI-вызовов и экспертных оценок не было: controlled результаты не измеряют
  качество модели. Полный E2 — prepared_external, команды в docs/reviews/import-ai-evaluation-e2.md.
- Интегратор просмотрел diff, отправил авторам замечания по типизации и защите текста
  при закрытии формы; исправления и регрессии проверены. Общий git diff --check clean.
  Full project-check не запускался: выполнены релевантные backend/frontend gates;
  mutating pre-commit --all-files не запускался поверх параллельных изменений.
- Три исполнителя Sol high, без вложенного делегирования. Ожидание через wait_agent;
  production работа интегратором не дублировалась. Push не выполнялся.

## Продуктовый пакет: сценарий, внешний вид, демонстрация

Приоритет владельца: проверить полезность и привлекательность продукта до дальнейшей
эксплуатационной подготовки. D1/D5/D6 в текущий пакет не входят.
Три Sol high, без вложенных агентов; интегратор владеет STATUS, общими docs и commits.

- product_journey: A3, frontend patient detail/list, PatientDashboard, upload/review/status,
  case wizard и их тесты; минимальная backend поддержка только при необходимости ACL контекста.
  Не менять DoctorDashboard/RecentCases/global styles, lockfiles или общие docs.
- product_dashboard: DoctorDashboard/RecentCases и отдельные dashboard компоненты/tests.
  Улучшить визуальную иерархию и понятность действий, сохранить реальные данные/состояния.
  Не менять PatientDashboard, shared case cards, глобальный layout/styles, API/backend.
- product_demo: docs/DEMO.md, docs/PRODUCT-VALIDATION.md, собственные scripts/product_demo*
  и frontend/e2e/product-demo*; синтетический воспроизводимый сценарий без reset/seed.
  Владеет запуском одного изолированного demo стенда для браузерных проверок всех агентов.
  Никаких секретов или реальных AI-вызовов. Не менять production UI/backend.

Выход: законченный путь пациента к разбору, визуально проверенный рабочий стол,
демонстрация 5–7 минут и протокол проверки спроса. Каждый агент сохраняет профильный отчёт.
Только локальные commits в master, без push. Пока исполнители работают, интегратор ждёт.

### Результат продуктового пакета

- A3 выполнен: серверная проверка контекста пациента, явный выбор при импорте,
  ссылки на созданные записи/мастер и принятые материалы пациентского dashboard.
  41 targeted tests, настоящий E2E 1 passed (28.5s), typecheck/lint/build passed.
  Network/reload и чужой пациент/записи проверены, backend не менялся.
- Рабочий стол: одна очередь первых пяти задач, продолжение разбора и начальные
  действия вместо дублирующих очередей/KPI. Review устранил сохранение старого контекста
  при refresh/logout/account switch. 31 targeted tests; screenshots 390/768/1440
  заполненного и пустого dashboard, keyboard проверены. Полные frontend gates passed.
- Demo: воспроизводимые API setup/check без очистки данных; два врача, документы,
  импорт, активный и завершённый случаи. 1 real E2E passed (8.3s), readiness passed.
  AI выключен, подготовленные тексты обозначены как ручные. Cold build/start нового
  wrapper не проверен. F2 протокол готов, реальные интервью не проводились.
- Отчёты: docs/reviews/product-{journey-a3,dashboard,demo}.md.
  Интегратор просмотрел code diff и визуальный screenshot, git diff --check clean.
  Локальные commits в master; push не выполнялся. Приёмка спроса впереди.
