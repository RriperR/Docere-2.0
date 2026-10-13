# Синтетические документы AI-импорта

В файлах нет настоящих пациентов. Имя Synthetic Patient и даты вымышлены.

- `synthetic-report.pdf`: текстовый PDF, одна страница.
- `synthetic-scan.png`: изображение с теми же тестовыми сведениями.
- `synthetic-scanned.pdf`: PDF с изображением, без текстового слоя.
- `synthetic-photo.jpg`: JPEG для проверки нормализации.
- `synthetic-protected.pdf`: PDF с тестовым паролем `synthetic-only` для проверки отказа.

`provider.py` — управляемый HTTP-адаптер для изолированного E2E-стенда, который возвращает
заранее известные сведения этих документов. Запуск разрешён только с `DOCERE_AI_DEMO=1`.
Он не распознаёт документы и не используется приложением вместо реальной модели.

E2E: `frontend/e2e/import-ai.spec.ts` требует настроенного синтетического провайдера,
API/worker/dispatcher и отдельных demo-аккаунтов. Не подключайте этот провайдер к
окружению с реальными данными. Для проверки настоящего подключения используйте эти
же документы с вашим провайдером и вручную сверяйте поля/страницы.

## Набор E1

`manifest.json` — версионируемые синтетические исходники и эталон `import-ai-e1-v1`:
24 документа, 15 development и 9 holdout. Прежние пять примеров из
`scripts/evaluate_import_ai.py` сохранены с прежними именами, страницами и ожиданиями.
Пять бинарных E2E-фикстур выше также сохранены.

Покрытие: текстовый PDF и скан без текстового слоя, JPEG с перспективой, поворот,
низкое качество, многостраничные документы, 7 страниц через границу пакета из 5 страниц,
несколько пакетов, отсутствие даты/даты рождения, равнозначные и противоречащие даты,
дата рождения рядом с датой события, административные даты, разные пациенты и
совпадающее имя с разными датами рождения, внедрённые инструкции, защищённый и повреждённый PDF.
Все имена, даты, показатели и названия лекарств вымышлены.

Каждый документ содержит `pages` с номерами и исходным текстом. `expected.fields`
перечисляет допустимые значения и подтверждающие источники `page`/`excerpt`,
`empty_fields` — поля, которые должны остаться пустыми, `facts` — утверждения для
сверки пересказа с источниками. Полного буквального совпадения пересказа не требуется;
неперечисленные поля не ограничены. Низкое качество допускает отказ от заполнения
реквизитов; такие факты помечены `required: false`. Для защищённого/повреждённого PDF
ожидается `unreadable_document` без вызова провайдера и заполненных полей.
Защищённый пример использует существующий `synthetic-protected.pdf` с тестовым паролем
`synthetic-only`; plaintext в manifest описывает его синтетическое содержимое.

Разделение зафиксировано до оценки: development разрешено использовать при работе
над инструкцией, holdout предназначен для независимого измерения. Не изменяйте
инструкцию под ошибки holdout и не переносите документы между частями без новой версии набора.

Генерация без AI, чтения настроек провайдера и сети (зависимости уже входят в проект):

```bash
.venv/bin/python scripts/import_ai_dataset.py --output artifacts/import-ai-dataset
.venv/bin/python scripts/import_ai_dataset.py --split development --output artifacts/import-ai-development
.venv/bin/python scripts/import_ai_dataset.py --split holdout --output artifacts/import-ai-holdout
```

В Git хранятся генератор, исходники и эталон; новые PDF/PNG/JPEG/DICOM/ZIP и manifest
с SHA-256 пишутся только в игнорируемый `artifacts/`. Генератор не использует случайные
UID, часы или системные шрифты. Байты воспроизводимы при одинаковых версиях Pillow/pydicom;
PDF writer не добавляет временных меток, ZIP entries имеют фиксированную дату.
Mixed ZIP содержит `text-report.pdf`, `no-date.png` и синтетический DICOM с фиксированными UID.
Он относится к development и создаётся только для `--split all` / `--split development`.
Holdout manifest не содержит метаданные этого архива. Повторная генерация разрешена
только для той же версии и того же split; несовместимый или неуправляемый непустой
`--output` отклоняется до записи, никакие файлы не удаляются. Для другого split задайте
отдельный каталог. Без `--output` полный набор пишется в `artifacts/import-ai-dataset`,
а development/holdout — в `artifacts/import-ai-dataset-development` / `artifacts/import-ai-dataset-holdout`.
Критический тест проверяет отказ ручного выбора DICOM, автоматический выбор только
PDF/PNG и два вызова управляемого провайдера. Внешний HTTP transport в тесте заблокирован.

Проверка набора без реальных AI-запросов:

```bash
.venv/bin/pytest -p no:cacheprovider tests/unit/test_import_ai_dataset_unit.py tests/critical/test_import_ai_dataset.py -q
```

## Оценка E2

`evaluate_import_ai.py` без `--live-ai` генерирует выбранный E1 split и выполняет
воспроизводимый evaluator через управляемый adapter, который возвращает эталонные
фикстуры. Он не распознаёт документы и не измеряет качество реальной модели.
Настройки провайдера/секреты не читаются, сетевые запросы отсутствуют.

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --output artifacts/import-ai-evaluation-e2
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --split holdout --output artifacts/import-ai-evaluation-holdout
```

В выбранном каталоге создаются `results.json`, `manual-review-template.json` и
`manual-review.md`: точность ограниченных E1 реквизитов, корректные пустые/неоднозначные
поля, ошибки формата/страниц, безопасные коды отказов и таблица утверждение → источник
→ ручная оценка. Полноту непустого свободного пересказа размечает человек;
другой LLM не используется как эталон. Без разметки итоговые пропуски фактов — `null`.
Офлайн latency/usage/стоимость — «нет данных», статус полного E2 — `prepared_external`.

Внешнее измерение требует явного opt-in и настроенного vision provider:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --live-ai --split development --output artifacts/import-ai-e2-live-development
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --live-ai --split holdout --output artifacts/import-ai-e2-live-holdout
```

Команды отправляют только сгенерированные синтетические документы выбранного split,
сохраняют проверенный результат/доступную usage и времена в artifacts. Live запуск
требует нового каталога; prompt и holdout эталон под результаты не изменяются.
Для all используется `--split all` (24 документа, включая прежние пять примеров).
DICOM в evaluator не отправляется; mixed ZIP проверяется отдельным critical gate.

После ручной разметки копии шаблона подсчёт выполняется без повторного AI:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --output artifacts/import-ai-e2-live-holdout --manual-review artifacts/import-ai-e2-live-holdout/manual-review.json
```

Результаты и правила ручной оценки, тарифов, отказов и продолжения полного E2:
[профильный отчёт](../../../docs/reviews/import-ai-evaluation-e2.md).
