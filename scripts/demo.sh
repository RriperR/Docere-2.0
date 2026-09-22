#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
archive_path="$project_root/docere-demo-archive.zip"

cd "$project_root"

wait_for_url() {
    url=$1
    label=$2
    attempt=1
    while [ "$attempt" -le 60 ]; do
        if curl --fail --silent --show-error "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
        attempt=$((attempt + 1))
    done
    echo "$label не стал доступен за 120 секунд" >&2
    return 1
}

check_demo() {
    wait_for_url 'http://localhost:8000/api/health' 'API'
    wait_for_url 'http://localhost:8000/' 'Web-интерфейс'
    docker compose ps
    echo 'Docere доступен: http://localhost:8000'
    echo 'OpenAPI доступен: http://localhost:8000/docs'
}

seed_demo() {
    docker compose run --rm api migrate
    docker compose run --rm -v "$project_root:/demo" api \
        seed-demo --archive-output /demo/docere-demo-archive.zip
    echo "Синтетический архив создан: $archive_path"
}

case "${1:-up}" in
    up)
        docker compose up -d --build
        check_demo
        seed_demo
        check_demo
        ;;
    reset)
        check_demo
        seed_demo
        ;;
    check)
        check_demo
        ;;
    logs)
        docker compose logs --tail=200 api celery-worker gateway frontend
        ;;
    down)
        docker compose down
        ;;
    *)
        echo 'Использование: scripts/demo.sh {up|reset|check|logs|down}' >&2
        exit 2
        ;;
esac
