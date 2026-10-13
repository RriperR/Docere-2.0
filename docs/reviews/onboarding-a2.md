# A2: первый вход и следующий шаг

Дата: 13 октября 2026. Область: A2 из `docs/roadmap/01-onboarding.md`.
Работа без commit/push; backend, lockfiles и общая документация относятся интегратору.

## Реализовано

- PatientDashboard сохраняет свою историю и отдельно показывает действие «Я врач».
  Собственная карточка определяется `access_context=own_confirmed`, а не старой открытой
  карточкой в store, именем или совпадением email.
- Статус заявки загружается независимо от поиска проверяющих. Показаны no application,
  pending, rejected и approved; ошибки не выдаются за отсутствие заявки.
- Pending: объяснение ожидания администратора/двух врачей, просмотр заявки и обновление
  статуса. Пока действующая заявка неизвестна или pending, форма не предлагается.
- Rejected: доступны только серверные `reviews[].note` и fallback отсутствия причины.
  Новая подача разрешена действующим backend: создание запрещается только при pending
  и для роли, отличной от patient. Кворум и server authorization сохранены.
- Approved: новая форма скрыта, роль обновляется существующим `refreshUser`.
- Новый врач без других доступных карточек получает главное «Добавить пациента» и второе
  «Импорт документов». Автоматически созданная собственная карточка не считается
  добавленным пациентом и остаётся видна в списке. Другие карточки сохраняют обычный dashboard.
- Штатные RecentCases, Attention/InboxTasks, рабочая очередь и последние карточки сохранены.
  `/inbox/tasks` разрешён только врачам: на пациентском dashboard этот API не вызывается;
  штатные входящие пациента остаются в DashboardLayout и `/share-requests`.
- История и заявки различают loading/error/empty, ошибки повторяются кнопкой.
- `/patients?create=1` открывает форму только doctor/admin и удаляет управляющий query-параметр.
  Поля получили id/label, dialog semantics, начальный focus, Tab/Shift+Tab trap, Enter submit,
  ограничение высоты и прокрутку; responsive фильтры и пустой RecentCases скорректированы.

## Стенд

На старте `/tmp/docere-roadmap-a1.sh` отсутствовал, localhost:8012 возвращал connection refused,
`docker compose ls --format json` вернул `[]`. Создан отдельный project
`docere-roadmap-a2-20261013` с новыми postgres_data/minio_data volumes, без `.env`, seed/reset/down-v.
AI явно выключен. Использованы cached baseline images `docere-ai-api:local` и
`docere-ai-frontend:local`, backend image имеет миграции до `20261011_25`.
Применены migrate и штатный create-admin с синтетическим `admin@docere.demo`.

- API/gateway: `http://localhost:8012`.
- Текущий frontend: `http://127.0.0.1:4174` (Vite, session 35037).
- Безопасный wrapper: `/tmp/docere-roadmap-a2.sh`; override: `/tmp/docere-roadmap-a2.override.yml`.
- Vite proxy: `DOCERE_DEV_API_URL=http://localhost:8012 npm run dev -- --host 127.0.0.1 --port 4174 --strictPort`.
  Новый env не встраивается в production; default API localhost:8000 сохранён.
- Данные E2E создаются UI-регистрацией с уникальным UUID email `@example.com`; нет fixed UUID.

## Проверки и продолжение

- `npm run test -- src/pages/dashboard/Onboarding.test.tsx`: **20 passed**.
- `npm run type-check`: passed.
- `npm run lint`: passed.
- `npm run build`: passed.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4174 npx playwright test e2e/onboarding-a2.spec.ts --retries=0 --reporter=list`:
  последний завершённый прогон **1 passed (11.1s)**: регистрация → rejected note → повторная подача → pending
  без формы → approved/role refresh → собственная карточка → создание нового пациента клавиатурой →
  обычный наполненный dashboard. Проверены 390/768/1440 px без горизонтального overflow,
  клавиатура и аппроксимация 200% reflow. Финальный повтор для стабильных screenshots прошёл; изображения 390/768/1440 и
  reflow 200% просмотрены.
- Unit покрывает отсутствие/pending/rejected/approved, loading/error/retry, отсутствие note,
  подачу при ошибке/quorum, загрузку истории, старую shared card, literal zero/own card,
  обычный dashboard и штатное входящее приглашение, keyboard modal, запрет создания patient и
  сохранение dirty формы при отмене закрытия (Escape/крестик/backdrop/Отмена).

Общий close-handler modal использует подтверждение потери при dirty форме; во время submission
закрытие запрещено. Успешное сохранение закрывает форму без подтверждения. Замечание scoped review
по Escape выполнено и покрыто unit-тестом.

Аппроксимация 200% reflow — 720 CSS px и deviceScaleFactor=2 для физического 1440 px — не является
проверкой настоящего browser zoom. Настоящий native browser zoom пока не подтверждён.
Снимки только синтетического doctor dashboard: `artifacts/onboarding-a2/` (gitignored).
Первый визуальный просмотр выявил сжатие empty RecentCases на 390px: исправлен responsive flex.
Временный неуспех повторного E2E был гонкой теста после auto role refresh: ожидаемая кнопка pending
исчезала при уже открывшемся doctor dashboard. Теперь проверка pending refresh выполняется до
approval, затем выполняется reload и проверяется разрешённый переход к доктору.
PatientDashboard был единственным изменённым файлом с CRLF. Он нормализован к LF; `.gitattributes`
задаёт только binary PDF и не задаёт endings. `git diff --check -- frontend` проходит без overrides.
Для содержательного review этого файла можно смотреть `git diff --ignore-space-at-eol`.

## Файлы A2

- `frontend/src/pages/dashboard/DoctorDashboard.tsx`, `PatientDashboard.tsx`, `RecentCases.tsx`.
- `frontend/src/pages/roles/DoctorRequestPage.tsx`, новые `DoctorRoleStatus.tsx` и `useMyDoctorApplications.ts`.
- `frontend/src/pages/patients/PatientListPage.tsx`.
- `frontend/src/pages/dashboard/Onboarding.test.tsx`, `frontend/e2e/onboarding-a2.spec.ts`.
- `frontend/vite.config.ts`, данный отчет.

Реализация и доступные automated gates завершены; остается scoped review интегратором.

## Предлагаемые изменения общих docs для интегратора

README: кратко описать «Я врач» на пациентском dashboard, pending/rejected и следующий шаг нового
подтверждённого врача; `DOCERE_DEV_API_URL` для подключения frontend к отдельному локальному API.
ARCHITECTURE: onboarding выводится из существующих заявок и `access_context`; own_confirmed
не считается пациентом, добавленным врачом; новых onboarding таблиц и новых прав нет.
STATUS: A2 оставить in_progress до scoped review и финальной responsive проверки.
A3 (контекст импорта/записи/мастер случая и принятые записи patient dashboard) не реализован.
