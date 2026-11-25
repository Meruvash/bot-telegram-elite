#!/usr/bin/env bash
# Atualiza o código dos robôs. SÓ À MÃO, quando houver mudança no repositório: nunca ponha isto num timer ou cron.
# É o único momento em que o servidor fala com o GitHub (um git pull, como qualquer pessoa faria).
#   sudo bash /opt/elite-robos/servidor/atualizar.sh
set -euo pipefail
BASE=/opt/elite-robos
git -c safe.directory="$BASE" -C "$BASE" pull --ff-only
chown -R elite:elite "$BASE"
chmod +x "$BASE/servidor/rodar.sh"
cp "$BASE"/servidor/systemd/* /etc/systemd/system/
systemctl daemon-reload
echo "Código atualizado. Os timers seguem como estavam: systemctl list-timers 'elite-robo*'"
