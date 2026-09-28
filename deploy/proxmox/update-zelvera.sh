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

log() { echo "==> $*"; }
die() { echo "$*" >&2; exit 1; }

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
git fetch --depth 1 origin "${BRANCH}"

if ! git diff --quiet -- run.py 2>/dev/null; then
    log "Сброс локальной правки run.py"
    git checkout -- run.py
fi

git reset --hard "origin/${BRANCH}"

log "Обновление зависимостей"
./venv/bin/pip install -r backend/requirements.txt

if [ "${ZELVERA_VOICE:-0}" = "1" ]; then
    log "Установка голосовых зависимостей Telegram-бота"
    ./venv/bin/pip install -r backend/requirements-voice.txt
fi

if id -u "${ZELVERA_USER}" >/dev/null 2>&1; then
    chown -R "${ZELVERA_USER}":"${ZELVERA_USER}" \
        "${ZELVERA_HOME}/backend" \
        "${ZELVERA_HOME}/frontend" \
        "${ZELVERA_HOME}/deploy" \
        "${ZELVERA_HOME}/venv" \
        2>/dev/null || true
fi

log "Перезапуск сервиса"
systemctl daemon-reload
cp "${ZELVERA_HOME}/deploy/proxmox/zelvera.service" /etc/systemd/system/zelvera.service
chmod 644 /etc/systemd/system/zelvera.service
systemctl daemon-reload
systemctl restart zelvera

log "Готово. Текущая версия:"
git log --oneline -1
systemctl status zelvera --no-pager | head -3
