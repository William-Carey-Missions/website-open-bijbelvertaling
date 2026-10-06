#!/usr/bin/env bash
set -euo pipefail

if (( $# != 1 )); then
    echo "Gebruik: $0 MAP_MET_SERVERBESTANDEN" >&2
    exit 2
fi

SOURCE_DIR=$1
NGINX_SITE=${OV_NGINX_SITE:-/etc/nginx/sites-available/openvertaling.nl}
INCLUDE_LINE='    include /etc/nginx/snippets/openvertaling-collaboration.conf;'

for tool in curl install nginx python3 systemctl useradd getent chown; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "Vereist programma ontbreekt: $tool" >&2
        exit 1
    }
done
python3 -c 'import cryptography'
MODULES=(collaboration_api.py collaboration_schema.py collaboration_errors.py correction_schema.py correction_scope.py correction_verse_scope.py
    review_content.py review_components.py component_reviews.py correction_files.py corrections.py correction_routes.py correction_cli.py)
for file in "${MODULES[@]}" openvertaling-collaboration.service openvertaling-collaboration.nginx openvertaling-collaboration-limits.nginx; do
    test -f "$SOURCE_DIR/$file" || {
        echo "Installatiebestand ontbreekt: $file" >&2
        exit 1
    }
done
test -f "$NGINX_SITE"

if ! getent passwd openvertaling >/dev/null; then
    useradd --system --user-group --home-dir /var/lib/openvertaling-collaboration --shell /usr/sbin/nologin openvertaling
fi
if systemctl cat openvertaling-collaboration.service >/dev/null 2>&1; then
    systemctl stop openvertaling-collaboration.service
fi
install -d -m 0755 /opt/openvertaling-collaboration
for file in "${MODULES[@]}"; do
    install -m 0644 "$SOURCE_DIR/$file" "/opt/openvertaling-collaboration/$file"
done
install -d -o openvertaling -g openvertaling -m 0700 /var/lib/openvertaling-collaboration
chown -R --no-dereference openvertaling:openvertaling /var/lib/openvertaling-collaboration
install -m 0644 "$SOURCE_DIR/openvertaling-collaboration.service" /etc/systemd/system/openvertaling-collaboration.service
install -m 0644 "$SOURCE_DIR/openvertaling-collaboration.nginx" /etc/nginx/snippets/openvertaling-collaboration.conf
install -m 0644 "$SOURCE_DIR/openvertaling-collaboration-limits.nginx" /etc/nginx/conf.d/openvertaling-collaboration-limits.conf

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
curl --fail --silent --show-error --retry 10 --retry-delay 1 --retry-connrefused \
    --retry-max-time 30 http://127.0.0.1:8787/api/collaboration/health >/dev/null

trap - ERR
unlink -- "$SITE_BACKUP"
echo "Collaboration API geïnstalleerd en gecontroleerd."
