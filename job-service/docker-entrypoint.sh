#!/bin/sh
set -eu

if [ -n "${SERVICE_KEY:-}" ]; then
    export JOB_SERVICE_ADMIN_API_KEY="${SERVICE_KEY}"
fi

if [ "${JOB_SERVICE_INSTALL_DEPS_ON_STARTUP:-true}" = "true" ]; then
    poetry install --only main --no-root --sync --no-interaction --no-ansi
fi

exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
