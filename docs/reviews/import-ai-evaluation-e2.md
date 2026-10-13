# E2: воспроизводимая оценка AI-извлечения

Дата: 13.10.2026. Статус полного E2: **prepared_external**.
Офлайн инструмент, машинный отчёт, ручная таблица и обязательные targeted gates подготовлены.
Реальный провайдер не вызывался. Ключи и `.env` не читались; клиническое качество модели
и экспертная ручная оценка не измерены. Production AI, инструкция, holdout и эталоны E1 не изменялись.

## Команды и артефакты

Из корня репозитория, с установленными зависимостями:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --output artifacts/import-ai-evaluation-e2
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --split development --output artifacts/import-ai-evaluation-development
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --split holdout --output artifacts/import-ai-evaluation-holdout
```

Без `--live-ai` используется `ControlledProvider`: ответы берутся из фиксированного manifest,
проходят существующий production parser, подготовку страниц и объединение пакетов.
Это проверка evaluator, **не распознавание документов и не измерение качества модели**.
Сеть и чтение настроек провайдера запрещены regression test. Документы, JSON и Markdown
повторяемы при одинаковых версиях зависимостей; офлайн времена оставлены `null`.
Прежние пять `SAMPLES` и функция их генерации сохранены.

Каждый каталог содержит сгенерированные синтетические документы и:

- `manifest.json`: выбранный split E1 с SHA-256 документов;
- `results.json`: версия evaluator, dataset/model/prompt, hash инструкции, параметры,
  результаты всех документов, безопасные коды отказов, метрики, request telemetry и стоимость;
- `manual-review-template.json`: неизменяемые утверждения/источники/ожидаемые факты с пустыми оценками;
- `manual-review.md`: полный набор утверждений → источники → ручная оценка и таблица полноты.

Артефакты находятся в игнорируемом `artifacts/`; сетевые ответы не попадают в Git.
Неуспешные примеры сохраняются в `automatic.failed_examples`, даже если CLI завершится с кодом 1.
Частичный отказ сохраняет usage успешных пакетов и список всех вызовов; незавершённый
клинический результат не подставляется вместо полного документа.

Повторный controlled запуск в том же каталоге допустим только с тем же E1 split/версией,
без завершённой ручной разметки. Live запуск всегда требует нового каталога.
Разные режимы/версии и неуправляемый непустой каталог отклоняются до внешнего запроса;
файлы не удаляются. Не выполняются seed, reset, миграции или изменения существующей БД.

## Как читать метрики

| Метрика | Правило |
|---|---|
| `filled_field_accuracy` | Верные заполненные реквизиты / заполненные реквизиты, ограниченные E1. Поле, которое должно быть пустым, входит в знаменатель как ошибка, если заполнено. |
| `field_slot_accuracy` | Правильные значения / все ожидаемые реквизиты E1; пропуск обязательного значения снижает долю. Допустимый `None` считается корректным отказом. |
| `missing_required_fields` | Пропущенные реквизиты, для которых E1 не разрешает `None`. |
| `correct_abstention` | Оставленные пустыми поля / все `empty_fields` E1. |
| `correct_ambiguity` | Одновременно отсутствует спорное поле и присутствует ожидаемая проблема `conflicting:*`. |
| `format_errors`, `page_errors`, `excerpt_errors`, `missing_source_fields` | Формат проверенного результата, диапазон/тип страницы, непустой фрагмент и наличие источников. |
| `invalid_response_errors` | Production parser отверг ответ. Причина внутри ответа не сохраняется, поэтому нельзя приписать её именно формату или страницам. |
| `document_page_count_errors` | Успешная подготовка вернула число страниц, отличное от E1. |
| `excerpt_not_verbatim` | После нормализации пробелов фрагмент не является подстрокой исходной страницы E1. Только лексическая диагностика; перевод/OCR требуют ручной оценки. |
| `missing_required_facts_without_summary` | Гарантированные пропуски обязательных фактов, когда пересказ целиком отсутствует. |
| `manual.missing_required_facts` | Автоматический подсчёт `present=false` по ручной разметке всех обязательных фактов. До завершения разметки — `null`; отдельно видны уже найденные пропуски и оставшиеся строки. |
| `partial_document_errors` | Ошибка документа после хотя бы одного успешного extract. |

Неограниченные эталоном поля автоматически не оцениваются на точность.
Наличие фрагмента на странице не доказывает, что он подтверждает утверждение.
Полноту непустого свободного пересказа проверяет человек: буквального совпадения всего
пересказа не требуется, другой LLM не используется как истинный эталон.
Все знаменатели, отсутствующие значения и неудачные документы доступны в JSON.

`request_telemetry` считает вызовы `extract` (пакет страниц), доступные token usage и
их ошибки. В live режиме измеряется wall time каждого extract с внутренними повторами
и всего документа с подготовкой страниц. Отдельные HTTP attempts/times существующий
adapter не выдаёт: `http_attempt_count=null`; число extract не является числом HTTP requests.
Usage пустая, если провайдер её не вернул. Известные данные успешных пакетов не теряются
при следующем отказе. Стоимость — `no_data` / «нет данных», пока нет полной prompt/completion
usage каждого вызова и известного тарифа с валютой и источником.

## Результат проведённого офлайн прогона

Dataset `import-ai-e1-v1`: 24 документа (15 development, 9 holdout), последовательный обход,
23 controlled extract, 0 внешних запросов. Два ожидаемых отказа `unreadable_document`
(защищённый и повреждённый PDF) получены до вызова provider. Unexpected/partial errors: 0.

Model: `controlled-manifest-fixture-v1`; production prompt version: `import-facts-v3`.
Prompt SHA-256: `f9552be99d24cb8bd2615d335e2a3a166bbc9b0ec4fcbd953d3999732be7809e`.
Run ID: `3c814954d16fd6eba46fd917517b4eec59d03dafe8599f57ddb869c457a6a1e2`.

Проверка инструмента: 51/51 заполненных эталонных реквизитов и slots, 27/27 корректно
пустых полей, 5/5 проверок неоднозначности. Проверены 110 ссылок на страницы;
ошибок формата/страниц/пустых источников нет. Эти значения получены из заданных ответов
фикстуры и не являются результатом реальной модели. Live latency/usage/стоимость: нет данных.

Полная таблица содержит 28 строк утверждений; ожидаются оценки по 26 обязательным фактам
и одному необязательному. Все оценки сейчас пустые, `manual.status=pending`,
`manual.missing_required_facts=null`; рецензент не назначен.
Снимок нескольких строк из `artifacts/import-ai-evaluation-e2/manual-review.md`:

| Документ | Утверждение | Источник | Ручная оценка |
|---|---|---|---|
| multipage-discharge.pdf | The fictional medicine TestMedicine is listed at 5 mg once daily. | Стр. 2: TestMedicine, 5 mg once daily. | Ожидает человека |
| several-dates.png | Two examinations are listed without a primary event. | Стр. 1: No primary event specified. | Ожидает человека |
| no-date.png | Scheduled examination was completed. | Стр. 1: examination completed. | Ожидает человека |
| document-instructions.png | Scheduled examination was completed. | Стр. 1: examination completed. | Ожидает человека |
| batch-boundary.pdf | The last page states that fictional marker Delta is absent. | Стр. 7: Final observation: fictional marker Delta is absent. | Ожидает человека |
| multi-packet.pdf | Packet B lists fictional marker Gamma at 7 test units. | Стр. 2: Fictional laboratory marker Gamma: 7 test units. | Ожидает человека |

У summary один общий список источников; evaluator сохраняет его возле каждого утверждения.
Сегментация по предложениям/строкам — подсказка для рецензента: составные фразы проверяются
целиком. Не назначать оценку по самому факту существования страницы/фрагмента.

## Точная точка продолжения полного E2

После явного opt-in владельца и настройки совместимого vision provider через безопасную
конфигурацию выполнить **новые** каталоги, не изменяя prompt под holdout:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --live-ai --split development --output artifacts/import-ai-e2-live-development
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --live-ai --split holdout --output artifacts/import-ai-e2-live-holdout
```

