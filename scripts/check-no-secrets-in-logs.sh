#!/usr/bin/env bash
#
# Проверка, не попадают ли в логи чувствительные данные из .env:
#   хост PostgreSQL (POSTGRES_HOST), логин (POSTGRES_USER), пароль (POSTGRES_PASSWORD),
#   строка HTTPS_PROXY (в том числе user:password@прокси).
#
# По умолчанию скрипт ничего не изменяет, только печатает отчёт.
# Запуск (вручную):
#   chmod +x scripts/check-no-secrets-in-logs.sh
#   ./scripts/check-no-secrets-in-logs.sh
#   LOG_TAIL_LINES=20000 AI_EDITOR_ROOT=/path/to/AI_Editor ./scripts/check-no-secrets-in-logs.sh
#
set -uo pipefail

AI_EDITOR_ROOT="${AI_EDITOR_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_FILE="${AI_EDITOR_ROOT}/.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[!] Файл .env не найден: ${ENV_FILE}" >&2
  exit 2
fi

# Значение одной переменной из .env без вывода в отчёт
_kv() {
  local key="$1"
  grep -E "^[[:space:]]*${key}=" "${ENV_FILE}" 2>/dev/null | tail -n1 \
    | sed "s/^[^=]*=//; s/^[\"']//; s/[\"']\$//" | sed 's/[[:space:]]*$//'
}

PHOST="$(_kv POSTGRES_HOST)"
PUSER="$(_kv POSTGRES_USER)"
PPASS="$(_kv POSTGRES_PASSWORD)"
HTTPSPX="$(_kv HTTPS_PROXY)"

LEAK_FLAG=0

# label, needle (секрет), haystack (тестируемый текст). Секрет в stdout не печатается.
scan_text() {
  local label="$1"
  local needle="$2"
  local haystack="$3"

  if [[ -z "${needle}" ]]; then
    return 0
  fi
  # Очень короткие подстроки (например host=«db») дают море ложных срабатываний в журналах Docker.
  local -i nlen=${#needle}
  if (( nlen < 6 )); then
    echo "[игнор] Короткая подстрока (${nlen} симв.) для «${label}» — при необходимости проверьте журналы вручную."
    return 0
  fi

  if grep -Fq -- "${needle}" <<< "${haystack}"; then
    echo "[ПОДОЗРИТЕЛЬНО] В «${label}» найдена подстрока, совпадающая со значением из .env (само значение не выводится)."
    LEAK_FLAG=1
  fi
}

collect_streams() {
  if command -v docker >/dev/null 2>&1; then
    (cd "${AI_EDITOR_ROOT}" && docker compose logs --no-color --tail="${LOG_TAIL_LINES:-800}" app nginx db 2>/dev/null) \
      || true
    for c in ai-editor-app ai-editor-nginx ai-editor-db; do
      docker logs --tail "${LOG_TAIL_LINES:-800}" "${c}" 2>/dev/null || true
    done
  else
    echo "(docker недоступен — журналы контейнеров пропущены)"
  fi
}

LOG_BUFFER="$(collect_streams)"

scan_text "логи Docker (compose / docker logs: app, nginx, db)" "${PHOST:-}" "${LOG_BUFFER}"
scan_text "логи Docker" "${PUSER:-}" "${LOG_BUFFER}"
scan_text "логи Docker" "${PPASS:-}" "${LOG_BUFFER}"
scan_text "логи Docker" "${HTTPSPX:-}" "${LOG_BUFFER}"

while IFS= read -r -d '' logf; do
  buf="$(cat "${logf}" 2>/dev/null || true)"
  scan_text "файл ${logf}" "${PHOST:-}" "${buf}"
  scan_text "файл ${logf}" "${PUSER:-}" "${buf}"
  scan_text "файл ${logf}" "${PPASS:-}" "${buf}"
  scan_text "файл ${logf}" "${HTTPSPX:-}" "${buf}"
done < <(find "${AI_EDITOR_ROOT}" -maxdepth 3 -type f -name '*.log' -print0 2>/dev/null)

if [[ "${LEAK_FLAG}" -eq 0 ]]; then
  echo "Совпадений полной подстроки из POSTGRES_* / HTTPS_PROXY в хвосте логов и в *.log (если есть) не обнаружено."
  echo "Длинные значения: для POSTGRES_HOST/USER < 6 симв. см. сообщения «[игнор]». Увеличить охват: export LOG_TAIL_LINES=50000"
fi

exit 0
