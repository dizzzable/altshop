#!/bin/sh
set -eu

PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
ENV_FILE="${PROJECT_DIR}/.env"
PROD_COMPOSE_FILE="${PROJECT_DIR}/docker-compose.prod.yml"
PROD_OVERRIDE_FILE="${PROJECT_DIR}/docker-compose.prod.override.yml"
BOOTSTRAP_REF="${ALTSHOP_BOOTSTRAP_REF:-main}"
RAW_BASE_URL="${ALTSHOP_RAW_BASE_URL:-https://raw.githubusercontent.com/dizzzable/altshop/${BOOTSTRAP_REF}}"
CERT_DIR="${ALTSHOP_CERT_DIR:-/opt/altshop/nginx}"

log() {
    printf '%s\n' "$*"
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"
}

backup_file() {
    file_path="$1"
    if [ -f "$file_path" ]; then
        cp "$file_path" "${file_path}.bak.$(date +%Y%m%d_%H%M%S)"
    fi
}

ensure_env_key() {
    env_key="$1"
    env_value="$2"
    if grep -q "^${env_key}=" "$ENV_FILE" 2>/dev/null; then
        return 0
    fi
    printf '\n%s=%s\n' "$env_key" "$env_value" >> "$ENV_FILE"
}

inspect_mount() {
    container_name="$1"
    destination="$2"
    docker inspect -f '{{range .Mounts}}{{if eq .Destination "'"$destination"'"}}{{.Type}}|{{if .Name}}{{.Name}}{{end}}|{{.Source}}{{end}}{{end}}' "$container_name" 2>/dev/null || true
}

render_override_file() {
    has_override=0

    {
        printf 'services:\n'

        if [ -n "${DB_BIND_SOURCE:-}" ]; then
            has_override=1
            printf '  altshop-db:\n'
            printf '    volumes:\n'
            printf '      - %s:/var/lib/postgresql/data\n' "$DB_BIND_SOURCE"
        fi

        if [ -n "${REDIS_BIND_SOURCE:-}" ]; then
            has_override=1
            printf '  altshop-redis:\n'
            printf '    volumes:\n'
            printf '      - %s:/data\n' "$REDIS_BIND_SOURCE"
        fi
    } > "$PROD_OVERRIDE_FILE"

    if [ "$has_override" -eq 0 ]; then
        rm -f "$PROD_OVERRIDE_FILE"
    fi
}

compose_up() {
    if [ -f "$PROD_OVERRIDE_FILE" ]; then
        docker compose -f "$PROD_COMPOSE_FILE" -f "$PROD_OVERRIDE_FILE" "$@"
    else
        docker compose -f "$PROD_COMPOSE_FILE" "$@"
    fi
}

require_command curl
require_command docker

[ -f "$ENV_FILE" ] || fail "missing .env in ${PROJECT_DIR}; place your current production .env there first"

cd "$PROJECT_DIR"

log "Backing up current files"
backup_file "$ENV_FILE"
backup_file "$PROD_COMPOSE_FILE"
backup_file "$PROD_OVERRIDE_FILE"

log "Ensuring required directories exist"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/assets" "$CERT_DIR"

log "Downloading docker-compose.prod.yml from ${BOOTSTRAP_REF}"
curl -fsSL "${RAW_BASE_URL}/docker-compose.prod.yml" -o "$PROD_COMPOSE_FILE"

log "Detecting existing data mounts"
DB_MOUNT="$(inspect_mount altshop-db /var/lib/postgresql/data)"
REDIS_MOUNT="$(inspect_mount altshop-redis /data)"

DB_BIND_SOURCE=""
REDIS_BIND_SOURCE=""

if [ -n "$DB_MOUNT" ]; then
    DB_MOUNT_TYPE=$(printf '%s' "$DB_MOUNT" | cut -d'|' -f1)
    DB_MOUNT_NAME=$(printf '%s' "$DB_MOUNT" | cut -d'|' -f2)
    DB_MOUNT_SOURCE=$(printf '%s' "$DB_MOUNT" | cut -d'|' -f3-)

    if [ "$DB_MOUNT_TYPE" = "volume" ] && [ -n "$DB_MOUNT_NAME" ]; then
        ensure_env_key "ALTSHOP_DB_VOLUME_NAME" "$DB_MOUNT_NAME"
    elif [ "$DB_MOUNT_TYPE" = "bind" ] && [ -n "$DB_MOUNT_SOURCE" ]; then
        DB_BIND_SOURCE="$DB_MOUNT_SOURCE"
    fi
fi

if [ -n "$REDIS_MOUNT" ]; then
    REDIS_MOUNT_TYPE=$(printf '%s' "$REDIS_MOUNT" | cut -d'|' -f1)
    REDIS_MOUNT_NAME=$(printf '%s' "$REDIS_MOUNT" | cut -d'|' -f2)
    REDIS_MOUNT_SOURCE=$(printf '%s' "$REDIS_MOUNT" | cut -d'|' -f3-)

    if [ "$REDIS_MOUNT_TYPE" = "volume" ] && [ -n "$REDIS_MOUNT_NAME" ]; then
        ensure_env_key "ALTSHOP_REDIS_VOLUME_NAME" "$REDIS_MOUNT_NAME"
    elif [ "$REDIS_MOUNT_TYPE" = "bind" ] && [ -n "$REDIS_MOUNT_SOURCE" ]; then
        REDIS_BIND_SOURCE="$REDIS_MOUNT_SOURCE"
    fi
fi

render_override_file

ensure_env_key "ALTSHOP_IMAGE_TAG" "${ALTSHOP_IMAGE_TAG:-latest}"
ensure_env_key "ALTSHOP_NGINX_IMAGE_TAG" "${ALTSHOP_NGINX_IMAGE_TAG:-latest}"
ensure_env_key "NGINX_SSL_FULLCHAIN_PATH" "${NGINX_SSL_FULLCHAIN_PATH:-${CERT_DIR}/remnabot_fullchain.pem}"
ensure_env_key "NGINX_SSL_PRIVKEY_PATH" "${NGINX_SSL_PRIVKEY_PATH:-${CERT_DIR}/remnabot_privkey.key}"

log "Stopping legacy containers if they exist"
docker rm -f altshop altshop-nginx altshop-taskiq-worker altshop-taskiq-scheduler altshop-db altshop-redis altshop-webapp-build >/dev/null 2>&1 || true

log "Pulling GHCR images"
compose_up pull

log "Starting production stack"
compose_up up -d

log "Bootstrap complete"
log "Next updates:"
log "  docker compose -f docker-compose.prod.yml pull"
if [ -f "$PROD_OVERRIDE_FILE" ]; then
    log "  docker compose -f docker-compose.prod.yml -f docker-compose.prod.override.yml up -d"
else
    log "  docker compose -f docker-compose.prod.yml up -d"
fi