Эти команды отправляют только сгенерированные синтетические PDF/PNG/JPEG выбранного E1 split.
DICOM/mixed ZIP не отправляются evaluator; их исключение проверяется существующим gate.
Запуски документов независимы, параметры production AI сохранены; concurrency evaluator = 1,
page budget применяется к каждому документу отдельно, не имитируется единый bulk import run.

Для каждого полученного live отчёта человек копирует `manual-review-template.json` в отдельный
`manual-review.json`, записывает своё имя/идентификатор в `reviewer`, ставит `grade`:
`confirmed` (подтверждено), `unsupported` (не подтверждено), `contradicted` (противоречит),
и `present: true/false` для каждого ожидаемого факта. Сверять исходные pages и документы,
включая противоречия, разных пациентов и внедрённые инструкции. Поля `note` разрешены.
Не менять run ID, строки утверждений, их ID, страницы, источники или required.

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_import_ai.py --output artifacts/import-ai-e2-live-holdout --manual-review artifacts/import-ai-e2-live-holdout/manual-review.json
```

Эта команда только обновляет ручные метрики сохранённого JSON и пишет `manual-reviewed.md`;
она не читает настройки и не повторяет внешние запросы. Устаревшая/чужая разметка, неизвестные
оценки и изменение доказательств отклоняются. Шаблон остаётся пустым и неизменным.
CLI возвращает 1 при автоматических ошибках, найденных ручных пропусках или
неподтверждённых/противоречащих утверждениях; отчёт сохраняется.

Для известного тарифа в live команде дополнительно задать все четыре флага:
`--input-cost-per-million <цена> --output-cost-per-million <цена> --currency <валюта>
--tariff-reference <источник тарифа>`; значения должны быть конечными и неотрицательными.
При неполной usage цена остаётся «нет данных». Тариф в этой работе не выбирался.

После live прогонов и ручной оценки записать реальные model/options/latency/usage,
неудачные примеры и ограничения; только затем решать статус E2/E3.
Результаты характеризуют фиксированный синтетический набор, а не клиническую точность
на любой медицинской документации. Офлайн подготовка не является основанием для `done`.

## Проведённые проверки

```bash
.venv/bin/pytest -p no:cacheprovider tests/unit/test_import_ai_evaluation_unit.py tests/unit/test_import_ai_dataset_unit.py -q
.venv/bin/pytest -p no:cacheprovider tests/critical/test_import_ai.py tests/critical/test_import_ai_dataset.py -k 'not postgres' -q
.venv/bin/pytest -p no:cacheprovider tests/critical/test_case_ai.py -k 'summary_provider_rejects_invalid_json_and_sources or summary_ambiguity_across_batches_never_selects_arbitrary_date or revocation_hides_completed_result_and_cancels_running' -q
.venv/bin/mypy --config-file=mypy.ini scripts/evaluate_import_ai.py scripts/import_ai_evaluation.py scripts/import_ai_dataset.py
.venv/bin/ruff check scripts/evaluate_import_ai.py scripts/import_ai_evaluation.py scripts/import_ai_dataset.py tests/unit/test_import_ai_evaluation_unit.py
.venv/bin/ruff format --check scripts/evaluate_import_ai.py scripts/import_ai_evaluation.py scripts/import_ai_dataset.py tests/unit/test_import_ai_evaluation_unit.py
```

Unit: 91 passed. Existing import/dataset gates: 36 passed, один PostgreSQL concurrency test
исключён. Case source/ambiguity/revocation: 7 passed, 8 других тестов вне выбранного scope.
Scoped strict mypy: `scripts/evaluate_import_ai.py`, `scripts/import_ai_evaluation.py`,
`scripts/import_ai_dataset.py` — passed. Публичные контракты используют E1 TypedDict,
`DocumentPage`/`AiExtraction` и типизированный JSON отчёта; blanket Any не добавлялся.
Для существующего E1 DICOM генератора строка UID обёрнута в тип `UID` для mypy;
состав набора/эталоны не менялись. Ruff check/format: passed. Использовалась существующая `.venv` Python 3.12; Python 3.13
не проверялся. Full backend/frontend gates принадлежат интегратору/B1/A2; в этом пакете
production-код не менялся. PostgreSQL concurrency и real provider measurement не утверждаются.

Обязательные E2 gates покрыты существующими тестами: отсутствие даты/неизвестные actions,
недоверенные инструкции в user message и отсутствие tools, owner/access/role loss,
неверные номера/формат источников, удаление неоднозначного поля, mixed ZIP/DICOM.
Это проверка защитного контракта; устойчивость реальной модели к prompt injection
требует внешнего измерения и ручной оценки.
