#!/usr/bin/env python3
"""Tira links de afiliado de terceiros dos dados do Black antes da publicação (27/11/2026).

A trava de publicação (rodar.sh) suspende a rodada inteira quando acha link de afiliado de terceiros em qualquer
arquivo de conteudo/black/ ou black/. Em 27/11/2026 um achado da comunidade com link de afiliado entrou em
comunidade.json e a página ficou mais de 6 horas sem ser publicada em plena Black Friday. Agora, antes da trava, este
script limpa os dados na origem: link de afiliado vira None (campo que é só o link) ou some do texto. A trava continua
lá, como última barreira; com os dados limpos ela não para mais tudo por causa de um post.

Uso: python3 tools/black/limpar_afiliados.py           limpa os dados (conteudo/black)
     python3 tools/black/limpar_afiliados.py --saida   limpa o que vai ao ar (black/), antes do envio
"""
import json
import re
import sys
from pathlib import Path

RADAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADAR / "tools"))
try:
    from verificar_site import AFILIADO_PUBLICO
except Exception:  # noqa: BLE001
    from radar import _AFILIADO_PUBLICO as AFILIADO_PUBLICO  # noqa: E402

URL = re.compile(r"https?://\S+")


def limpar_texto(s):
    """Devolve (texto limpo, quantos trechos saíram). Texto que é só um link de afiliado vira None."""
    if not AFILIADO_PUBLICO.search(s):
        return s, 0
    if URL.fullmatch(s.strip()):
        return None, 1
    n = 0

    def tira(m):
        nonlocal n
        if AFILIADO_PUBLICO.search(m.group(0)):
            n += 1
            return ""
        return m.group(0)
    s2 = URL.sub(tira, s)
    if AFILIADO_PUBLICO.search(s2):  # sobra sem http (ex.: "amzn.to/abc"): tira a palavra inteira
        palavras = s2.split(" ")
        fora = [w for w in palavras if AFILIADO_PUBLICO.search(w)]
        n += len(fora)
        s2 = " ".join(w for w in palavras if not AFILIADO_PUBLICO.search(w))
    return re.sub(r"\s{2,}", " ", s2).strip(), n


def limpar(obj):
    if isinstance(obj, dict):
        tot = 0
        for k in list(obj):
            obj[k], c = limpar(obj[k])
            tot += c
        return obj, tot
    if isinstance(obj, list):
        tot = 0
        for i, v in enumerate(obj):
            obj[i], c = limpar(v)
            tot += c
        return obj, tot
    if isinstance(obj, str):
        return limpar_texto(obj)
    return obj, 0


LINK_HTML = re.compile(r"""https?://[^\s"'<>]+""")


def limpar_saida():
    """Última barreira (pedido do dono em 27/11/2026: "se aparecer um link de afiliado, você ignora ele, conserta e
    publica o resto"): nos arquivos que vão ao ar (black/), link de afiliado vira "#" e sobra em texto some.
    A operação nunca para por causa de um link."""
    for arq in sorted((RADAR / "black").rglob("*")):
        if not arq.is_file() or arq.suffix.lower() not in (".html", ".json", ".xml", ".txt", ".js"):
            continue
        texto = arq.read_text(encoding="utf-8", errors="ignore")
        if not AFILIADO_PUBLICO.search(texto):
            continue
        n = 0

        def troca(m):
            nonlocal n
            if AFILIADO_PUBLICO.search(m.group(0)):
                n += 1
                return "#"
            return m.group(0)
        novo = LINK_HTML.sub(troca, texto)
        if AFILIADO_PUBLICO.search(novo):
            novo, k = re.subn(r"""[^\s"'<>]*(?:amzn\.to|amzlink\.to|link\.amazon|amzlinks\.|meli\.la|shope\.ee|s\.shopee|tidd\.ly|lmd\.ink|awin1\.com|redir\.lomadee)[^\s"'<>]*""", "#", novo)
            n += k
        arq.write_text(novo, encoding="utf-8")
        print(f"tirei {n} link(s) de afiliado de terceiros de {arq.relative_to(RADAR)} antes de publicar")


def main():
    if "--saida" in sys.argv:
        return limpar_saida()
    for arq in sorted((RADAR / "conteudo" / "black").rglob("*.json")):
        try:
            texto = arq.read_text(encoding="utf-8")
        except OSError:
            continue
        if not AFILIADO_PUBLICO.search(texto):
            continue
        try:
            dados = json.loads(texto)
        except ValueError:
            continue
        dados, n = limpar(dados)
        if n:
            arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            print(f"limpei {n} link(s) de afiliado de terceiros em {arq.relative_to(RADAR)}")


if __name__ == "__main__":
    main()
