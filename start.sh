#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

run_as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "Need root privileges to install Docker. Re-run as root or install sudo."
  fi
}

docker_ok() {
  docker info >/dev/null 2>&1 || { command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; }
}

compose() {
  if ! command -v docker-compose >/dev/null 2>&1; then
    die "docker-compose not found. Re-run ./start.sh on Ubuntu to install it, or install docker-compose manually."
  fi
  if docker info >/dev/null 2>&1; then
    docker-compose "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    sudo docker-compose "$@"
  else
    die "Cannot talk to the Docker daemon. Start Docker or add your user to the docker group, then re-login."
  fi
}

detect_primary_ip() {
  local ip
  ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
  if [[ -n "${ip:-}" ]]; then
    printf '%s\n' "$ip"
    return
  fi
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
  if [[ -n "${ip:-}" ]]; then
    printf '%s\n' "$ip"
    return
  fi
  printf 'localhost\n'
}

# From https://github.com/cybrtps/Docker-offline-install
DOCKER_OFFLINE_REPO="https://github.com/cybrtps/Docker-offline-install.git"
DOCKER_OFFLINE_BUNDLE="docker-offline-bundle-bookworm.tar.gz"
DOCKER_OFFLINE_SHA256="bf3e6504e9f3d4f8a852f0a009d8e37676ae8475b9d6c770105681f64254584e"

install_docker_offline() {
  need_cmd git
  need_cmd sha256sum

  local workdir
  workdir="$(mktemp -d /tmp/docker-offline-install.XXXXXX)"
  # shellcheck disable=SC2064
  trap "rm -rf '$workdir'" RETURN

  log "Installing Docker + docker-compose via cybrtps/Docker-offline-install..."
  log "Cloning ${DOCKER_OFFLINE_REPO}"
  git clone --depth 1 "$DOCKER_OFFLINE_REPO" "$workdir/docker-offline-install"
  cd "$workdir/docker-offline-install"

  [[ -f "$DOCKER_OFFLINE_BUNDLE" ]] || die "Missing $DOCKER_OFFLINE_BUNDLE in offline install repo."

  log "Verifying bundle integrity (sha256)..."
  local actual
  actual="$(sha256sum "$DOCKER_OFFLINE_BUNDLE" | awk '{print $1}')"
  if [[ "$actual" != "$DOCKER_OFFLINE_SHA256" ]]; then
    die "Bundle hash mismatch.
Expected: ${DOCKER_OFFLINE_SHA256}
Actual:   ${actual}
Refusing to install."
  fi
  log "Bundle hash OK."

  chmod +x run-docker-install.sh
  # install.sh inside the bundle typically needs root for dpkg/systemctl
  run_as_root ./run-docker-install.sh

  cd "$ROOT_DIR"

  if [[ "$(id -u)" -ne 0 ]] && command -v usermod >/dev/null 2>&1; then
    run_as_root usermod -aG docker "$USER" || true
    warn "Added '$USER' to the docker group. If docker commands fail without sudo, log out and back in."
  fi

  command -v docker >/dev/null 2>&1 || die "Docker install finished but 'docker' was not found on PATH."
  command -v docker-compose >/dev/null 2>&1 || die "Docker install finished but 'docker-compose' was not found on PATH."
  log "Docker offline install complete: $(docker --version 2>/dev/null || true)"
  log "Compose: $(docker-compose version 2>/dev/null || true)"
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1 && docker_ok; then
    return
  fi

  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    # Bundle targets Debian 12-based systems (Ubuntu 22.04+)
    case "${ID:-}" in
      ubuntu|debian|kali|parrot)
        install_docker_offline
        return
        ;;
    esac
  fi

  die "Docker / docker-compose is not installed.
On Ubuntu/Debian this script installs them via:
  ${DOCKER_OFFLINE_REPO}
Otherwise install Docker Engine and docker-compose manually, then re-run ./start.sh."
}

