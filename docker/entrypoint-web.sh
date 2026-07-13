#!/bin/sh
set -e

MEDIA_ROOT="${MEDIA_ROOT:-/app/media}"
APP_USER="${APP_USER:-django}"
APP_UID="${APP_UID:-1000}"

# Named Docker volumes are often root-owned on first use; the app runs as non-root.
mkdir -p "${MEDIA_ROOT}/ticket_pending" "${MEDIA_ROOT}/kb_community" "${MEDIA_ROOT}/profiles"
if [ "$(id -u)" = "0" ]; then
  chown -R "${APP_UID}:${APP_UID}" "${MEDIA_ROOT}" 2>/dev/null || chown -R "${APP_USER}:${APP_USER}" "${MEDIA_ROOT}"
  exec gosu "${APP_USER}" "$@"
fi

exec "$@"
