#!/bin/sh
set -eu
# Append only: an open tab may request a previous release's lazy chunk.
cd "${ASSETS_SOURCE:-/usr/share/nginx/html/assets}"
target="${ASSETS_DEST:-/retained-assets}"
find . -type f | while IFS= read -r relative; do
    destination="$target/$relative"
    if [ -f "$destination" ]; then
        cmp -s "$relative" "$destination" || { echo 'Asset name collision; release rejected.' >&2; exit 1; }
    else
        mkdir -p "$(dirname "$destination")"
        cp "$relative" "$destination"
    fi
done
