#!/usr/bin/env bash
# Создаёт/обновляет учётку для docker login в локальном реестре (файл auth/htpasswd).
# Пароль храните согласованно с .env/приложением — сам registry не использует SQLite,
# но вы можете намеренно взять тот же пароль, что и у БД в приложении.
set -euo pipefail

REGISTRY_DIR="$(cd "$(dirname "$0")" && pwd)"
HTPASSWD="${REGISTRY_DIR}/auth/htpasswd"
HTTPD_IMAGE="httpd:2"

usage() {
  echo "Использование: $0 <логин> <пароль>" >&2
  echo "Пример: $0 admin 'ВашСекрет123'" >&2
  exit 1
}

[[ $# -eq 2 ]] || usage

if ! command -v docker &>/dev/null; then
  echo "error: требуется docker в PATH" >&2
  exit 1
fi

LOG="$1"
PASS="$2"

mkdir -p "${REGISTRY_DIR}/auth"

# htpasswd: -c только при первом создании файла; -Bb — добавить или обновить пользователя
if [[ ! -f "${HTPASSWD}" ]] || [[ ! -s "${HTPASSWD}" ]]; then
  docker run --rm --pull=missing -v "${REGISTRY_DIR}/auth:/auth" --entrypoint htpasswd \
    "${HTTPD_IMAGE}" -Bbc "/auth/htpasswd" "${LOG}" "${PASS}"
else
  docker run --rm --pull=missing -v "${REGISTRY_DIR}/auth:/auth" --entrypoint htpasswd \
    "${HTTPD_IMAGE}" -Bb "/auth/htpasswd" "${LOG}" "${PASS}"
fi

chmod 600 "${HTPASSWD}" 2>/dev/null || true

echo "ok: пользователь «${LOG}» записан в ${HTPASSWD}"
echo "   Перезапустите контейнер registry, если меняли пользователя/пароль: docker compose up -d registry"
echo "   Синхронизируйте REGISTRY_USER в .env (рядом с docker-compose.yml), если задали новый логин."
