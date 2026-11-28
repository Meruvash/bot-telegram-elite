"""Promoções de jogos de tabuleiro nas grandes lojas de varejo (pedido do dono em 28/11/2026: mais fontes de ofertas,
para o feed ter novidade toda vez que a pessoa volta).

Lojas na plataforma VTEX cuja consulta pública de catálogo (/api/catalog_system/pub/products/search) o robots.txt
libera: Ri Happy, Livrarias Curitiba, Toymania, Americanas e Fast Shop. Para cada uma, duas consultas por leitura
("jogo de tabuleiro" e "jogo de cartas"), no máximo uma leitura por loja a cada INTERVALO_H horas, pelo leitor de
ps5._direto: robots.txt conferido, identificação EliteBoardgamers, e 401/403/429 encerra sem insistir.

Estas lojas ainda não têm histórico de preço no radar, então o desconto mostrado é o ANUNCIADO PELA LOJA (preço "de"
contra o preço "por"), e a página diz isso no cartão: não entra na conta de "desconto real". O preço de cada dia fica
guardado em conteudo/black/varejo.json; com o histórico, dá para passar a calcular o desconto real também aqui.

Uso: python3 tools/black/varejo.py   (lê as lojas e mostra quantas promoções achou)
"""
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import radar  # noqa: E402

ARQ = radar.DADOS / "varejo.json"
LOJAS = {"Ri Happy": "https://www.rihappy.com.br", "Livrarias Curitiba": "https://www.livrariascuritiba.com.br",
         "Toymania": "https://www.toymania.com.br", "Americanas": "https://www.americanas.com.br",
         "Fast Shop": "https://site.fastshop.com.br"}
BUSCAS = ("jogo de tabuleiro", "jogo de cartas")
INTERVALO_H = 2       # cada loja é lida no máximo a cada 2 horas
CORTE = 0.20          # desconto anunciado mínimo para entrar no feed
PRECO_MIN = 40.0
GUARDA_DIAS = 3       # promoção que some da loja sai do arquivo depois disso
JOGO = re.compile(r"(?i)\bjogo|tabuleiro|board ?game|card ?game|\bcartas\b")
FORA = re.compile(r"(?i)video ?game|playstation|ps[45]\b|xbox|nintendo|switch|console|controle|pc gamer|mouse|teclado|headset|"
                  r"cadeira|mesa gamer|quebra-cabe[çc]a|puzzle|pelúcia|boneca|lego\b|massinha|slime|baralho de truco|tapete")


def _agora():
    return dt.datetime.now(dt.timezone.utc)


def ler_arquivo():
    try:
        return json.loads(ARQ.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"lojas": {}, "itens": {}}


def _melhor_oferta(p):
    """(preço, preço de tabela, foto) do vendedor mais barato com estoque."""
    melhor = None
    for it in p.get("items") or []:
        for sel in it.get("sellers") or []:
            o = sel.get("commertialOffer") or {}
            preco, tabela = o.get("Price"), o.get("ListPrice")
            if not preco or not o.get("AvailableQuantity"):
                continue
            if not melhor or preco < melhor[0]:
                img = next((i.get("imageUrl") for i in it.get("images") or [] if (i.get("imageUrl") or "").startswith("https://")), None)
                melhor = (float(preco), float(tabela or preco), img)
    return melhor


def ler_loja(loja, base):
    import ps5
    achados = {}
    for q in BUSCAS:
        texto = ps5._direto(f"{base}/api/catalog_system/pub/products/search?ft={quote(q)}&_from=0&_to=49")
        time.sleep(2)
        if not texto:
            continue
        try:
            produtos = json.loads(texto)
        except ValueError:
            continue
        for p in produtos:
            nome, link = p.get("productName") or "", p.get("link") or ""
            cats = " ".join(p.get("categories") or [])
            if not link.startswith("https://") or FORA.search(nome) or not (JOGO.search(nome) or JOGO.search(cats)):
                continue
            m = _melhor_oferta(p)
            if not m or m[0] < PRECO_MIN:
                continue
            achados[link] = {"n": nome[:120], "l": loja, "p": m[0], "t": m[1], "i": m[2]}
    return achados


def ler():
    """Lê as lojas que estão na vez, atualiza conteudo/black/varejo.json e devolve o arquivo."""
    dados = ler_arquivo()
    agora = _agora()
    hoje = agora.date().isoformat()
    for loja, base in LOJAS.items():
        ultima = dados["lojas"].get(loja)
        if ultima and (agora - dt.datetime.fromisoformat(ultima)).total_seconds() < INTERVALO_H * 3600:
            continue
        try:
            achados = ler_loja(loja, base)
        except Exception as ex:  # noqa: BLE001 — uma loja nunca derruba o robô
            print(f"aviso: varejo {loja} falhou ({ex.__class__.__name__}: {ex})")
            continue
        dados["lojas"][loja] = agora.isoformat(timespec="minutes")
        for url, a in achados.items():
            it = dados["itens"].get(url) or {"entrou": agora.isoformat(timespec="minutes"), "hist": {}}
            # volta a ser novidade quando o preço cai de novo
            if it.get("p") and a["p"] < it["p"] - 0.005:
                it["entrou"] = agora.isoformat(timespec="minutes")
            it.update(a)
            it["visto"] = agora.isoformat(timespec="minutes")
            it["hist"][hoje] = a["p"]
            it["hist"] = dict(sorted(it["hist"].items())[-180:])
            dados["itens"][url] = it
        print(f"ok varejo {loja}: {len(achados)} jogos lidos")
    limite = (agora - dt.timedelta(days=GUARDA_DIAS)).isoformat()
    dados["itens"] = {u: it for u, it in dados["itens"].items() if it.get("visto", "") >= limite}
    radar.gravar(ARQ, dados)
    return dados


def promocoes(dados=None):
    """Itens com desconto anunciado de CORTE ou mais, vistos nas últimas 6 horas, sem link de afiliado."""
    dados = dados if dados is not None else ler_arquivo()
    limite = (_agora() - dt.timedelta(hours=6)).isoformat()
    saida = []
    for url, it in dados.get("itens", {}).items():
        if it.get("visto", "") < limite or not it.get("t") or it["t"] <= it["p"]:
            continue
        desc = (it["t"] - it["p"]) / it["t"]
        if desc < CORTE or desc > 0.85 or radar.afiliado(url) or radar._AFILIADO_PUBLICO.search(url):
            continue
        saida.append({**it, "u": url, "d": desc})
    return sorted(saida, key=lambda a: a["entrou"], reverse=True)


if __name__ == "__main__":
    d = ler()
    pr = promocoes(d)
    print(f"{len(d['itens'])} jogos guardados, {len(pr)} com desconto anunciado de {CORTE:.0%} ou mais")
    for a in pr[:15]:
        print(f"  −{a['d']:.0%} {a['l']}: {a['n'][:60]} por R$ {a['p']:.2f} (de R$ {a['t']:.2f})")
