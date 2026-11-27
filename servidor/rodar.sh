#!/usr/bin/env bash
# Uma rodada de um robô no servidor. Chamado pelo systemd (servidor/systemd/), nunca em laço.
#
# REGRA DESTE REPOSITÓRIO: nenhum robô faz commit, push, pull, fetch ou chamada à API do GitHub.
# Os dados ficam só no disco do servidor (radar/conteudo/black, radar/img/black, radar/black, telegram/estado.json).
# A página /black/ vai para o bucket R2 da Cloudflare; o GitHub não recebe nada.
#
# Uso: rodar.sh <normal|ml|educado|alertas|telegram|notificacoes|auditoria|calibragem>
set -u
{
ROBO="${1:-}"
BASE="${ELITE_ROBOS:-/opt/elite-robos}"
RADAR="$BASE/radar"
export PATH="$BASE/.venv/bin:$PATH"
cd "$RADAR" || exit 1

exec 9>"/tmp/elite-robo-$ROBO.lock"
flock -n 9 || { echo "o robô $ROBO ainda está rodando; esta rodada fica para a próxima"; exit 0; }

case "$ROBO" in
  telegram)     BOT_ESTADO="${BOT_ESTADO:-$BASE/telegram/estado.json}" exec python3 "$BASE/telegram/bot.py" ;;
  notificacoes) exec python3 tools/notificacoes/vigia.py --sem-pausa ;;
  alertas)      exec python3 tools/black/alertas.py --fila ;;
  calibragem)   exec python3 tools/black/calibrar.py treinar ;;
  normal|ml|educado|auditoria) ;;
  *) echo "robô desconhecido: $ROBO"; exit 1 ;;
esac

# pauta.json e busca.json (jogos com resenha no site) vêm do site no ar, não do GitHub: no máximo a cada 6 horas
for arq in pauta.json busca.json; do
  if [ -z "$(find "$arq" -mmin -360 2>/dev/null)" ]; then
    curl -fsS -A "EliteBoardgamers/1.0 (+https://eliteboardgamers.com.br/black/robo/)" --max-time 60 \
      -o "$arq.novo" "https://eliteboardgamers.com.br/$arq" \
      && python3 -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" "$arq.novo" \
      && mv "$arq.novo" "$arq" || { rm -f "$arq.novo"; echo "aviso: não atualizei $arq; segue a cópia que já existe"; }
  fi
done

mkdir -p conteudo/black
COPIA="$BASE/copia/$ROBO"; rm -rf "$COPIA"; mkdir -p "$COPIA"; cp -a conteudo/black/. "$COPIA/"

case "$ROBO" in
  normal) timeout --kill-after=60 25m python3 tools/black/robo_normal.py ;;
  ml) timeout --kill-after=60 25m python3 tools/black/robo_ml.py ;;
  educado)
    acao=coletar
    if [ "$(date -u +%u)" = "7" ] && [ "$(date -u +%H)" -ge 14 ] && [ "$(date -u +%H)" -le 16 ]; then acao=varrer; fi
    timeout --kill-after=60 4h python3 tools/black/robo_educado.py "$acao" ;;
  auditoria) timeout --kill-after=60 50m python3 tools/auditoria_links.py --so-black --nao-falhar ;;
esac || echo "o robô terminou com erro ou no prazo; publica o que já leu"

date -u +%Y-%m-%dT%H:%M:%S+00:00 > "conteudo/black/batimento_$ROBO.txt"
for f in conteudo/black/*.json; do
  [ -e "$f" ] || continue
  python3 -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" "$f" 2>/dev/null \
    || { echo "JSON quebrado, volta a cópia: $f"; cp -a "$COPIA/$(basename "$f")" "$f" 2>/dev/null || true; }
done

# link de afiliado de terceiros sai dos dados antes da trava, para um post não parar a publicação (27/11/2026)
timeout 2m python3 tools/black/limpar_afiliados.py || echo "aviso: não consegui limpar os links de afiliado"

exec 8>/tmp/elite-robo-publicar.lock
# espera a vez de publicar no máximo 20 min: uma publicação travada não pode parar todos os robôs (27/11/2026)
flock -w 1200 8 || { echo "a trava de publicação está presa há 20 min; esta rodada não publica"; exit 1; }
timeout --kill-after=30 10m python3 tools/black/radar.py pagina >/dev/null || { echo "não consegui refazer a página"; exit 1; }

# postagem duplicada nunca vai ao ar (antes era o workflow black-sem-duplicata.yml)
if ! timeout 5m python3 tools/duplicatas.py >/dev/null 2>&1; then
  timeout --kill-after=30 10m python3 tools/black/radar.py pagina >/dev/null
  timeout 5m python3 tools/duplicatas.py || echo "aviso: a página refeita ainda tem duplicata; publica assim mesmo (a operação não para)"
fi

# link de afiliado de terceiros nunca vai ao ar (pedido do usuário em 05/11/2026), e também nunca para a operação
# (pedido do dono em 27/11/2026): o que sobrar na página é tirado do HTML e o resto é publicado
timeout 2m python3 tools/black/limpar_afiliados.py --saida || echo "aviso: não consegui limpar a saída"
if ! python3 -c "import sys,pathlib; sys.path.insert(0,'tools'); import verificar_site as v; \
p=[str(f) for f in pathlib.Path('black').rglob('*.*') if f.is_file() and v.AFILIADO_PUBLICO.search(f.read_text(encoding='utf-8',errors='ignore'))]; \
print('\n'.join(p)); sys.exit(1 if p else 0)"; then
  echo "link de afiliado ainda na página depois da limpeza: este arquivo não vai, o resto vai"
  python3 -c "import sys,pathlib; sys.path.insert(0,'tools'); import verificar_site as v; \
[f.unlink() for f in pathlib.Path('black').rglob('*.*') if f.is_file() and f.name != 'index.html' and v.AFILIADO_PUBLICO.search(f.read_text(encoding='utf-8',errors='ignore'))]"
fi

timeout --kill-after=30 10m python3 "$BASE/servidor/publicar_r2.py" black img/black
exit $?
}
