#!/usr/bin/env bash
# Установка Ollama с поддержкой NVIDIA GPU внутри LXC-контейнера Proxmox.
# Запускать от root внутри контейнера (pct enter <id>).
# Перед запуском выполните GPU passthrough (см. README.md в этой папке).

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

log() { echo "==> $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Запускайте скрипт от root (внутри контейнера: pct enter <id>)." >&2
    exit 1
fi

log "Проверка наличия GPU"
if [ ! -e /dev/nvidiactl ]; then
    echo "Устройства NVIDIA (/dev/nvidiactl) не найдены." >&2
    echo "Настройте passthrough в /etc/pve/lxc/<id>.conf на хосте (см. README.md)." >&2
    exit 1
fi
nvidia-smi || echo "nvidia-smi пока недоступен (установите драйвер nvidia-utils)."

log "Установка системных пакетов"
apt-get update -y
apt-get install -y curl pciutils gpg

log "Установка Ollama"
curl -fsSL https://ollama.com/install.sh | sh

log "Настройка доступа в сеть (по умолчанию слушает все интерфейсы)"
systemctl enable ollama
systemctl start ollama

log "Загрузка моделей"
ollama pull gemma4:26b
ollama pull nomic-embed-text

log "Готово. Проверка:"
log "  nvidia-smi  (должна показывать GPU)"
log "  ollama list"
log "  curl http://<ip-контейнера>:11434/api/tags"
log ""
log "В контейнере Zelvera укажите OLLAMA_BASE_URL=http://<ip-контейнера-ollama>:11434"
