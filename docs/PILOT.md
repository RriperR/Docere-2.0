# Изолированный локальный стенд Docere (D4)

`compose.pilot.yaml` — самостоятельный конфиг, не override демо-стенда. Он публикует
только TLS gateway на `127.0.0.1:18443`. PostgreSQL, Redis, MinIO, API и frontend
не имеют host ports. Все volumes и сеть принадлежат явно названному проекту
`docere-pilot-*`; внешних/shared volumes и `container_name` нет. Порт 8012 запрещён
в helper, существующий стенд не используется. Это локальная подготовка D4.

**Публичный пилот ещё не готов:** D1 (серверные сессии/отзыв), D2 (SMTP/reset),
D3 (общие лимиты), D5 (доказанное восстановление), D6 (диагностика фоновых операций)
должны быть завершены и приняты. Внешнее размещение требует отдельного поручения.
Допустимы только синтетические данные; рабочие медицинские документы сюда не загружать.

## Конфигурация

Использовать `deploy/pilot/env.example`. В нём нет секретов и действующего домена.
Секреты — абсолютные пути к отдельным файлам вне checkout/build context:
JWT key, пароль PostgreSQL, пароль Redis, access/secret MinIO, TLS certificate/key,
AI token (пустой файл при AI=false). Хранить каталог с mode 0700 и secrets/env с
mode 0600. Compose secrets на локальном Docker — bind mounts, **не зашифрованный
secret manager**; администраторам Docker доступны контейнеры и память процессов.
Не коммитить и не передавать каталог. Не вставлять значения в env, командную строку
или вывод `docker inspect`. Не менять DB/storage credentials уже созданных volumes
простым редактированием файлов: это требует отдельной процедуры ротации.

`pilot.py config` и runtime guard API/worker/dispatcher/migrate отклоняют слабые
или известные demo secrets. Приложение получает подключения только после guard;
пустые значения не заменяются `docere`, `minioadmin` или `dev-secret-key`.
Для каждого релиза задать отдельные неизменяемые tags или digests API/frontend,
сохранить предыдущие references. Не перетегировать предыдущий релиз.

`PILOT_HOST`, `PILOT_ORIGIN=https://HOST:PORT` и authority проверяются строго:
gateway отклоняет чужой Host (421) и чужой Origin (403). Отсутствующий Origin
допустим для same-origin navigation и CLI. CORS wildcard отсутствует; frontend/API
работают с одного origin. Входной X-Forwarded-For заменяется адресом соединения,
X-Request-ID генерируется gateway. API недоступен напрямую с host.
Это контроль периметра, не замена ACL/аутентификации или распределённого limiter D3.

Storage: внутренний MinIO, bucket `docere-pilot-records`, регион `us-east-1`, TLS
завершается на gateway. Корневой MinIO account пока используется и приложением;
перед внешним пилотом требуется отдельный service account с bucket policy,
подтверждённые настройки хранения/шифрования и процедура ротации.

AI по умолчанию выключен. Для включения нужны явные `PILOT_AI_ENABLED=true`,
URL, model и token file. Без конфигурации guard откажет в запуске. Внешний AI в
локальном smoke не вызывается. Provider token — непрозрачное непустое значение
без CR/LF; минимальная длина серверных secrets к нему не применяется.
SMTP в текущем runtime отсутствует: **APP_SMTP_*
не имеют эффекта**. D2 должен определить поддерживаемые настройки SMTP, отдельный
ключ шифрования outbox payload и фиксированный frontend origin, затем проверить
mail sink и реальную доставку. Этот env не заявляет фиктивное подключение почты.

## Fresh install

Нужны Docker Compose v2+, Python 3.12/3.13 и openssl; для smoke — зависимости
проекта (`.venv`). Все команды выполнять из корня checkout. Не запускать
`seed-demo`, `demo-reset`, `down -v`; helper не предоставляет этих команд.

```bash
python3 scripts/pilot.py init-local \
  --directory /private/tmp/docere-pilot-local \
  --project docere-pilot-local --port 18443
python3 scripts/pilot.py config --env /private/tmp/docere-pilot-local/pilot.env
python3 scripts/pilot.py up --build --env /private/tmp/docere-pilot-local/pilot.env
PYTHONPATH=src .venv/bin/python scripts/pilot_smoke.py \
  --env /private/tmp/docere-pilot-local/pilot.env
```

