#!/usr/bin/env bash
# Обновление Zelvera в LXC-контейнере / VM Proxmox.
# Запускать от root внутри контейнера: bash /opt/zelvera/deploy/proxmox/update-zelvera.sh

set -euo pipefail

ZELVERA_HOME="${ZELVERA_HOME:-/opt/zelvera}"

log() { echo "==> $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Запускайте скрипт от root." >&2
    exit 1
fi

cd "${ZELVERA_HOME}"

log "Загрузка новых изменений из GitHub"
git pull

log "Обновление зависимостей"
./venv/bin/pip install -r backend/requirements.txt

if [ "${ZELVERA_VOICE:-0}" = "1" ]; then
    log "Установка голосовых зависимостей Telegram-бота (faster-whisper, edge-tts)"
    ./venv/bin/pip install -r backend/requirements-voice.txt
fi

log "Перезапуск сервиса"
systemctl restart zelvera

log "Готово. Текущая версия:"
git log --oneline -1
systemctl status zelvera --no-pager | head -3
