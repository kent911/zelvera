#!/usr/bin/env bash
# Установка Zelvera в LXC-контейнер Proxmox.
# Запускать от root внутри контейнера (pct enter <id>).

set -euo pipefail

ZELVERA_USER="${ZELVERA_USER:-zelvera}"
ZELVERA_HOME="${ZELVERA_HOME:-/opt/zelvera}"
ZELVERA_DATA="${ZELVERA_DATA:-${ZELVERA_HOME}/data}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-gemma4:26b}"
OLLAMA_VISION_MODEL="${OLLAMA_VISION_MODEL:-gemma4:26b}"
OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
REPO_URL="${REPO_URL:-}"

log() { echo "==> $*"; }

if [ "$(id -u)" -ne 0 ]; then
    echo "Запускайте скрипт от root (внутри контейнера: pct enter <id>)." >&2
    exit 1
fi

log "Обновление системы"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

log "Установка зависимостей"
apt-get install -y python3 python3-venv python3-pip git curl unzip

log "Создание пользователя ${ZELVERA_USER}"
if ! id -u "${ZELVERA_USER}" >/dev/null 2>&1; then
    useradd --system --create-home --home-dir "${ZELVERA_HOME}" "${ZELVERA_USER}"
fi
mkdir -p "${ZELVERA_HOME}" "${ZELVERA_DATA}"
chown -R "${ZELVERA_USER}":"${ZELVERA_USER}" "${ZELVERA_HOME}"

log "Получение исходного кода"
if [ -z "${REPO_URL}" ]; then
    echo "Укажите REPO_URL (адрес вашего git-репозитория с исходниками Zelvera)."
    echo "Пример: REPO_URL=https://github.com/kent911/zelvera.git ./install-zelvera.sh"
    echo "Либо вручную скопируйте файлы в ${ZELVERA_HOME} и повторите."
    exit 1
fi
if [ ! -d "${ZELVERA_HOME}/.git" ]; then
    if [ -f "${ZELVERA_HOME}/backend/app/main.py" ]; then
        log "Исходники есть, но без Git — клонирую поверх, data не трогаю"
        tmp="$(mktemp -d)"
        git clone --depth 1 "${REPO_URL}" "${tmp}"
        rsync -a --exclude='data' --exclude='venv' --exclude='backend/.env' "${tmp}/" "${ZELVERA_HOME}/"
        rm -rf "${tmp}"
    else
        git clone --depth 1 "${REPO_URL}" "${ZELVERA_HOME}/src"
        rsync -a --exclude='data' "${ZELVERA_HOME}/src/" "${ZELVERA_HOME}/"
        rm -rf "${ZELVERA_HOME}/src"
    fi
    git -C "${ZELVERA_HOME}" config --global --add safe.directory "${ZELVERA_HOME}" >/dev/null 2>&1 || true
else
    log "Исходники уже присутствуют, обновление пропущено"
fi

log "Создание виртуального окружения"
python3 -m venv "${ZELVERA_HOME}/venv"
"${ZELVERA_HOME}/venv/bin/pip" install --upgrade pip
"${ZELVERA_HOME}/venv/bin/pip" install -r "${ZELVERA_HOME}/backend/requirements.txt"

log "Настройка .env"
cat > "${ZELVERA_HOME}/backend/.env" <<EOF
LLM_BACKEND=ollama
OLLAMA_BASE_URL=${OLLAMA_URL}
OLLAMA_MODEL=${OLLAMA_MODEL}
OLLAMA_VISION_MODEL=${OLLAMA_VISION_MODEL}
OLLAMA_EMBED_MODEL=${OLLAMA_EMBED_MODEL}
ZELVERA_DATA_DIR=${ZELVERA_DATA}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
TELEGRAM_ALLOWED_CHAT_IDS=${TELEGRAM_ALLOWED_CHAT_IDS:-}
TELEGRAM_PROXY=${TELEGRAM_PROXY:-}
GITHUB_PROXY=${GITHUB_PROXY:-}
EOF
chown "${ZELVERA_USER}":"${ZELVERA_USER}" "${ZELVERA_HOME}/backend/.env"

log "Установка systemd-сервиса"
cp "${ZELVERA_HOME}/deploy/proxmox/zelvera.service" /etc/systemd/system/zelvera.service
chmod 644 /etc/systemd/system/zelvera.service
systemctl daemon-reload
systemctl enable zelvera.service

log "Готово. Дальнейшие шаги:"
log "  1) Убедитесь, что Ollama доступна по адресу: ${OLLAMA_URL}"
log "  2) Загрузите модели: ollama pull ${OLLAMA_MODEL}"
log "     ollama pull ${OLLAMA_EMBED_MODEL}"
log "  3) Запуск: systemctl start zelvera"
log "  4) Веб-интерфейс: http://<ip-контейнера>:8000"
