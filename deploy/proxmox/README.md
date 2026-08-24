# Развёртывание Zelvera в Proxmox (мини-ПК)

Автономная среда: Zelvera работает круглосуточно в LXC-контейнере, Ollama
— в отдельном контейнере с NVIDIA GPU. Всё остаётся локальным, интернет
не требуется (кроме момента загрузки моделей и пакетов).

## Схема

```
Proxmox (мини-ПК)
├── LXC "ollama"   — Ollama + NVIDIA GPU (passthrough)
│   └── http://<ip-ollama>:11434
├── LXC "zelvera"  — приложение (FastAPI + uvicorn, systemd, автозапуск)
│   ├── http://<ip-zelvera>:8001  (веб-интерфейс)
│   └── данные в /opt/zelvera/data (на постоянном storage)
└── (опционально) Caddy — доступ по имени, например http://zelvera.lan
```

## Шаг 1. Создание контейнеров

На хосте Proxmox (pve1). Для каждого контейнера:

```bash
pveam update
pct create 100 local:vztmpl/ubuntu-24.04-standard_24.04-1_amd64.tar.zst \
  --hostname zelvera \
  --storage local-lvm \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1 \
  --features nesting=1 \
  --cores 4 --memory 4096 --swap 512
```

Аналогично создайте контейнер `ollama` (id 101) с теми же параметрами.
Узнать IP контейнеров:

```bash
pct enter 100 -- ip -4 addr show eth0
```

## Шаг 2. GPU passthrough для контейнера Ollama

На хосте установите драйверы NVIDIA:

```bash
apt-get update && apt-get install -y pve-headers nvidia-driver
reboot
```

После перезагрузки отредактируйте конфиг контейнера Ollama на хосте:

```bash
nano /etc/pve/lxc/101.conf
```

Добавьте (id 101 — номер контейнера Ollama):

```
lxc.cgroup2.devices.allow: c 195:0 rwm
lxc.cgroup2.devices.allow: c 195:255 rwm
lxc.cgroup2.devices.allow: c 10:144 rwm
lxc.mount.entry: /dev/nvidia0 dev/nvidia0 none bind,optional,create=file
lxc.mount.entry: /dev/nvidiactl dev/nvidiactl none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-modeset dev/nvidia-modeset none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm dev/nvidia-uvm none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm-tools dev/nvidia-uvm-tools none bind,optional,create=file
```

Перезапустите контейнер: `pct reboot 101`.

> Если видеочип не NVIDIA (AMD/Intel), вместо этого пробросьте `/dev/dri`:
> `lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir`

## Шаг 3. Установка Ollama в контейнер

Скопируйте скрипт в контейнер с хоста:

```bash
pct push 101 ./deploy/proxmox/install-ollama-gpu.sh /root/install-ollama-gpu.sh
pct enter 101 -- bash /root/install-ollama-gpu.sh
```

Скрипт установит Ollama, загрузит модели и проверит GPU через `nvidia-smi`.

Проверка с хоста:

```bash
curl http://<ip-ollama>:11434/api/tags
```

## Шаг 4. Установка Zelvera

Скопируйте проект и скрипт установки:

```bash
pct push 100 ./deploy/proxmox/install-zelvera.sh /root/install-zelvera.sh
pct push 100 ./deploy/proxmox/zelvera.service /root/zelvera.service
```

Перенесите исходники в контейнер (через SMB-шару, scp на хост и `pct push`,
или склонируйте прямо из git). Укажите адрес Ollama:

```bash
pct enter 100 -- bash /root/install-zelvera.sh \
  REPO_URL=https://github.com/<ваш-репозиторий>.git \
  OLLAMA_URL=http://<ip-ollama>:11434
```

Если код уже скопирован в контейнер вручную, передайте только `OLLAMA_URL`.

## Шаг 5. Запуск и доступ

```bash
pct enter 100 -- systemctl start zelvera
pct enter 100 -- systemctl status zelvera
```

Веб-интерфейс: `http://<ip-zelvera>:8001`.

## Шаг 6. (Опционально) Доступ по имени через Caddy

На хосте (или в контейнере Zelvera):

```bash
apt-get install -y caddy
```

Скопируйте `Caddyfile` из этой папки в `/etc/caddy/Caddyfile`, замените
`zelvera.lan` на нужное имя и перезапустите:

```bash
systemctl restart caddy
```

## Резервное копирование

- Данные приложения: `/opt/zelvera/data` (SQLite + ChromaDB).
- Снапшот контейнера через Proxmox Backup Server или стандартный снапшот:
  `pct snapshot 100 zelvera-$(date +%Y%m%d)`.
- Периодический бэкап папки данных в crontab хоста:

```bash
0 3 * * * tar czf /var/backups/zelvera-data.tgz /opt/zelvera/data
```

## Полезные команды

```bash
pct enter 100                      # вход в контейнер Zelvera
pct enter 101                      # вход в контейнер Ollama
pct exec 100 -- journalctl -u zelvera -f   # логи приложения
pct exec 101 -- ollama ps          # загруженные модели/размер VRAM
```