`init-local` создаёт **новый** каталог, случайные локальные credentials и тестовый
сертификат `localhost` сроком семь дней; повторная команда не перезаписывает secrets.
Этот сертификат нельзя использовать на реальном домене. Не отключать TLS verify:
smoke доверяет только файлу тестового сертификата. Для браузера разрешить тестовый
сертификат вручную только для этого localhost; не устанавливать его глобальным CA.

`up` последовательно проверяет конфиг, при `--build` собирает API/frontend, ждёт
health PostgreSQL/Redis/MinIO, создаёт bucket и сохраняет assets, останавливает
gateway/API/worker/dispatcher/frontend, выполняет **один** `migrate` и только
после успеха пересоздаёт процессы. Установка/обновление имеют короткое окно
maintenance; rolling/zero-downtime deploy не заявляется. Не выполнять два `up`
одновременно. Не запускать raw `docker compose up`: он обходит порядок миграций.

Администратор создаётся существующим CLI без seed, пароль поступает через stdin:

```bash
python3 scripts/pilot.py admin --env /private/tmp/docere-pilot-local/pilot.env \
  --email synthetic-admin@example.com
```

Smoke создаёт нового синтетического пациента, входит, проверяет `/me` и отказ
импорта для пациента (403). Затем существующий CLI создаёт отдельного synthetic
admin со случайным паролем через stdin. Admin загружает синтетический архив,
ждёт review от worker и пропускает всех кандидатов. Записи
кандидатов в историю не добавляются; тестовые аккаунты/import metadata остаются
в отдельном проекте. Проверяются TLS, UI/asset, чужой Host/Origin, 401 без токена,
закрытые docs и завершение import. Это не приёмка D1–D3/D5–D6 или вся регрессия.

## Update и предыдущие assets

1. Сохранить предыдущий env (references и пути, не экспорт значений secrets),
   release notes, current Alembic revision. Согласованная годная backup перед
   внешними обновлениями требует D5; один `pg_dump` не покрывает документы.
2. В рабочем env выбрать новые API/frontend references. Для локальной сборки —
   отдельные tags, например `docere-pilot-api:release-2`/`docere-pilot-frontend:release-2`.
3. Выполнить `pilot.py up [--build] --env ...`, затем `pilot_smoke.py --env ...`.
   Не менять project, secret paths, bucket или volume names при обновлении.

`publish-assets` берёт `/usr/share/nginx/html/assets` из **нового frontend image**
и добавляет файлы в project volume `frontend_assets`. Существующие файлы не
удаляются; конфликт имени с отличающимся содержимым отвергает релиз до остановки
старых процессов. Gateway отдаёт `/assets/*` из retained volume, а HTML из текущего
frontend с `Cache-Control: no-store`. Поэтому старая открытая вкладка может загрузить
старый lazy chunk после смены HTML. Retained assets не содержат пользовательских
данных и не дают обхода API ACL. API совместимость открытой вкладки надо проверять
при каждом изменении контрактов. Серверный logout/revoke должен быть принят в D1;
конфиг D4 сам по себе не отзывает нынешние stateless JWT.

Проверка двух настоящих релизов: до update сохранить URL одного hash asset и его
SHA-256; после update проверить новый hash из нового HTML и повторить GET старого
URL — 200 и прежний SHA-256. Войти/сохранить допустимое действие из уже открытой
вкладки. После D1 дополнительно выполнить logout и убедиться в 401 старого API
токена. `tests/test_pilot_config.py` проверяет процедуру append-only на двух
наборах assets и отказ при коллизии. Автоматического pruning нет: сохранять assets
пока возможны открытые вкладки/rollback; очистка только после согласованного окна
перехода и проверки отсутствия используемых старых chunks. Не удалять весь volume.

## Failed migration и rollback

Если migrate завершился ошибкой, `up` прекращается: gateway и писатели остаются
остановленными, инфраструктура и volumes сохранены. Не возобновлять процессы
автоматически, не запускать seed/reset, не делать downgrade для «исправления».
Проверить статус и private migration diagnostics, фактическую Alembic revision,
применение отдельных DDL и совместимость схемы. Исправить причину и повторить тот
же релиз. Если схема повреждена/несовместима, нужна процедура D5 в **новую** цель.

При подтверждённой совместимости предыдущего приложения с текущей схемой вернуть
предыдущие image references в копию env с **тем же project и secret paths**:

```bash
python3 scripts/pilot.py rollback --schema-compatible --env /path/to/previous.env
PYTHONPATH=src .venv/bin/python scripts/pilot_smoke.py --env /path/to/previous.env
```

