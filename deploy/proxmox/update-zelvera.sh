#!/usr/bin/env bash
# Обновление Zelvera в LXC-контейнере / VM Proxmox.
# Запускать от root внутри контейнера:
#   bash /opt/zelvera/deploy/proxmox/update-zelvera.sh
# Если установка была без Git (старый install-zelvera.sh):
#   REPO_URL=https://github.com/kent911/zelvera.git bash /opt/zelvera/deploy/proxmox/update-zelvera.sh

set -euo pipefail

ZELVERA_HOME="${ZELVERA_HOME:-/opt/zelvera}"
ZELVERA_USER="${ZELVERA_USER:-zelvera}"
REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-}"
UNIT_FILE="/etc/systemd/system/zelvera.service"

log() { echo "==> $*"; }
die() { echo "$*" >&2; exit 1; }

read_unit_field() {
    local file="$1" key="$2"
    [ -f "${file}" ] || return 0
    sed -n "s/^${key}=//p" "${file}" | head -1
}

read_unit_port() {
    local file="$1"
    [ -f "${file}" ] || return 0
    sed -n 's/.*--port \([0-9][0-9]*\).*/\1/p' "${file}" | head -1
}

read_unit_env() {
    local file="$1" key="$2"
    [ -f "${file}" ] || return 0
    sed -n "s/^Environment=${key}=//p" "${file}" | head -1
}

if [ "$(id -u)" -ne 0 ]; then
    die "Запускайте скрипт от root."
fi

[ -d "${ZELVERA_HOME}" ] || die "Каталог ${ZELVERA_HOME} не найден."
cd "${ZELVERA_HOME}"
git config --global --add safe.directory "${ZELVERA_HOME}" >/dev/null 2>&1 || true

if [ ! -d "${ZELVERA_HOME}/.git" ]; then
    if [ -z "${REPO_URL}" ]; then
        die "Установка без Git. Укажите репозиторий, например:
  REPO_URL=https://github.com/kent911/zelvera.git bash ${ZELVERA_HOME}/deploy/proxmox/update-zelvera.sh"
    fi
    log "Восстановление Git из ${REPO_URL}"
    tmp="$(mktemp -d)"
    git clone --depth 1 "${REPO_URL}" "${tmp}"
    rsync -a "${tmp}/.git/" "${ZELVERA_HOME}/.git/"
    rm -rf "${tmp}"
fi

if [ -z "${BRANCH}" ]; then
    BRANCH="$(git remote show origin 2>/dev/null | sed -n 's/.*HEAD branch: //p')"
    [ -n "${BRANCH}" ] || BRANCH="master"
fi

log "Загрузка изменений из GitHub (${BRANCH})"
git remote get-url origin >/dev/null 2>&1 || {
    [ -n "${REPO_URL}" ] || die "Нет remote origin. Укажите REPO_URL=..."
    git remote add origin "${REPO_URL}"
}
log "Remote: $(git remote get-url origin)"
BEFORE="$(git rev-parse --short HEAD 2>/dev/null || echo none)"
log "Сейчас: $(git log --oneline -1 2>/dev/null || echo нет коммита)"

if ! git fetch --depth 1 origin "${BRANCH}"; then
    die "Не удалось скачать обновления (приватный репозиторий?). Проверьте:
  git -C ${ZELVERA_HOME} remote -v
  git -C ${ZELVERA_HOME} fetch origin ${BRANCH}"
fi

if ! git diff --quiet -- run.py 2>/dev/null; then
    log "Сброс локальной правки run.py"
    git checkout -- run.py
fi

# FETCH_HEAD надёжнее origin/${BRANCH}: shallow fetch часто не двигает remote-tracking ref.
git reset --hard FETCH_HEAD
AFTER="$(git rev-parse --short HEAD)"
if [ "${BEFORE}" = "${AFTER}" ]; then
    log "Уже последняя версия: $(git log --oneline -1)"
else
    log "Обновлено ${BEFORE} -> $(git log --oneline -1)"
fi

log "Обновление зависимостей"
./venv/bin/pip install -r backend/requirements.txt

if [ "${ZELVERA_VOICE:-0}" = "1" ]; then
    log "Установка голосовых зависимостей Telegram-бота"
    ./venv/bin/pip install -r backend/requirements-voice.txt
fi

KEEP_USER="$(read_unit_field "${UNIT_FILE}" User)"
KEEP_GROUP="$(read_unit_field "${UNIT_FILE}" Group)"
KEEP_PORT="${ZELVERA_PORT:-$(read_unit_port "${UNIT_FILE}")}"
KEEP_OLLAMA="$(read_unit_env "${UNIT_FILE}" OLLAMA_BASE_URL)"

if [ -n "${KEEP_USER}" ]; then
    ZELVERA_USER="${KEEP_USER}"
fi
if [ -z "${KEEP_GROUP}" ]; then
    KEEP_GROUP="${ZELVERA_USER}"
fi

if ! id -u "${ZELVERA_USER}" >/dev/null 2>&1; then
    log "Создание пользователя ${ZELVERA_USER}"
    useradd --system --home-dir "${ZELVERA_HOME}" --no-create-home "${ZELVERA_USER}"
fi

log "Права ${ZELVERA_USER} на код и данные"
chown -R "${ZELVERA_USER}":"${ZELVERA_USER}" \
    "${ZELVERA_HOME}/backend" \
    "${ZELVERA_HOME}/frontend" \
    "${ZELVERA_HOME}/deploy" \
    "${ZELVERA_HOME}/venv" \
    "${ZELVERA_HOME}/data" \
    2>/dev/null || true

log "Перезапуск сервиса"
cp "${ZELVERA_HOME}/deploy/proxmox/zelvera.service" "${UNIT_FILE}"
chmod 644 "${UNIT_FILE}"
sed -i "s/^User=.*/User=${ZELVERA_USER}/" "${UNIT_FILE}"
sed -i "s/^Group=.*/Group=${KEEP_GROUP}/" "${UNIT_FILE}"
if [ -n "${KEEP_PORT}" ]; then
    log "Порт из текущей установки: ${KEEP_PORT}"
    sed -i "s/--port [0-9][0-9]*/--port ${KEEP_PORT}/" "${UNIT_FILE}"
fi
if [ -n "${KEEP_OLLAMA}" ]; then
    log "OLLAMA_BASE_URL из текущей установки: ${KEEP_OLLAMA}"
    sed -i "s|^Environment=OLLAMA_BASE_URL=.*|Environment=OLLAMA_BASE_URL=${KEEP_OLLAMA}|" "${UNIT_FILE}"
fi
systemctl daemon-reload
systemctl reset-failed zelvera || true
systemctl restart zelvera

log "Готово. Текущая версия:"
git log --oneline -1
systemctl status zelvera --no-pager | head -3
