#!/usr/bin/env bash
# Optional: issue a Let's Encrypt certificate and switch nginx to HTTPS.
# Prerequisites: stack already running via ./start.sh, DOMAIN + EMAIL set in .env,
# and DNS for DOMAIN pointing to this server.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

compose() {
  if ! command -v docker-compose >/dev/null 2>&1; then
    die "docker-compose not found. Run ./start.sh first."
  fi
  if docker info >/dev/null 2>&1; then
    docker-compose "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    sudo docker-compose "$@"
  else
    die "Cannot talk to the Docker daemon."
  fi
}

[[ -f .env ]] || die "Missing .env — run ./start.sh first."

set -a
# shellcheck disable=SC1091
source .env
set +a

DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-}"

[[ -n "$DOMAIN" ]] || die "Set DOMAIN in .env (e.g. odoo.example.com)."
[[ -n "$EMAIL" ]] || die "Set EMAIL in .env (used for Let's Encrypt notices)."

HTTP_CONF="nginx/conf.d/odoo.conf"
HTTP_BAK="nginx/conf.d/odoo.conf.http.bak"
HTTPS_TEMPLATE="nginx/conf.d/odoo-https.conf.template"

[[ -f "$HTTPS_TEMPLATE" ]] || die "Missing $HTTPS_TEMPLATE"
[[ -f "$HTTP_CONF" ]] || die "Missing $HTTP_CONF — run ./start.sh first."

log "Ensuring HTTP stack is up (needed for ACME challenge)..."
compose up -d db odoo nginx

log "Requesting certificate for ${DOMAIN}..."
compose --profile https run --rm --entrypoint certbot certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email "$EMAIL" \
  --agree-tos \
  --no-eff-email \
  --non-interactive \
  -d "$DOMAIN"

if [[ ! -f "$HTTP_BAK" ]]; then
  cp "$HTTP_CONF" "$HTTP_BAK"
  log "Backed up HTTP nginx config to $HTTP_BAK"
fi

log "Installing HTTPS nginx config..."
DOMAIN="$DOMAIN" python3 - "$HTTPS_TEMPLATE" "$HTTP_CONF" <<'PY'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read().replace("__DOMAIN__", os.environ["DOMAIN"])
open(dst, "w", encoding="utf-8").write(text)
PY

log "Starting certbot renewer and reloading nginx..."
compose --profile https up -d
compose exec nginx nginx -t
compose exec nginx nginx -s reload

cat <<EOF

HTTPS enabled for https://${DOMAIN}

Certbot renewer runs under the Compose profile "https".
To start the full stack later:

  docker-compose --profile https up -d

To revert to HTTP-only:

  cp ${HTTP_BAK} ${HTTP_CONF}
  docker-compose --profile https down
  docker-compose up -d
  docker-compose exec nginx nginx -s reload

EOF
