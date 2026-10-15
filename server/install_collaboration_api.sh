#!/usr/bin/env bash
set -euo pipefail

if (( $# != 1 )); then
    echo "Gebruik: $0 MAP_MET_SERVERBESTANDEN" >&2
    exit 2
fi

SOURCE_DIR=$1
NGINX_SITE=${OV_NGINX_SITE:-/etc/nginx/sites-available/openvertaling.nl}
INCLUDE_LINE='    include /etc/nginx/snippets/openvertaling-collaboration.conf;'

for tool in curl install nginx python3 systemctl; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "Vereist programma ontbreekt: $tool" >&2
        exit 1
    }
done
python3 -c 'import cryptography'
MODULES=(collaboration_api.py collaboration_schema.py collaboration_errors.py correction_schema.py correction_scope.py correction_verse_scope.py
    review_content.py review_components.py component_reviews.py correction_files.py corrections.py correction_routes.py correction_cli.py)
for file in "${MODULES[@]}" openvertaling-collaboration.service openvertaling-collaboration.nginx; do
    test -f "$SOURCE_DIR/$file" || {
        echo "Installatiebestand ontbreekt: $file" >&2
        exit 1
    }
done
test -f "$NGINX_SITE"

install -d -m 0755 /opt/openvertaling-collaboration
for file in "${MODULES[@]}"; do
    install -m 0644 "$SOURCE_DIR/$file" "/opt/openvertaling-collaboration/$file"
done
install -d -o www-data -g www-data -m 0700 /var/lib/openvertaling-collaboration
# Bestaande databases kunnen door onderhoud onder root zijn aangemaakt.
# De service moet ook de SQLite-journalbestanden kunnen bijwerken.
for database_file in /var/lib/openvertaling-collaboration/collaboration.sqlite3{,-wal,-shm,-journal}; do
    if [[ -L "$database_file" ]]; then
        echo "Onverwachte database-symlink: $database_file" >&2
        exit 1
    fi
    if [[ -f "$database_file" ]]; then
        chown www-data:www-data "$database_file"
        chmod 0600 "$database_file"
    fi
done
install -m 0644 "$SOURCE_DIR/openvertaling-collaboration.service" /etc/systemd/system/openvertaling-collaboration.service
install -m 0644 "$SOURCE_DIR/openvertaling-collaboration.nginx" /etc/nginx/snippets/openvertaling-collaboration.conf

SITE_BACKUP=$(mktemp)
cp -- "$NGINX_SITE" "$SITE_BACKUP"
site_changed=false
rollback() {
    if [[ "$site_changed" == true ]]; then
        install -m 0644 "$SITE_BACKUP" "$NGINX_SITE"
        nginx -t >/dev/null 2>&1 && systemctl reload nginx
    fi
    unlink -- "$SITE_BACKUP"
}
trap rollback ERR

if ! grep -Fqx "$INCLUDE_LINE" "$NGINX_SITE"; then
    python3 - "$NGINX_SITE" "$INCLUDE_LINE" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
include = sys.argv[2]
text = path.read_text(encoding="utf-8")
marker = "    location / {"
if text.count(marker) != 1:
    raise SystemExit("Nginx-site bevat niet exact één primaire location")
path.write_text(text.replace(marker, include + "\n\n" + marker), encoding="utf-8")
PY
    site_changed=true
fi

systemctl daemon-reload
systemctl enable --now openvertaling-collaboration.service
systemctl restart openvertaling-collaboration.service
nginx -t
systemctl reload nginx
if ! curl --fail --silent --show-error --retry 10 --retry-delay 1 --retry-connrefused \
    --retry-max-time 30 http://127.0.0.1:8787/api/collaboration/health >/dev/null; then
    systemctl status openvertaling-collaboration.service --no-pager -l >&2 || true
    journalctl -u openvertaling-collaboration.service -n 40 --no-pager >&2 || true
    exit 1
fi

trap - ERR
unlink -- "$SITE_BACKUP"
echo "Collaboration API geïnstalleerd en gecontroleerd."