`rollback` сохраняет/публикует assets предыдущего frontend, меняет только процессы
и не выполняет migrate/downgrade. Флаг означает, что оператор проверил контракт
схемы и API; автоматического доказательства совместимости нет. Без такого
подтверждения оставить ingress остановленным и подготовить восстановление D5.

## Состояние и логи

```bash
python3 scripts/pilot.py status --env /path/to/pilot.env
python3 scripts/pilot.py logs --env /path/to/pilot.env --service gateway
python3 scripts/pilot.py logs --env /path/to/pilot.env --service celery-worker
python3 scripts/pilot.py stop --env /path/to/pilot.env
```

Health: PostgreSQL readiness, authenticated Redis ping, MinIO readiness, API
liveness, frontend, gateway liveness и адресный Celery ping. `/api/health` не
доказывает готовность DB/storage; import smoke проверяет весь путь. Dispatcher
пока имеет только process/restart status: age outbox/leases и recovery диагностика
требуют D6. Не добавлять фиктивный success health для фонового цикла.

Gateway access log выключен; Uvicorn access logger выключен runtime wrapper,
так как он включает query strings. Gateway ошибки ограничены уровнем crit;
Docker logs ограничены ротацией 3×10 MB. Текущие app/worker exceptions могут
содержать диагностические детали: читать локально, не отправлять сырой вывод
третьим лицам и не прикладывать к публичным issues. Для отчёта брать только
service/state/status/count, request/job IDs; исключить документы, имена, email,
токены, provider responses, пароли/URLs подключения. Полная гарантия redaction
и диагностика ошибок входят в последующие security/operations gates.

## Настройки, необходимые от владельца перед внешним пилотом

- Реальный домен, DNS, VPS/сеть/firewall, порт и доступный TLS certificate/key,
  issuer/renewal, точные allowed host/origin и доверенный reverse proxy hop.
- Registry/release references и политика совместимости схемы/API/открытых вкладок.
- Способ хранения/ротации secrets, storage service account/bucket policy,
  размещение/шифрование данных и ограничения синтетического набора.
- SMTP endpoint/port, TLS режим, sender, credentials и ключ payload после D2;
  mail sink для теста и разрешение отдельной проверки реальной доставки.
- Если AI нужен: endpoint/model/token и согласованные условия передачи данных.
- Принятые D1–D3, backup/restore протокол D5 с измеренными RPO/RTO и D6.

Пока этих значений нет, конфиг намеренно остаётся с loopback binding и локальным
сертификатом. Домен, VPS, SMTP и TLS credentials здесь не подразумеваются.

## Фактическая локальная проверка 12 октября 2026

Проверен только проект `docere-pilot-d4-20261012`, env/secrets вне checkout в
`/private/tmp/docere-pilot-d4-20261012`, единственный опубликованный порт
`127.0.0.1:18443`. Образы API/frontend собраны как `docere-pilot-api:d4` и
`docere-pilot-frontend:d4`; миграции прошли до `20261011_25`. Проект A1 на 8012
не изменялся. Все настроенные healthchecks успешны, dispatcher — running.

- `pilot.py config`: успешно; `ruff check` и `ruff format --check` четырёх Python
  файлов: успешно; `pytest tests/test_pilot_config.py -q -p no:cacheprovider`:
  **26 passed**, включая остановку писателей при ошибке migrate (mock), короткий
  AI token, неправильные secrets/origin/project и коллизию assets.
- `pilot_smoke.py`: успешно после fresh install, обновления и последнего изменения
  logging wrapper. Проверены TLS, UI/assets, 421/403/401/404, patient import 403,
  CLI synthetic admin и фоновый import → review → skip → completed.
- Реальное переключение frontend на `docere-ux-frontend:local` и обратно:
  `index-DOQnNtCx.js` и `index-Bp3gPnqh.js` доступны после переходов с HTTP 200
  и прежним SHA-256. Сработали compatible frontend rollback и update с no-op migrate.
- API получил безопасный уникальный query marker на `/api/health`; в Docker logs
  marker отсутствует, техническая запись `http_request` присутствует.

SMTP/AI delivery, внешние TLS/DNS, реальное повреждение миграции, восстановление
backup, rollback на другую API/schema и ручное сохранение из ранее открытой вкладки
не проверены. Проверка server-side logout отложена до D1. Полная регрессия не запускалась.