random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 16
  else
    # Fallback: use /dev/urandom
    tr -dc 'a-f0-9' </dev/urandom | head -c 32
  fi
}

set_env_value() {
  local key="$1"
  local value="$2"
  local file="$3"
  if grep -qE "^${key}=" "$file"; then
    # Escape sed replacement specials in value: \ & |
    local escaped
    escaped="$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')"
    sed -i.bak -E "s|^${key}=.*|${key}=${escaped}|" "$file"
    rm -f "${file}.bak"
  else
    printf '%s=%s\n' "$key" "$value" >>"$file"
  fi
}

bootstrap_env() {
  if [[ ! -f .env ]]; then
    log "Creating .env from .env.example..."
    cp .env.example .env
  fi

  # shellcheck disable=SC1091
  set -a
  source .env
  set +a

  if [[ -z "${POSTGRES_PASSWORD:-}" || "${POSTGRES_PASSWORD}" == "CHANGE_ME_STRONG_PASSWORD" ]]; then
    local db_pass
    db_pass="$(random_secret)"
    set_env_value POSTGRES_PASSWORD "$db_pass" .env
    log "Generated POSTGRES_PASSWORD"
  fi

  if [[ -z "${ODOO_ADMIN_PASSWORD:-}" || "${ODOO_ADMIN_PASSWORD}" == "CHANGE_ME_ADMIN_PASSWORD" ]]; then
    local admin_pass
    admin_pass="$(random_secret)"
    set_env_value ODOO_ADMIN_PASSWORD "$admin_pass" .env
    log "Generated ODOO_ADMIN_PASSWORD"
  fi

  # Reload after possible updates
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
}

render_odoo_conf() {
  local template="odoo/config/odoo.conf.template"
  local target="odoo/config/odoo.conf"
  [[ -f "$template" ]] || die "Missing $template"

  local user="${POSTGRES_USER:-odoo}"
  local db_pass="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD missing}"
  local admin_pass="${ODOO_ADMIN_PASSWORD:?ODOO_ADMIN_PASSWORD missing}"

  # Use Python for safe substitution (passwords may contain sed metacharacters)
  POSTGRES_USER="$user" \
  POSTGRES_PASSWORD="$db_pass" \
  ODOO_ADMIN_PASSWORD="$admin_pass" \
  python3 - "$template" "$target" <<'PY'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src, encoding="utf-8").read()
replacements = {
    "__POSTGRES_USER__": os.environ["POSTGRES_USER"],
    "__POSTGRES_PASSWORD__": os.environ["POSTGRES_PASSWORD"],
    "__ODOO_ADMIN_PASSWORD__": os.environ["ODOO_ADMIN_PASSWORD"],
}
for k, v in replacements.items():
    text = text.replace(k, v)
open(dst, "w", encoding="utf-8").write(text)
PY

  log "Rendered $target"
}

main() {
  need_cmd python3
  ensure_docker
  bootstrap_env
  render_odoo_conf

  mkdir -p addons certbot/www certbot/conf nginx/conf.d odoo/config

  log "Pulling images..."
  compose pull

  log "Starting stack..."
  compose up -d

  local ip http_port url
  ip="$(detect_primary_ip)"
  http_port="${HTTP_PORT:-80}"
  if [[ "$http_port" == "80" ]]; then
    url="http://${ip}"
  else
    url="http://${ip}:${http_port}"
  fi

  cat <<EOF

Odoo 19 stack is up.

  URL:              ${url}
  Master password:  ${ODOO_ADMIN_PASSWORD}
  (also stored in .env as ODOO_ADMIN_PASSWORD)

Open the URL, create a database, and start using Odoo.
Postgres and Odoo ports are internal-only; nginx listens on ${http_port}.

Optional HTTPS later:
  1. Set DOMAIN and EMAIL in .env
  2. Point DNS A record to this server
  3. Run: ./scripts/enable-https.sh

Useful commands:
  docker-compose logs -f
  docker-compose ps
  docker-compose down

EOF
}

main "$@"
