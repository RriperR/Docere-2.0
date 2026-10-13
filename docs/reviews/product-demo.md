# Продуктовая демонстрация и проверка спроса

Дата: 13.10.2026. Исполнитель product_demo; production UI/backend, STATUS и lockfiles
не менял. Commit/push, seed/reset, удаление данных и реальные AI-вызовы не выполнялись.

## Готовый результат

- `docs/DEMO.md`: запуск, вход в два браузерных профиля и показ примерно за шесть минут.
- `scripts/product_demo_setup.mjs`: новые синтетические аккаунты и данные через API;
  содержательные PNG из локальных HTML, ручной import resolve, приглашение, вопрос,
  ответ, итог и публикация. Один дополнительный пустой врач для проверки первого входа.
- `scripts/product_demo_stand.sh`, `scripts/product_demo.compose.yaml`: изолированный
  Compose project, порт 8012, собственные volumes, AI false, `--env-file /dev/null`.
  Стенд в этой сессии переиспользован, fresh build/start этим wrapper не выполнялся.
- `scripts/product_demo_check.mjs`: проверка готовых состояний через API;
  открытый вопрос должен оставаться открытым, иначе нужно создать новый run.
- `frontend/e2e/product-demo.spec.ts`: настоящий браузерный переход от истории/вложения
  к ответу другого врача и сохранению итога; AI false подтверждается API.
- `docs/PRODUCT-VALIDATION.md`: протокол 5–7 врачей, реальные прошлые задачи,
  наблюдение без подсказок, конкретное продолжение и фактический возврат.

## Стенд и доступ

Работающий Docker project `docere-roadmap-a2-20261013` обнаружен через Docker с escalation;
API `http://localhost:8012/api/health` вернул ok. Dev UI текущих исходников запущен:
`http://127.0.0.1:4174`, shell session 93615, proxy на 8012. Его нужно оставлять запущенным
на время показа. Docker-сборка на 8012 не отражает последние frontend edits.
Отдельный синтетический администратор создан штатным Python CLI:
`product-admin@docere.demo / ProductDemo123`; существующие аккаунты не заменялись.
Адреса и способ входа переданы product_journey и product_dashboard.

Готовый, не расходованный E2E run:

```text
artifacts/product-demo/20261013091356-8a343d28/OPEN-ME.md
artifacts/product-demo/20261013091356-8a343d28/state.json
coordinator: product-coordinator-20261013091356-8a343d28@example.com
colleague: product-colleague-20261013091356-8a343d28@example.com
empty: product-empty-20261013091356-8a343d28@example.com
password: ProductDemo123
patient: 97b3c5c7-efa7-4b43-be14-92ebaae3300f
active case: 2804cfc8-6f50-44bc-bc45-03fb7e550ca7
completed case: cd36800e-667f-42da-97e3-55e80da6e3ee
```

Артефакты находятся в ignored каталоге `artifacts`; setup воспроизводит их заново,
поэтому generated картинки и state не добавляются в Git. State не содержит bearer tokens.
Если `PRODUCT_DEMO_OUTPUT` уже существует, setup отклоняет запуск до API-вызовов и записи файлов.
Первый прерванный запуск оставил отдельные синтетические аккаунты/импорт; ничего не удалялось.

## Выполненные проверки

- Setup выполнен полностью два раза: настоящие ручные импорты completed,
  отдельные needs_review, три записи со вложениями и опубликованный итог.
- Playwright: **1 passed (8.3s)** на run `20261013091102-4bdffe41`.
  Через UI: вход обоих врачей, раскрытие записи, PNG preview, адресный ответ,
  сохранение версии итога, просмотр опубликованного результата.
  Первый запуск теста был остановлен из-за отсутствовавшего в тесте раскрытия карточки;
  действие исправлено в спецификации, production UI для этого не менялся.
- Readiness check на свежем run: passed, active opinion open, completed case closed,
  опубликованный record совпал, 3 исходных вложения, ai_requested false.
- `node --check scripts/product_demo_setup.mjs`, `sh -n scripts/product_demo_stand.sh`,
  targeted ESLint для E2E, `git diff --check`: passed.
- `docker compose --env-file /dev/null ... config --quiet`: passed.
  `sh scripts/product_demo_stand.sh check`: API/frontend и существующие контейнеры healthy.
- Повторный setup в существующий output: ожидаемый EEXIST до API-вызовов.
- Изображение мониторирования просмотрено визуально: содержимое читаемо, синтетическая
  маркировка и ручное происхождение заметны, ничего не обрезано.

## Ограничения

AI извлечение/сводка отключены; подготовленные тексты написаны вручную и явно обозначены.
Результатов AI или врачебного исследования нет. Opt-in AI не выполнялся.
Живой показ расходует открытый вопрос; для повторения нужен новый run.
Повторный needs_review использует те же документы и может показывать предупреждения о дублях;
его не нужно подтверждать ради показа. Медицинские записи не подтверждены врачом автоматически.
Реальные пользователи F2, итоговые F1/F3 и публичный пилот остаются внешней/общей работой.
Полный frontend build/lint выполняют владельцы production frontend изменений; здесь проверен
собственный E2E и скрипты. Новый холодный Docker build этим wrapper не проверен.
