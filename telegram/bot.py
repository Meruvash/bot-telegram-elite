"""Bot do Telegram da Elite Boardgamers: promoções do Black de Verdade e notícias/resenhas do site.

Projeto separado do repositório do site, de propósito: os robôs do Radar Black (que consultavam lojas e faziam
centenas de commits por semana) levaram à desativação do repositório antigo. Este bot:
  - NÃO consulta loja nenhuma: só lê as duas listas públicas que o próprio site já publica
    (https://eliteboardgamers.com.br/black/alertas.json e /alertas/conteudo.json), 2 pedidos por rodada;
  - NÃO faz commit nem push: guarda o que já publicou num arquivo local (estado.json);
  - publica pela API oficial de bots do Telegram (permitida, sem risco de banimento por automação).

Opcional: com TELEGRAM_CHAT_WHATSAPP (o seu chat privado com o bot), cada item também chega lá já formatado para
o WhatsApp (*negrito* do WhatsApp, link no fim). No celular é só tocar e segurar, copiar e colar no Canal do WhatsApp.

Uso (no servidor, o timer elite-robo-telegram chama servidor/rodar.sh telegram a cada 15 min):
  python3 bot.py              uma rodada
  python3 bot.py --simular    mostra o que seria publicado, sem enviar nada e sem gravar estado
  python3 bot.py --teste      manda uma mensagem de teste para o canal (confere token e permissão)

Variáveis (no servidor, em /etc/elite-robos.env; para testar fora dele, um .env ao lado do bot.py):
  TELEGRAM_BOT_TOKEN       token do @BotFather (obrigatório)
  TELEGRAM_CANAL           @canal das promoções (e das notícias, se TELEGRAM_CANAL_NOTICIAS ficar vazio)
  TELEGRAM_CANAL_NOTICIAS  @canal só das notícias e resenhas (opcional)
  TELEGRAM_CHAT_WHATSAPP   id numérico do seu chat com o bot, para receber os textos prontos do WhatsApp (opcional)
"""
import datetime as dt
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ESTADO = Path(os.environ.get("BOT_ESTADO", AQUI / "estado.json"))
SITE = "https://eliteboardgamers.com.br"
FEEDS = {"black": f"{SITE}/black/alertas.json", "site": f"{SITE}/alertas/conteudo.json"}
PAGINA = {"black": f"{SITE}/black/", "noticias": f"{SITE}/noticias/", "resenhas": f"{SITE}/resenhas/"}
UA = "EliteBoardgamersBot/1.0 (+https://eliteboardgamers.com.br/)"  # identifica o bot; nunca se passar por navegador
MAX_POR_RODADA = 6       # acima disso o resto fica para a próxima rodada (sem enxurrada no canal)
PAUSA = 3.5              # segundos entre mensagens (o Telegram aceita ~20 por minuto num canal)
VALIDADE = dt.timedelta(hours=12)  # promoção ou notícia mais velha que isso não é mais publicada
GUARDA_IDS = 1000


def carregar_env():
    arq = AQUI / ".env"
    if not arq.exists():
        return
    for linha in arq.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def baixar_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def itens(feeds):
    """Junta as duas listas num formato só: id único, tema (black, noticias, resenhas), hora, título, texto, url, imagem."""
    out = []
    for origem, lista in feeds.items():
        for a in lista or []:
            if not isinstance(a, dict) or not a.get("id") or not a.get("titulo") or not a.get("url"):
                continue
            tema = "black" if origem == "black" else (a.get("tema") or "noticias")
            out.append({"id": f"{tema}:{a['id']}", "tema": tema, "hora": a.get("hora") or "", "titulo": a["titulo"],
                        "texto": a.get("texto") or "", "url": a["url"], "imagem": a.get("imagem")})
    return sorted(out, key=lambda a: a["hora"])


def _hora(s):
    try:
        h = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return h if h.tzinfo else h.replace(tzinfo=dt.timezone.utc)
    except (ValueError, AttributeError):
        return None


def novos(lista, estado, agora=None):
    agora = agora or dt.datetime.now(dt.timezone.utc)
    vistos = set(estado.get("publicados", []))
    res = []
    for a in lista:
        if a["id"] in vistos:
            continue
        h = _hora(a["hora"])
        if h is None or agora - h > VALIDADE:
            continue
        res.append(a)
    return res


def _esc(s):
    return html.escape(s or "", quote=False)


def texto_telegram(a):
    rotulo = {"black": "Black de Verdade", "noticias": "Notícias", "resenhas": "Resenhas"}.get(a["tema"], "Elite Boardgamers")
    pag = PAGINA.get(a["tema"], SITE)
    return f"<b>{_esc(a['titulo'])}</b>\n{_esc(a['texto'])}\n\n<a href=\"{html.escape(pag)}\">{rotulo}</a> · Elite Boardgamers"


def botoes(a):
    rot = "Ver a oferta" if a["tema"] == "black" else ("Ler a resenha" if a["tema"] == "resenhas" else "Ler a notícia")
    return {"inline_keyboard": [[{"text": rot, "url": a["url"]}]]}


def texto_whatsapp(a):
    """Formato do WhatsApp: *negrito*, sem HTML. Leva o link do site (no Black, o link da oferta)."""
    titulo = a["titulo"].strip()
    emoji = "" if titulo[:1] and not titulo[:1].isalnum() else {"black": "🔥 ", "noticias": "📰 ", "resenhas": "⭐ "}.get(a["tema"], "🎲 ")
    if emoji == "" and " " in titulo and not titulo[:1].isalnum() and titulo[0] not in "−-":  # "📰 Título" -> "📰 *Título*"
        emoji, titulo = titulo.split(" ", 1)[0] + " ", titulo.split(" ", 1)[1]
    elif emoji == "":
        emoji = "🔥 " if a["tema"] == "black" else ""
    return f"{emoji}*{titulo}*\n\n{a['texto'].strip()}\n\n{a['url']}"


