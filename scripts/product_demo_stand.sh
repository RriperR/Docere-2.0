#!/bin/sh
# Изолированный локальный стенд. Никогда не читает .env и не сбрасывает данные.
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"
compose() {
    docker compose --env-file /dev/null --project-directory "$project_root" \
        -p "${PRODUCT_DEMO_PROJECT:-docere-roadmap-a2-20261013}" \
        -f docker-compose.yml -f scripts/product_demo.compose.yaml "$@"
}
check() {
    curl --fail --silent --show-error http://localhost:8012/api/health
    curl --fail --silent --show-error -o /dev/null http://localhost:8012/
    compose ps
}
case "${1:-check}" in
    check) check ;;
    up)
        if curl --fail --silent -o /dev/null http://localhost:8012/api/health; then
            echo 'Порт 8012 уже обслуживает API; переиспользуйте проверенный стенд. Новые данные создаёт setup.'
            check
            exit 0
        fi
        compose build api frontend
        compose up -d postgres redis minio createbuckets
        compose wait createbuckets
        compose run --rm --no-deps api migrate
        compose up -d api frontend gateway celery-worker import-dispatcher
        echo 'Дождитесь готовности: sh scripts/product_demo_stand.sh check'
        ;;
    create-admin)
        compose exec -T api python -m app.presentation.cli create-admin \
            --email product-admin@docere.demo --password ProductDemo123 \
            --fio 'Администратор Демонстрации' --phone '+79990000099'
        ;;
    dev)
        cd frontend
        DOCERE_DEV_API_URL=http://localhost:8012 npm run dev -- --host 127.0.0.1 --port 4174 --strictPort
        ;;
    *) echo 'Использование: sh scripts/product_demo_stand.sh {check|up|create-admin|dev}' >&2; exit 2 ;;
esac
