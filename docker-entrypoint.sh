#!/bin/sh
set -e

export ASSETS_CONTAINER_PATH="/opt/altshop/assets"
export ASSETS_DEFAULT_PATH="/opt/altshop/assets.default"

UVICORN_RELOAD_ARGS=""
if ! python -m src.core.utils.assets_sync; then
    echo "Asset initialization failed! Exiting container..."
    exit 1
fi

echo "Creating logs directory"
mkdir -p /opt/altshop/logs

echo "Migrating database"

if ! alembic -c src/infrastructure/database/alembic.ini upgrade head; then
    echo "Database migration failed! Exiting container..."
    exit 1
fi

echo "Migrations deployed successfully"


if [ "$UVICORN_RELOAD_ENABLED" = "true" ]; then
    echo "Uvicorn will run with reload enabled"
    UVICORN_RELOAD_ARGS="--reload --reload-dir /opt/altshop/src --reload-dir /opt/altshop/assets --reload-include *.ftl"
else
    echo "Uvicorn will run without reload"
fi

FORWARDED_ALLOW_IPS="${APP_TRUSTED_PROXY_IPS:-127.0.0.1,::1}"

exec uvicorn src.__main__:application --host "${APP_HOST}" --port "${APP_PORT}" --factory --use-colors --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS}" ${UVICORN_RELOAD_ARGS}
