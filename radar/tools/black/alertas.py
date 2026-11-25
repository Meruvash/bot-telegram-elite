"""Alertas no celular do Black de Verdade, pelo ntfy (ntfy.sh: serviço open source e gratuito de notificações).

Quem quer receber assina o canal TOPICO no app ntfy (Android ou iPhone) ou no navegador (ntfy.sh/<canal>); o
alerta chega na barra de notificações do celular, como mensagem, e o toque abre a página do radar.

O robô chama `avisar()` no fim de cada leitura: compara o radar de agora com o da última leitura
(conteudo/black/alertas_estado.json) e manda um alerta para cada jogo que entrou com desconto real de 20% ou mais
(no máximo MAX_POR_LEITURA por leitura; o resto vai num alerta-resumo). Jogo que sai e volta no mesmo dia não
avisa de novo. Na primeira vez só grava o estado, sem disparar nada (para não mandar 60 alertas de uma vez).

Envio com conta: se existir a variável NTFY_TOKEN (token de uma conta gratuita do ntfy.sh, guardado como secret),
o envio vai autenticado e o limite diário passa a ser da conta, não do endereço de IP (sem conta, o ntfy.sh limita
por IP, e IP compartilhado esgota rápido). Alerta que não sai fica pendente e é tentado de novo nas leituras
seguintes, por até 6 horas.

Telegram: quem publica no canal é o bot deste repositório (telegram/bot.py), lendo black/alertas.json. Este módulo
não publica mais no Telegram (assim nada sai em dobro). O nome público do canal vai em
conteudo/black/alertas_config.json ({"telegram": "nomedocanal"}) para a página mostrar o botão "Entrar no canal".

Sem git: o estado (alertas_estado.json) fica só no disco do servidor. Antes, buscava no GitHub o estado salvo na main;
isso saiu em 25/11/2026 (um robô só, sem reserva no GitHub, e nenhum acesso automático ao GitHub).

Uso manual: python3 tools/black/alertas.py [--teste]   (--teste manda um alerta só para o canal de teste)
"""
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
ESTADO = ROOT / "conteudo" / "black" / "alertas_estado.json"
FILA = ROOT / "conteudo" / "black" / "alertas_fila.json"
FEED = ROOT / "black" / "alertas.json"  # lista pública dos últimos alertas; o serviço de notificações do site lê e manda o push  # alertas esperando envio pelo GitHub Actions (que tem o token)
SERVIDOR = "https://ntfy.sh"
TOPICO = "eliteboardgamers-black"
TOPICO_TESTE = "eliteboardgamers-black-teste"
PAGINA = "https://eliteboardgamers.com.br/black/"
ICONE = "https://eliteboardgamers.com.br/apple-touch-icon.png"
MAX_POR_LEITURA = 10  # alertas individuais por leitura; os outros jogos novos vão todos, pelo nome, num alerta-resumo
UA = {"User-Agent": "EliteBoardgamers/1.0 (+https://eliteboardgamers.com.br/black/robo/)"}


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def no_feed(titulo, texto, link, imagem=None):
    """Acrescenta o alerta à lista pública black/alertas.json (os 30 mais recentes). O serviço de notificações do site
    (worker em api.eliteboardgamers.com.br) lê essa lista a cada minuto e manda a notificação do navegador para quem
    tocou em "Ativar alertas" na página: sem app e sem cadastro."""
    try:
        feed = json.loads(FEED.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        feed = []
    agora = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    # id fixo por alerta e por dia: se dois robôs (ou o principal e a reserva) mandarem o mesmo alerta, o serviço de
    # notificações guarda um só (INSERT OR IGNORE pelo id)
    ident = hashlib.sha1(f"{agora[:10]}|{titulo}".encode()).hexdigest()[:16]
    if any(x.get("id") == ident for x in feed):
        return
    feed.append({"id": ident, "hora": agora, "titulo": titulo, "texto": texto, "url": link, "imagem": imagem})
    FEED.parent.mkdir(parents=True, exist_ok=True)
    FEED.write_text(json.dumps(feed[-30:], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def enviar(titulo, texto, link=PAGINA, tags="game_die", prioridade="default", topico=TOPICO, imagem=None):
    if topico == TOPICO:
        no_feed(titulo, texto, link, imagem)
    return _enviar_ntfy(titulo, texto, link, tags, prioridade, topico, imagem)


def _enviar_ntfy(titulo, texto, link=PAGINA, tags="game_die", prioridade="default", topico=TOPICO, imagem=None):
    """Sem NTFY_TOKEN (leitura de reserva fora do GitHub), o alerta vai para a fila e o workflow alertas.yml envia."""
    if not os.environ.get("NTFY_TOKEN") and topico == TOPICO:
        fila = json.loads(FILA.read_text(encoding="utf-8")) if FILA.exists() else []
        fila.append({"titulo": titulo, "texto": texto, "link": link, "tags": tags, "prioridade": prioridade, "imagem": imagem,
                     "hora": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")})
        FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return True
    return _publicar(titulo, texto, link, tags, prioridade, topico, imagem)


def enviar_fila():
    """Envia o que a leitura de reserva deixou na fila (só no GitHub Actions, com NTFY_TOKEN) e esvazia a fila."""
    if not FILA.exists():
        print("fila vazia")
        return
    fila = json.loads(FILA.read_text(encoding="utf-8"))
    limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)).isoformat()
    sobra = []
    for a in fila:
        if a["hora"] < limite:
            continue  # promoção de mais de 6 horas atrás: não vale mais o alerta
        if not _publicar(a["titulo"], a["texto"], a["link"], a["tags"], a["prioridade"], TOPICO, a.get("imagem")):
            sobra.append(a)
    FILA.write_text(json.dumps(sobra, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ok fila: {len(fila) - len(sobra)} alertas enviados, {len(sobra)} ficaram para a próxima")


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _publicar(titulo, texto, link=PAGINA, tags="game_die", prioridade="default", topico=TOPICO, imagem=None):
    """Manda um alerta para o canal. Os cabeçalhos do ntfy vão em ASCII; título e texto acentuados vão no corpo JSON."""
    corpo = {"topic": topico, "title": titulo, "message": texto, "click": link, "tags": tags.split(","),
             "priority": {"min": 1, "low": 2, "default": 3, "high": 4, "max": 5}[prioridade], "icon": ICONE,
             "actions": [{"action": "view", "label": "Ver no Black de Verdade", "url": PAGINA}]}
    if imagem:
        corpo["attach"] = imagem
    cab = {**UA, "Content-Type": "application/json"}
    if os.environ.get("NTFY_TOKEN"):
        cab["Authorization"] = f"Bearer {os.environ['NTFY_TOKEN']}"
    try:
        r = requests.post(SERVIDOR, data=json.dumps(corpo).encode("utf-8"), headers=cab, timeout=20)
        if r.status_code != 200:
            print(f"   ntfy respondeu {r.status_code}: {r.text[:120]}")
        return r.status_code == 200
    except requests.RequestException:
        return False


FRESCO_HORAS = 24  # alerta individual só com preço lido há no máximo 24 horas
IMPERDIVEIS_POR_DIA = 3  # docs/PLANO_RADAR.md, Frente 3: alerta na hora só para Imperdível, no máximo 3 por dia


def fresco(x, agora=None):
    """O preço da oferta foi lido há no máximo FRESCO_HORAS? Sem hora conhecida, conta como fresco (como antes)."""
    try:
        t = dt.datetime.fromisoformat(str(x.get("verificado") or "").replace("Z", "+00:00"))
    except ValueError:
        return True
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (agora or dt.datetime.now(dt.timezone.utc)) - t <= dt.timedelta(hours=FRESCO_HORAS)


def avisar(radar_itens):
    """Alerta os jogos que entraram no radar desde a última leitura."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import radar  # noqa: E402  (aqui dentro: o radar também importa este módulo)
    melhor = {}
    for x in radar_itens:
        if x["slug"] not in melhor or (x.get("nota", 0), x["desc"]) > (melhor[x["slug"]].get("nota", 0), melhor[x["slug"]]["desc"]):
            melhor[x["slug"]] = x
    try:
        est = json.loads(ESTADO.read_text(encoding="utf-8"))
    except FileNotFoundError:
        est = None
    hoje = dt.date.today().isoformat()
    if est is None:  # primeira vez: só registra quem já está no radar
        ESTADO.write_text(json.dumps({"no_radar": sorted(melhor), "avisados": {s: hoje for s in melhor}}, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        print(f"ok alertas: estado inicial gravado com {len(melhor)} jogos (nenhum alerta enviado)")
        return
    antes = set(est.get("no_radar", []))
    avisados = {s: d for s, d in est.get("avisados", {}).items() if d >= (dt.date.today() - dt.timedelta(days=7)).isoformat()}
    limite = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=6)).isoformat()
    pendentes = {s: h for s, h in est.get("pendentes", {}).items() if h >= limite and s in melhor}
    novos = [x for s, x in melhor.items() if (s not in antes or s in pendentes) and avisados.get(s) != hoje]
    # piso do destaque (25/11/2026): oferta que economiza menos de R$ 30 ou custa menos de R$ 50 fica só na página
    pequenas = [x for x in novos if not radar.vale_destaque(x)]
    novos = [x for x in novos if radar.vale_destaque(x)]
    for x in pequenas:
        pendentes.pop(x["slug"], None)
    novos.sort(key=lambda x: (-x.get("nota", 0), -x["desc"]))
    enviados = 0
    # alerta individual só para oferta "Imperdível" com preço lido nas últimas 24 horas, no máximo
    # IMPERDIVEIS_POR_DIA por dia (docs/PLANO_RADAR.md, Frente 3); as outras acima do piso vão no alerta-resumo
    dia_cota = est.get("individuais_dia", {})
    ja_hoje = dia_cota.get(hoje, 0)
    vagas = max(0, IMPERDIVEIS_POR_DIA - ja_hoje)
    individuais = [x for x in novos if x.get("nivel", "Imperdível") == "Imperdível" and fresco(x)][:min(vagas, MAX_POR_LEITURA)]
    for x in individuais:
        nome = x["nome"].replace("–", "-").replace("—", "-")
        texto = (f"{brl(x['por'])} na {x['loja']}, {x['desc'] * 100:.0f}% abaixo da média real de {brl(x['ref'])}."
                 + (" Menor preço do período." if x.get("recorde") else "")
                 + (" Achado da comunidade, vendedor não conferido." if x.get("comunidade") else "")
                 + (" Em Outras promoções (nota BGG abaixo de 7)." if x.get("principal") is False else ""))
        if enviar(f"−{x['desc'] * 100:.0f}% {nome}", texto, link=x.get("url") or PAGINA, tags="game_die,moneybag",
                  prioridade="high" if x.get("nivel") == "Imperdível" or (x.get("nivel") is None and x["desc"] >= 0.35) else "default",
                  imagem=x.get("imagem")):
            enviados += 1
            avisados[x["slug"]] = hoje
            pendentes.pop(x["slug"], None)
        else:
            pendentes.setdefault(x["slug"], dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"))
    # loja em promoção forte (docs/PLANO_RADAR.md, Frente 1, item 3): um alerta quando a loja entra no bloco, no
    # máximo um por loja a cada 7 dias; fora da cota de Imperdíveis, porque fala de uma loja, não de um jogo
    import nota  # noqa: E402
    fortes = nota.lojas_fortes(radar_itens, excluir=radar.FORA)
    lojas_avisadas = {lj: d for lj, d in est.get("lojas_avisadas", {}).items()
                      if d >= (dt.date.today() - dt.timedelta(days=7)).isoformat()}
    for lj, ofs in fortes.items():
        if lj in lojas_avisadas or lj in est.get("lojas_fortes", []):
            continue
        txt = (f"{len(ofs)} ofertas com nota alta ao mesmo tempo, até {max(x['desc'] for x in ofs) * 100:.0f}% abaixo da média real. "
               f"Destaques: " + "; ".join(f"{x['nome']} por {brl(x['por'])}" for x in ofs[:3]) + ". Todas no bloco da loja, no topo da página.")
        if enviar(f"🏬 {lj} entrou em Black de verdade", txt, link=PAGINA + "#lojas-black", tags="game_die,department_store",
                  prioridade="high"):
            lojas_avisadas[lj] = hoje
    ids = {id(x) for x in individuais}
    resto = [x for x in novos if id(x) not in ids]
    # todos os outros jogos novos saem no resumo, pelo nome e com o desconto (pedido do usuário em 04/11/2026)
    lista_resto = "; ".join(f"{x['nome']} (−{x['desc'] * 100:.0f}%)" for x in resto)
    if len(lista_resto) > 3500:  # limite do texto do alerta; o restante está na página
        lista_resto = lista_resto[:3500].rsplit("; ", 1)[0] + "; e outros na página"
    if resto and enviar(f"+{len(resto)} promoções novas no Black de Verdade", lista_resto, tags="game_die"):
        for x in resto:
            avisados[x["slug"]] = hoje
            pendentes.pop(x["slug"], None)
    ESTADO.write_text(json.dumps({"no_radar": sorted(melhor), "avisados": avisados, "pendentes": pendentes,
                                  "individuais_dia": {hoje: ja_hoje + enviados}, "lojas_fortes": sorted(fortes),
                                  "lojas_avisadas": lojas_avisadas}, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"ok alertas: {len(novos)} jogos novos no radar acima do piso ({len(pequenas)} abaixo, só na página), {enviados} alertas enviados" + (f" e 1 resumo com {len(resto)}" if resto else ""))


if __name__ == "__main__":
    if "--fila" in sys.argv:
        enviar_fila()
    elif "--teste" in sys.argv:
        print(enviar("−30% Jogo de teste", "R$ 99,90 na Loja Exemplo, 30% abaixo da média real. Alerta de teste.", topico=TOPICO_TESTE))
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import radar
        r = radar.calcular()
        avisar(r[0] + r[3])
