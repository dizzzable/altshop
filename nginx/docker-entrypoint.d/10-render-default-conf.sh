#!/bin/sh
set -eu

TEMPLATE_PATH="/etc/nginx/altshop/default.conf.template"
TARGET_PATH="/etc/nginx/conf.d/default.conf"

if [ -n "${APP_DOMAIN:-}" ]; then
    sed "s/server_name you.domain.com;/server_name ${APP_DOMAIN};/" "$TEMPLATE_PATH" > "$TARGET_PATH"
else
    cp "$TEMPLATE_PATH" "$TARGET_PATH"
fi
