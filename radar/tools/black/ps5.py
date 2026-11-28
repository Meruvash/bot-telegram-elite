"""Vigia de PlayStation 5 do Ofertas Elite (pedido do usuário em 20/11/2026: "se tiver qualquer PlayStation 5
abaixo de R$ 3.000, me informa e adiciona essa promoção no site"; limite subiu para R$ 3.700 em 25/11/2026,
a pedido do dono: o PS5 Digital passou a R$ 4.599,99 e nada aparecia abaixo de R$ 3.000).

Fora do tema do site (jogos de tabuleiro), por isso fica numa seção própria da página do Black e num arquivo próprio
(conteudo/black/ps5.json). Duas fontes, com as mesmas regras do radar:

  - API oficial do Mercado Livre (robô ml, a cada ciclo): busca no catálogo os produtos "console PlayStation 5", lê os
    anúncios de cada um e fica com o mais barato NOVO de loja oficial ou MercadoLíder. Anúncio de vendedor comum,
    usado, recondicionado, importado ou de acessório não entra.
  - Achados conferidos a mão (campo "manuais" do mesmo arquivo): só com link direto da página do produto na loja
    (nunca afiliado de ninguém), preço à vista e a hora em que alguém abriu a página e viu o preço. Saem sozinhos
    depois de radar.PRECO_MAX_HORAS.

Só entra na página o que está abaixo de LIMITE. Quando aparece um PS5 novo abaixo do limite, manda alerta (ntfy).

Uso: python3 tools/black/ps5.py   (lê a API, grava ps5.json e mostra o resultado; o robô ml chama ler() sozinho)
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar  # noqa: E402

ARQ = radar.DADOS / "ps5.json"
LIMITE = 3700.0  # pedido do dono em 25/11/2026 (era 3000.0)
BUSCAS = ("console playstation 5", "playstation 5 slim", "playstation 5 pro", "ps5 console")
PRECO_MIN = 1500.0  # nenhum PS5 novo custa menos que isso: abaixo, é jogo ou acessório (20/11/2026: "Catan Console
                    # Edition PS5" a R$ 199,97 entrou como console na primeira leitura)
# título de console de verdade: "Console (Sony) PlayStation 5/PS5 ...", "PlayStation 5/PS5 Slim|Pro|Digital ..." ou o
# título começando por "(Sony) PlayStation 5/PS5"; só mencionar PS5 não basta (jogos dizem "Jogo PS5", "Edition PS5")
CONSOLE = re.compile(r"(?i)\b(console|videogame|video game)\s+(sony\s+)?(playstation\s*5|ps\s*5)\b|"
                     r"\b(playstation\s*5|ps\s*5)\s+(slim|pro|digital|standard|825\s*gb|1\s*tb|2\s*tb)\b|"
                     r"^\s*(sony\s+)?(playstation\s*5|ps\s*5)\b")
# acessório, jogo, peça, usado e afins: fora
NAO_CONSOLE = re.compile(r"(?i)\b(controle|dualsense|capa|case|skin|adesivo|suporte|base|dock|cooler|ventoinha|carregador|"
                         r"cabo|fonte|headset|fone|volante|avulso|ssd|hd|mem[oó]ria|gift ?card|cart[aã]o|assinatura|plus|portal|"
                         r"vr2?|pulse|tampa|faceplate|pel[ií]cula|usado|seminovo|recondicionado|vitrine|reembalado|caixa vazia|"
                         r"r[eé]plica|chaveiro|miniatura|ps4|playstation 4|xbox|nintendo|switch|console edition|edition|"
                         r"deluxe|goty|jogo para|game para)\b")
# peça ou jogo vendido sozinho: o título começa pelo item ("Leitor de disco para PS5 Pro", "Jogo Spider-Man 2 PS5")
AVULSO = re.compile(r"(?i)^\s*(leitor|unidade|drive|jogo|game|m[ií]dia)\b")


def eh_console(titulo, preco=None):
    t = titulo or ""
    if preco is not None and preco < PRECO_MIN:
        return False
    return bool(CONSOLE.search(t) and not NAO_CONSOLE.search(t) and not AVULSO.search(t))


KABUM = "https://www.kabum.com.br/gamer/playstation/consoles-playstation/playstation-5"


def _produtos_next(o):
    """Produtos (dicts com priceWithDiscount) dentro do __NEXT_DATA__ da KaBuM!, que guarda parte dos dados como JSON
    dentro de string."""
    if isinstance(o, dict):
        if "priceWithDiscount" in o and o.get("code"):
            yield o
        for v in o.values():
            yield from _produtos_next(v)
    elif isinstance(o, list):
        for v in o:
            yield from _produtos_next(v)
    elif isinstance(o, str) and o[:1] == "{" and "priceWithDiscount" in o:
        try:
            yield from _produtos_next(json.loads(o))
        except ValueError:
            pass


def kabum():
    """PS5 da KaBuM! (pedido do dono em 28/11/2026: o radar precisa mostrar preço, e a API do Mercado Livre não dá).
    Uma página por leitura (a categoria de consoles PS5), pelo leitor das lojas: respeita o robots.txt (a KaBuM!
    libera), se identifica como EliteBoardgamers e para se a loja bloquear. Vendido pela própria KaBuM! conta como
    vendedor conferido; anúncio de marketplace dentro da KaBuM! entra com o aviso de vendedor não conferido."""
    import apis
    import lojas
    html = lojas.pagina(KABUM)
    if not html:
        print("-- PS5: KaBuM! não respondeu nesta leitura")
        return None
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        print("-- PS5: KaBuM! sem dados de produto na página")
        return None
    achados, vistos = [], set()
    for p in _produtos_next(json.loads(m.group(1))):
        nome, preco = p.get("name") or "", p.get("priceWithDiscount") or p.get("price")
        if p["code"] in vistos or not preco or float(preco) < PRECO_MIN or not p.get("available"):
            continue
        if "consoles playstation" not in (p.get("category") or "").lower() or re.search(r"(?i)portal|controle sem fio|usado|recondicionado", nome.split(",")[0]):
            continue
        vistos.add(p["code"])
        loja_mesmo = (p.get("sellerName") or "").lower().startswith("kabum")
        achados.append({"modelo": nome[:120], "loja": "KaBuM!", "vendedor": p.get("sellerName") or "KaBuM!",
                        "nivel": "vendido pela KaBuM!" if loja_mesmo else "marketplace na KaBuM!", "preco": float(preco),
                        "url": f"https://www.kabum.com.br/produto/{p['code']}/{p.get('friendlyName') or ''}".rstrip("/"),
                        "fonte": "página da KaBuM!", "verificado": apis.agora(), "vendedor_ok": loja_mesmo, "console": True,
                        "parcelado": p.get("maxInstallment"),
                        # foto do produto na própria KaBuM! (pedido do dono em 28/11/2026: os PS5 estavam sem foto)
                        "imagem": next((u for u in [p.get("image"), *(p.get("images") or []), p.get("thumbnail")]
                                        if isinstance(u, str) and u.startswith("https://")), None)})
    achados.sort(key=lambda a: a["preco"])
    print(f"ok PS5 KaBuM!: {len(achados)} consoles com preço (menor R$ {achados[0]['preco']:.2f})" if achados else "ok PS5 KaBuM!: nenhum console disponível")
    return achados


# Lojas na plataforma VTEX com a consulta pública de catálogo liberada no robots.txt (pedido do dono em 28/11/2026:
# "liga a Fast Shop e a Americanas também"). Uma consulta por loja e por leitura.
VTEX = {"Americanas": ("https://www.americanas.com.br", ("americanas",)),
        "Fast Shop": ("https://site.fastshop.com.br", ("fast shop", "fastshop"))}
NAO_PS5 = re.compile(r"(?i)portal|controle|dualsense\b(?!.*console)|jogo|game |headset|cabo|capa|suporte|usado|recondicionado|vitrine")


def vtex(loja, base, proprias):
    """PS5 de uma loja VTEX pela consulta pública /api/catalog_system/pub/products/search (preço, estoque, vendedor,
    foto e link), pelo leitor das lojas: robots.txt, identificação EliteBoardgamers, para se bloquear."""
    import apis
    import lojas
    from urllib.parse import quote
    url = f"{base}/api/catalog_system/pub/products/search?ft={quote('console playstation 5')}&_from=0&_to=29"
    texto = lojas.pagina(url) if not lojas.NUNCA.search(base) else _direto(url)
    if not texto:
        print(f"-- PS5: {loja} não respondeu nesta leitura")
        return None
    try:
        produtos = json.loads(texto)
    except ValueError:
        print(f"-- PS5: {loja} não devolveu JSON")
        return None
    achados = []
    for p in produtos:
        nome = p.get("productName") or ""
        cats = " ".join(p.get("categories") or []).lower()
        if not re.search(r"(?i)playstation\s*5|ps5", nome) or re.search(r"(?i)portal|usado|recondicionado|vitrine", nome):
            continue
        # "Console PlayStation 5 ... 1 Controle" é console; sem "Console" no começo, controle, jogo ou cabo ficam fora
        if not re.match(r"(?i)\s*console", nome) and (NAO_PS5.search(nome) or "console" not in cats):
            continue
        melhor = None
        for it in p.get("items") or []:
            for sel in it.get("sellers") or []:
                o = sel.get("commertialOffer") or {}
                preco = o.get("Price")
                if not preco or float(preco) < PRECO_MIN or not o.get("AvailableQuantity"):
                    continue
                if not melhor or preco < melhor[0]:
                    img = next((i.get("imageUrl") for i in it.get("images") or [] if (i.get("imageUrl") or "").startswith("https://")), None)
                    melhor = (float(preco), sel.get("sellerName") or loja, img)
        if not melhor or not (p.get("link") or "").startswith("https://"):
            continue
        preco, vendedor, img = melhor
        propria = any(x in vendedor.lower() for x in proprias)
        achados.append({"modelo": nome[:120], "loja": loja, "vendedor": vendedor,
                        "nivel": f"vendido pela {loja}" if propria else f"marketplace na {loja}", "preco": preco,
                        "url": p["link"], "fonte": f"catálogo da {loja}", "verificado": apis.agora(), "vendedor_ok": propria,
                        "console": True, "imagem": img})
    achados.sort(key=lambda a: a["preco"])
    print(f"ok PS5 {loja}: {len(achados)} consoles com preço" + (f" (menor R$ {achados[0]['preco']:.2f})" if achados else ""))
    return achados


def _direto(url):
    """Leitura de uma loja que o leitor geral pula (lista NUNCA de lojas.py, feita para o catálogo de jogos de
    tabuleiro): mesmas regras, feitas aqui — robots.txt conferido para EliteBoardgamers e ClaudeBot, identificação
    EliteBoardgamers, e 401/403/429 encerra a leitura sem insistir."""
    import requests
    from urllib.parse import urlparse
    from protego import Protego
    import lojas
    u = urlparse(url)
    h = {"User-Agent": lojas.UA}
    try:
        rb = requests.get(f"{u.scheme}://{u.netloc}/robots.txt", headers=h, timeout=20)
        regras = Protego.parse(rb.text if rb.status_code == 200 else "")
        if not all(regras.can_fetch(url, a) for a in ("EliteBoardgamers", "ClaudeBot")):
            print(f"-- PS5: robots.txt de {u.netloc} não libera {u.path}")
            return None
        r = requests.get(url, headers=h, timeout=30)
    except requests.RequestException:
        return None
    if r.status_code in (401, 403, 429):
        print(f"-- PS5: {u.netloc} respondeu {r.status_code}; não insistimos")
        return None
    return r.text if r.status_code in (200, 206) else None


def _lojas(dados):
    """Todos os PS5 lidos direto nas lojas (KaBuM!, Americanas, Fast Shop)."""
    return (dados.get("kabum") or []) + [a for k in VTEX for a in ((dados.get("vtex") or {}).get(k) or [])]


def _console(a):
    return a.get("console") or eh_console(a.get("modelo"), a.get("preco"))


def ler_arquivo():
    return radar.ler(ARQ, {"limite": LIMITE, "api": [], "manuais": []})


def ler():
    """Busca na API do Mercado Livre e grava ps5.json. Devolve as ofertas abaixo do limite que são novas desde a
    última leitura (para o alerta)."""
    import apis
    import requests
    dados = ler_arquivo()
    antes_kb = {(a["url"], a["preco"]) for a in _lojas(dados) if a.get("vendedor_ok") and a["preco"] < LIMITE}
    try:
        kb = kabum()
    except Exception as ex:  # noqa: BLE001 — a KaBuM! nunca derruba o vigia
        print(f"aviso: PS5 KaBuM! falhou ({ex.__class__.__name__}: {ex})")
        kb = None
    if kb is not None:
        dados["kabum"] = kb
    for loja, (base, proprias) in VTEX.items():
        try:
            lido = vtex(loja, base, proprias)
        except Exception as ex:  # noqa: BLE001 — uma loja nunca derruba o vigia
            print(f"aviso: PS5 {loja} falhou ({ex.__class__.__name__}: {ex})")
            lido = None
        if lido is not None:
            dados.setdefault("vtex", {})[loja] = lido
    radar.gravar(ARQ, dados)
    novos_kb = [a for a in _lojas(dados) if a.get("vendedor_ok") and a["preco"] < LIMITE and (a["url"], a["preco"]) not in antes_kb]
    token = apis._ml_token()
    if not token:
        print("-- PS5: sem chave do Mercado Livre; segue só com a KaBuM!")
        return novos_kb
    h = {**apis.UA, "Authorization": f"Bearer {token}"}
    produtos = {}
    for q in BUSCAS:
        r = requests.get(f"{apis.ML}/products/search", params={"status": "active", "site_id": "MLB", "q": q, "limit": 50},
                         headers=h, timeout=30)
        time.sleep(0.4)
        if r.status_code != 200:
            print(f"-- PS5: busca '{q}' respondeu {r.status_code}")
            continue
        for p in r.json().get("results") or []:
            if p.get("id") and eh_console(p.get("name")):
                produtos[p["id"]] = p.get("name")
    reputacao, achados, qualquer, codigos = {}, [], [], {}
    for pid, nome in produtos.items():
        r = requests.get(f"{apis.ML}/products/{pid}/items", headers=h, timeout=30)
        time.sleep(0.4)
        codigos[r.status_code] = codigos.get(r.status_code, 0) + 1
        if r.status_code == 200:
            itens = r.json().get("results") or []
        else:
            # 28/11/2026: /products/ID/items responde 403 (PolicyAgent) para o aplicativo; o produto em si ainda diz o
            # anúncio vencedor (buy_box_winner) quando o Mercado Livre preenche esse campo
            rp = requests.get(f"{apis.ML}/products/{pid}", headers=h, timeout=30)
            time.sleep(0.4)
            bw = (rp.json().get("buy_box_winner") or {}) if rp.status_code == 200 else {}
            itens = [bw] if bw.get("price") else []
            codigos[f"produto {rp.status_code}"] = codigos.get(f"produto {rp.status_code}", 0) + 1
        for it in sorted((x for x in itens if x.get("price") and x.get("condition", "new") == "new"), key=lambda x: x["price"])[:1]:
            if eh_console(nome, float(it["price"])):
                anuncio = it.get("item_id") or it.get("id")
                qualquer.append({"modelo": nome, "loja": "Mercado Livre", "vendedor": None, "nivel": "vendedor não conferido",
                                 "preco": float(it["price"]), "url": f"https://www.mercadolivre.com.br/p/{pid}" + (f"?pdp_filters=item_id:{anuncio}" if anuncio else ""),
                                 "fonte": "API do Mercado Livre", "verificado": apis.agora(), "vendedor_ok": False})
        for it in sorted((x for x in itens if x.get("price") and x.get("condition", "new") == "new"),
                         key=lambda x: x["price"]):
            oficial = bool(it.get("official_store_id"))
            nivel, apelido = apis._ml_reputacao(h, it.get("seller_id"), reputacao) if it.get("seller_id") else (None, None)
            if not eh_console(nome, float(it["price"])):
                continue  # anúncio com preço que não é de console (jogo ou acessório ligado ao produto): pula
            if oficial or nivel in apis.LIDER:
                anuncio = it.get("item_id") or it.get("id")
                achados.append({"modelo": nome, "loja": "Mercado Livre", "vendedor": apelido or str(it.get("seller_id")),
                                "nivel": "loja oficial" if oficial else f"MercadoLíder {nivel}", "preco": float(it["price"]),
                                "url": f"https://www.mercadolivre.com.br/p/{pid}?pdp_filters=item_id:{anuncio}",
                                "fonte": "API do Mercado Livre", "verificado": apis.agora()})
                break
    antes = {(a["url"], a["preco"]) for a in dados.get("api", []) if a["preco"] < LIMITE}
    dados["api"] = sorted(achados, key=lambda a: a["preco"])
    dados["api_todos"] = sorted(qualquer, key=lambda a: a["preco"])[:10]
    # links do catálogo (sem preço), para a página nunca ficar sem PS5 nenhum quando a API não dá preço
    vistos, dados["catalogo"] = set(), []
    for pid, n in produtos.items():
        if n.lower() not in vistos and len(dados["catalogo"]) < 6:
            vistos.add(n.lower())
            dados["catalogo"].append({"modelo": n, "url": f"https://www.mercadolivre.com.br/p/{pid}", "visto": apis.agora()})
    print(f"-- PS5: respostas do Mercado Livre {codigos}")
    dados["lido"] = apis.agora()
    radar.gravar(ARQ, dados)
    abaixo = [a for a in dados["api"] if a["preco"] < LIMITE]
    menor = f'menor R$ {dados["api"][0]["preco"]:.2f}' if dados["api"] else "nenhum anúncio de loja oficial ou MercadoLíder"
    print(f"ok PS5: {len(produtos)} produtos de console no catálogo, {len(achados)} com vendedor conferido, "
          f"{len(abaixo)} abaixo de R$ {LIMITE:.0f} ({menor})")
    return [a for a in abaixo if (a["url"], a["preco"]) not in antes] + novos_kb


def vitrine():
    """Ofertas que vão para a página: abaixo do limite, link direto sem afiliado, preço visto há menos de
    radar.PRECO_MAX_HORAS. Mais barata primeiro."""
    dados = ler_arquivo()
    saida = []
    for a in dados.get("api", []) + dados.get("manuais", []) + [k for k in _lojas(dados) if k.get("vendedor_ok")]:
        if not a.get("preco") or a["preco"] >= LIMITE or radar.preco_velho(a.get("verificado")):
            continue
        if not _console(a):
            continue
        if not a.get("url") or radar.afiliado(a["url"]) or radar._AFILIADO_PUBLICO.search(a["url"]):
            continue
        saida.append(a)
    return sorted(saida, key=lambda a: a["preco"]), dados


def mais_barato(dados=None):
    """O PS5 mais barato encontrado até agora, mesmo acima do limite (pedidos do dono em 27 e 28/11/2026)."""
    return (mais_baratos(1, dados) or [None])[0]


def mais_baratos(n=3, dados=None):
    """Os n PS5 mais baratos encontrados até agora (pedido do dono em 28/11/2026: "os mais baratos, tem que pôr"):
    um por modelo e loja, o mais barato primeiro; vendedor não conferido entra com aviso na página."""
    dados = dados if dados is not None else ler_arquivo()
    def ok(a):
        return (a.get("preco") and not radar.preco_velho(a.get("verificado")) and _console(a)
                and a.get("url") and not radar.afiliado(a["url"]) and not radar._AFILIADO_PUBLICO.search(a["url"]))
    kb = _lojas(dados)
    conferidos = sorted((a for a in dados.get("api", []) + dados.get("manuais", []) + [k for k in kb if k.get("vendedor_ok")] if ok(a)),
                        key=lambda a: a["preco"])
    outros = sorted((a for a in dados.get("api_todos", []) + [k for k in kb if not k.get("vendedor_ok")] if ok(a)), key=lambda a: a["preco"])
    todos = sorted(conferidos + outros, key=lambda a: a["preco"])  # o mais barato primeiro, conferido ou não (com aviso)
    # o mais barato de cada loja sempre aparece (pedido do dono em 28/11/2026: KaBuM!, Americanas e Fast Shop); o
    # resto das vagas vai para os mais baratos no geral
    saida, vistos, lojas_vistas = [], set(), set()
    for a in todos:
        if a["loja"] not in lojas_vistas:
            lojas_vistas.add(a["loja"])
            vistos.add((a["modelo"].lower()[:60], a["loja"]))
            saida.append(a)
    for a in todos:
        chave = (a["modelo"].lower()[:60], a["loja"])
        if len(saida) >= max(n, len(lojas_vistas)):
            break
        if chave not in vistos:
            vistos.add(chave)
            saida.append(a)
    return sorted(saida, key=lambda a: a["preco"])


def limite_txt():
    """"R$ 3.700", para os textos da página e dos alertas."""
    return "R$ " + f"{LIMITE:,.0f}".replace(",", ".")


def avisar(novos):
    if not novos:
        return
    import alertas
    for a in novos[:3]:
        alertas.enviar(f"PS5 por R$ {a['preco']:.2f}".replace(".", ","),
                       f"{a['modelo']} na {a['loja']} ({a.get('vendedor') or 'loja'}), abaixo de {limite_txt()}",
                       link=a["url"], tags="video_game,moneybag")


if __name__ == "__main__":
    novos = ler()
    print(json.dumps(vitrine()[0], ensure_ascii=False, indent=1))
    print(f"{len(novos)} novos abaixo do limite")
