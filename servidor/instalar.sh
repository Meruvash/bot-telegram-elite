#!/usr/bin/env bash
# Instala (ou reinstala) os robôs da Elite num servidor Ubuntu com systemd (a VM da Oracle Cloud).
# Rode como root, de dentro da cópia deste repositório em /opt/elite-robos:
#   sudo git clone https://github.com/Meruvash/bot-telegram-elite /opt/elite-robos
#   sudo bash /opt/elite-robos/servidor/instalar.sh
# Rodar de novo é seguro. Nada aqui faz commit, push nem agenda acesso ao GitHub.
set -euo pipefail
BASE=/opt/elite-robos
ENV=/etc/elite-robos.env
ANTIGO=/opt/elite/site            # instalação antiga (robôs rodando a partir do repositório do site)
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
[ "$AQUI" = "$BASE" ] || { echo "Clone o repositório em $BASE e rode o instalar.sh de lá."; exit 1; }

apt-get update -q
apt-get install -y -q python3 python3-venv python3-dev build-essential libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev curl

id elite >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/elite --shell /usr/sbin/nologin elite

[ -d "$BASE/.venv" ] || python3 -m venv "$BASE/.venv"
"$BASE/.venv/bin/pip" install -q --upgrade pip
"$BASE/.venv/bin/pip" install -q requests Pillow beautifulsoup4 lxml feedparser price-parser protego cryptography boto3

# 1. Para os robôs antigos ANTES de copiar os dados (senão os dois publicariam em dobro)
if systemctl list-unit-files 'elite-radar*' --no-legend 2>/dev/null | grep -q .; then
  echo "Desligando os robôs antigos (elite-radar-*), que buscavam código no GitHub a cada ciclo..."
  systemctl disable --now elite-radar-normal.timer elite-radar-ml.timer elite-radar-educado.timer elite-radar-alertas.timer 2>/dev/null || true
  for i in $(seq 1 60); do  # espera um ciclo antigo em andamento terminar (até 30 min)
    systemctl is-active --quiet 'elite-radar@*' || break
    [ "$i" = 1 ] && echo "  um robô antigo ainda está no meio de um ciclo; esperando ele terminar..."
    sleep 30
  done
fi
if systemctl list-unit-files 'bot-telegram-elite*' --no-legend 2>/dev/null | grep -q .; then
  systemctl disable --now bot-telegram-elite.timer 2>/dev/null || true   # versão anterior deste bot, em pasta própria
fi

# 2. Dados: vêm da instalação antiga, uma vez só (historico.json guarda meses de preços)
mkdir -p "$BASE/radar/conteudo/black" "$BASE/radar/img/black" "$BASE/radar/black" "$BASE/copia"
if [ -z "$(ls -A "$BASE/radar/conteudo/black" 2>/dev/null)" ] && [ -d "$ANTIGO/conteudo/black" ]; then
  echo "Copiando os dados da instalação antiga ($ANTIGO)..."
  cp -a "$ANTIGO/conteudo/black/." "$BASE/radar/conteudo/black/"
  cp -a "$ANTIGO/img/black/." "$BASE/radar/img/black/" 2>/dev/null || true
  cp -a "$ANTIGO/black/." "$BASE/radar/black/" 2>/dev/null || true
  [ -f "$ANTIGO/conteudo/auditoria_links.json" ] && cp -a "$ANTIGO/conteudo/auditoria_links.json" "$BASE/radar/conteudo/"
fi
[ -f /opt/bot-telegram-elite/estado.json ] && [ ! -f "$BASE/telegram/estado.json" ] && cp /opt/bot-telegram-elite/estado.json "$BASE/telegram/"

# 3. Chaves: aproveita as da instalação antiga
if [ ! -f "$ENV" ]; then
  if [ -f /etc/elite-radar.env ]; then
    grep -vE '^(TELEGRAM_BOT_TOKEN|TELEGRAM_CANAL)=' /etc/elite-radar.env > "$ENV"   # o Telegram agora é do bot
  else
    cat > "$ENV" <<'EOF'
# Chaves dos robôs da Elite. Só root e o usuário elite leem este arquivo. Nunca coloque no repositório.
R2_ACCOUNT_ID=0b88cc2d6b58c936265686f078d9969f
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=elite-radar
ML_CLIENT_ID=
ML_CLIENT_SECRET=
KEEPA_KEY=
NTFY_TOKEN=
EOF
  fi
  cat >> "$ENV" <<'EOF'

# Bot do Telegram (telegram/bot.py)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CANAL=
TELEGRAM_CANAL_NOTICIAS=
TELEGRAM_CHAT_WHATSAPP=
EOF
fi
chown root:elite "$ENV"; chmod 640 "$ENV"

chown -R elite:elite "$BASE"
chmod +x "$BASE/servidor/rodar.sh"
cp "$BASE"/servidor/systemd/* /etc/systemd/system/
systemctl daemon-reload

cat <<EOF

Instalado em $BASE. Falta:
  1. sudo nano $ENV                         (token e canal do Telegram; confira as chaves do R2)
  2. Teste:  sudo systemctl start elite-robo@telegram && journalctl -u elite-robo@telegram -n 20
             sudo systemctl start elite-robo@normal   && journalctl -u elite-robo@normal -n 30
  3. Ligue:  sudo systemctl enable --now elite-robo-{normal,ml,educado,alertas,telegram,notificacoes,auditoria}.timer
  4. Veja:   systemctl list-timers 'elite-robo*'
EOF
