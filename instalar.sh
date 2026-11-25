#!/usr/bin/env bash
# Instala o bot do Telegram num servidor Linux com systemd (ex.: a VM da Oracle Cloud), em pasta própria,
# separado do robô do Black. Roda a cada 15 minutos. Uso: sudo bash instalar.sh
set -euo pipefail
DEST=/opt/bot-telegram-elite
USUARIO=bot-telegram
id "$USUARIO" >/dev/null 2>&1 || useradd --system --home "$DEST" --shell /usr/sbin/nologin "$USUARIO"
mkdir -p "$DEST"
install -m 644 "$(dirname "$0")/bot.py" "$DEST/bot.py"
if [ ! -f "$DEST/.env" ]; then
  cat > "$DEST/.env" <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_CANAL=
TELEGRAM_CANAL_NOTICIAS=
TELEGRAM_CHAT_WHATSAPP=
EOF
fi
chown -R "$USUARIO":"$USUARIO" "$DEST"
chmod 600 "$DEST/.env"

cat > /etc/systemd/system/bot-telegram-elite.service <<EOF
[Unit]
Description=Bot do Telegram da Elite Boardgamers (uma rodada)
After=network-online.target
[Service]
Type=oneshot
User=$USUARIO
WorkingDirectory=$DEST
ExecStart=/usr/bin/python3 $DEST/bot.py
TimeoutStartSec=300
EOF

cat > /etc/systemd/system/bot-telegram-elite.timer <<'EOF'
[Unit]
Description=Bot do Telegram da Elite Boardgamers a cada 15 minutos
[Timer]
OnBootSec=3min
OnUnitActiveSec=15min
RandomizedDelaySec=60
[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
echo "Instalado em $DEST."
echo "1) Preencha o token e o canal:  sudo nano $DEST/.env"
echo "2) Teste:                        sudo -u $USUARIO python3 $DEST/bot.py --teste"
echo "3) Ligue a agenda:               sudo systemctl enable --now bot-telegram-elite.timer"
