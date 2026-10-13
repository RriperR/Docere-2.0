# A3: пациент → импорт → запись → клинический случай

Дата: 13 октября 2026. Область: A3 из docs/roadmap/01-onboarding.md.
Работа в общем продуктовом пакете; без commit/push, backend, lockfiles, инфраструктуры,
общих README/ARCHITECTURE/STATUS. Backend остаётся источником прав доступа.

## Реализовано

- В карточке доступны ручное добавление записи и импорт с ID пациента в URL. Для пациента
  ручное создание показано только в собственной подтверждённой карточке; принятая shared
  карточка не даёт права создавать записи. Врач/admin сохраняет существующее право создания.
- Upload, status и review сохраняют patient ID. Hook обращается к существующему
  GET /patients/{id}; имя и дата рождения отображаются только после проверки сервером.
  Недоступная карточка показывает ошибку, повтор и явное продолжение без контекста.
  Загрузить с непроверенным контекстом нельзя. Старый выбранный файл очищается после upload.
- Review сохраняет исходные извлечённые данные и восстановленные решения. Контекст применяется
  только кнопкой для конкретного кандидата, с пояснением сверить документ, имя и дату рождения.
  Нет автоматического назначения всех документов, совпадения email, создания identity link,
  замены даты рождения датой события или обхода regroup/duplicate/AI identity confirmation.
- Resolve показывает результаты отдельно по пациентам. Все созданные записи имеют прямые
  ссылки с отдельной нумерацией внутри карточки. Реальные ФИО карточек читает серверный
  API, при недоступности имени используется нейтральная нумерация карточек.
- Галочки записей в истории дают «Обсудить записи (N)»; результат импорта тоже предлагает
  существующий мастер. URL содержит только ID. Мастер проверяет каждую запись через сервер,
  сверяет patient_passport_id, исключает чужие/недоступные ID. В материалах можно явно снять
  выбор. Смена пациента очищает выбор. Больше 100 записей из ссылки не выбираются.
- PatientDashboard сохраняет собственную историю отдельно от «Принятых материалов».
  Shared карточки и записи берутся только из существующих авторизованных коллекций; карточки
  не объединяются с собственным человеком. Каждая запись ведёт к её карточке/событию.
  Подсказка ведёт через штатный выбор записей и sharing зарегистрированному врачу.
  Pending приглашение не добавляет документ в кабинет и не выдаёт доступ к файлу.
- Ошибка подтверждения из-за сети объясняется по-русски. Решения остаются в форме и в
  существующем серверном черновике. Повтор и reload не сбрасывают ручные поля.
- Пояснения «карточка — человек; запись — событие/документ; случай — обсуждение выбранных
  записей» встроены в действия и пустые состояния.

## Проверки

- Целевые Vitest: 7 files / 41 passed, включая ImportAiWorkflow, UploadReviewPage,
  PatientImportContext, NewCasePage, ImportResultSummary, Onboarding и ProductDashboard.
  Финальный повтор — 41 passed (4.90s), 12:32 MSK.
  Покрыты explicit context choice, несовпадение извлечённых имени/даты, отсутствие автоматической
  подстановки, сохранение ручных полей после ошибки, rejected context/retry, wrong-patient record,
  denied patient, отдельная собственная история/accepted материалы, multi-patient result links.
- Общий frontend: npm run type-check && npm run lint && npm run build — clean,
  включая окончательные изменения product_dashboard (10 unit tests); финальный повтор
  после guard заголовка кабинета и удаления stale названий ссылок — **clean**, 12:32 MSK.
- git diff --check — clean для своего frontend scope. Backend не менялся, backend gates
  по A3 не запускались.
- Реальный Playwright A3: **1 passed (28.5s)**, сценарий 27.7s, 12:31 MSK.
  Пройден полностью: новый врач/card/import без AI/network+reload/record/wizard/draft,
  accepted patient dashboard/PNG/transfer, foreign context и server resolve negatives.

Команда (существующий isolated stand, без compose/seed/reset):

```sh
ONBOARDING_ADMIN_EMAIL=product-admin@docere.demo \
ONBOARDING_ADMIN_PASSWORD=ProductDemo123 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:4174 \
npx playwright test e2e/onboarding-a3.spec.ts --retries=0 --reporter=list \
  --output=artifacts/onboarding-a3-results
```

Стенд: API/gateway localhost:8012, Vite 127.0.0.1:4174; подготовлен product_demo.
Тест создаёт 4 новых аккаунта с UUID email @example.com, получает роль врача штатной заявкой
и admin review; загружает синтетический PNG с ai_requested=false; создаёт карточку через UI.

## Что проверяет E2E

1. Новый врач → создание карточки → переход к импорту из неё → manual review с explicit patient.
2. Doctor с доступным job пытается resolve в чужую карточку: 422; job остаётся needs_review.
3. Обрыв сети на resolve: сообщение, сохранённые поля, reload и восстановление серверного draft,
   успешный повтор → запись → выбор/снятие галочки в мастере → созданный черновик случая.
4. Врач → пациент: до принятия запись 403 и отсутствует в dashboard; после принятия видна в
   «Принятых материалах», карточке и PNG viewer.
5. Пациент → второй врач: до принятия 403, после завершённого server accept — 200.
6. Посторонний всегда получает record 403; чужая карточка — 404. Upload с чужим patient ID
   показывает ошибку и не подставляет имя. Patient role resolve с валидным DTO — 403.

Промежуточные падения исправили тестовые селекторы таблицы/основного содержимого,
ожидание завершения POST accept (link на карточку существует и при pending), контракт
patient 404 и валидность negative DTO. Они не потребовали изменения ACL или sharing.

## Ограничения и интеграция

- C4: account binding не решён и не реализован. Email врача в созданной карточке не связывает
  её с пациентским аккаунтом. Shared материалы остаются отдельными карточками.
- B2/B3: PatientDashboard читает существующие полные коллекции; серверная пагинация/масштаб
  остаются отдельными задачами. A3 не меняет эти API или access provenance.
- Реальный AI/внешний provider не вызывался; ручной сценарий проверен с AI выключенным.
- A3 не проводил новый полный adaptive/200% zoom аудит. DoctorDashboard screenshots принадлежат
  product_dashboard; текущие изменения не заявляют native zoom acceptance.
- Интегратору: README описать путь из карточки к импорту и мастеру, отдельные принятые материалы;
  ARCHITECTURE — URL hint проходит server ACL и explicit review, records selection сверяет patient ID;
  STATUS — A3 после scoped review и финального E2E.

Файлы: PatientDetailsPage, PatientDashboard, UploadPage/UploadStatusPage/UploadReviewPage,
PatientImportContext/usePatientImportContext, NewCasePage, ImportResultSummary, их targeted tests,
frontend/e2e/onboarding-a3.spec.ts, данный отчёт. PatientList проверен штатным UI без изменения.

Ссылки результата намеренно не используют названия из review_decisions: при подтверждении
до debounce autosave там может остаться старый текст. Прямой target берётся только из
resolved_patients и относится к реально созданной записи.