class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}"

    def chamar(self, metodo, corpo, tentativas=3):
        dados = json.dumps(corpo).encode("utf-8")
        for _ in range(tentativas):
            req = urllib.request.Request(f"{self.base}/{metodo}", data=dados,
                                         headers={"Content-Type": "application/json", "User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                resp = _ler_erro(e)
                espera = (resp.get("parameters") or {}).get("retry_after")
                if e.code == 429 and espera:  # limite do Telegram: espera o tempo que ele pede e tenta de novo
                    time.sleep(min(int(espera) + 1, 120))
                    continue
                return resp
            except urllib.error.URLError as e:
                return {"ok": False, "description": f"rede: {e.reason}"}
        return {"ok": False, "description": "limite do Telegram (429) persistente"}

    def publicar(self, chat, a):
        legenda = texto_telegram(a)
        if a.get("imagem") and len(legenda) <= 1024:
            r = self.chamar("sendPhoto", {"chat_id": chat, "photo": a["imagem"], "caption": legenda, "parse_mode": "HTML",
                                          "reply_markup": botoes(a)})
            if r.get("ok"):
                return r
        return self.chamar("sendMessage", {"chat_id": chat, "text": legenda, "parse_mode": "HTML", "reply_markup": botoes(a),
                                           "link_preview_options": {"is_disabled": bool(a.get("imagem"))}})

    def texto(self, chat, txt):
        return self.chamar("sendMessage", {"chat_id": chat, "text": txt, "link_preview_options": {"is_disabled": True}})


def _ler_erro(e):
    try:
        return json.loads(e.read().decode("utf-8"))
    except Exception:
        return {"ok": False, "description": f"HTTP {e.code}"}


def canal(nome):
    nome = (nome or "").strip()
    return nome if not nome or nome.startswith(("@", "-")) or nome.lstrip("-").isdigit() else "@" + nome


def ler_estado():
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def gravar_estado(est):
    est["publicados"] = est.get("publicados", [])[-GUARDA_IDS:]
    tmp = ESTADO.with_suffix(".tmp")
    tmp.write_text(json.dumps(est, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(ESTADO)  # troca atômica: uma queda no meio não corrompe o estado


def rodar(simular=False):
    feeds = {}
    for nome, url in FEEDS.items():
        try:
            feeds[nome] = baixar_json(url)
        except Exception as e:  # site fora do ar: pula esta lista e tenta na próxima rodada
            print(f"aviso: não li {url} ({e})")
    if not feeds:
        return 1
    lista = itens(feeds)
    est = ler_estado()

    if not est.get("iniciado"):  # primeira rodada: só marca o que já existe, para não despejar tudo no canal
        print(f"primeira rodada: {len(lista)} itens marcados como já vistos, nada publicado")
        if not simular:
            gravar_estado({"iniciado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                           "publicados": [a["id"] for a in lista]})
        return 0

    fila = novos(lista, est)
    if not fila:
        print("nada novo")
        return 0
    if simular:
        for a in fila[:MAX_POR_RODADA]:
            print("---", a["tema"], a["id"], "\n" + texto_telegram(a), "\n[WhatsApp]\n" + texto_whatsapp(a))
        print(f"(simulação: {min(len(fila), MAX_POR_RODADA)} de {len(fila)} itens novos)")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    c_black = canal(os.environ.get("TELEGRAM_CANAL"))
    c_noticias = canal(os.environ.get("TELEGRAM_CANAL_NOTICIAS")) or c_black
    c_zap = canal(os.environ.get("TELEGRAM_CHAT_WHATSAPP"))
    if not token or not c_black:
        print("erro: falta TELEGRAM_BOT_TOKEN ou TELEGRAM_CANAL no .env")
        return 2
    tg = Telegram(token)
    enviados = falhas = 0
    for a in fila[:MAX_POR_RODADA]:
        destino = c_black if a["tema"] == "black" else c_noticias
        r = tg.publicar(destino, a)
        if not r.get("ok"):
            falhas += 1
            print(f"falhou {a['id']}: {r.get('description')}")
            if falhas >= 2:
                break  # token ou permissão errados: para e tenta na próxima rodada, sem marcar nada
            continue
        if c_zap:
            tg.texto(c_zap, texto_whatsapp(a))
        est.setdefault("publicados", []).append(a["id"])
        gravar_estado(est)  # grava a cada envio: se cair no meio, não repete o que já saiu
        enviados += 1
        time.sleep(PAUSA)
    print(f"ok: {enviados} publicados, {falhas} falhas, {max(0, len(fila) - MAX_POR_RODADA)} ficaram para a próxima")
    return 0 if falhas == 0 else 3


def teste():
    token, c = os.environ.get("TELEGRAM_BOT_TOKEN"), canal(os.environ.get("TELEGRAM_CANAL"))
    if not token or not c:
        print("erro: falta TELEGRAM_BOT_TOKEN ou TELEGRAM_CANAL no .env")
        return 2
    r = Telegram(token).texto(c, "Teste do bot da Elite Boardgamers: se você está lendo isto, o bot publica neste canal.")
    print("ok: mensagem de teste publicada" if r.get("ok") else f"falhou: {r.get('description')}")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    carregar_env()
    if "--teste" in sys.argv:
        sys.exit(teste())
    sys.exit(rodar(simular="--simular" in sys.argv))
