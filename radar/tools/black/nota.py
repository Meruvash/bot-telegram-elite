"""Nota de qualidade das ofertas do Radar Black de Verdade (0 a 100) e o nível de cada oferta.

Por que existe (plano de 25/11/2026): até aqui as listas, os destaques e os alertas usavam só o desconto real em %.
Com isso, um jogo de R$ 18 com 34% de desconto passava na frente de um jogo de R$ 380 com 30% (R$ 115 a menos).
A nota junta os sinais que os comparadores grandes usam, cada um de 0 a 1:

  desconto   quanto o preço está abaixo da média aparada de 180 dias (a régua do radar; PriceSpy usa a mesma ideia,
             menor preço de mercado dia a dia contra a tendência de 3 meses)
  historico  onde o preço cai entre a média e o menor preço do período; no menor preço (ou abaixo) vale 1
             (Amazon e Google mostram "menor preço em 30/90/365 dias")
  economia   reais economizados contra a média, em escala logarítmica (até R$ 10 vale 0, R$ 250 ou mais vale 1)
  relevancia nota BGG, prêmio ou resenha no site e quantas lojas vendem o jogo (jogo procurado aparece em mais lojas);
             expansão vale menos que jogo base
  confianca  de onde veio o preço e há quanto tempo foi lido; multiplica a soma, para preço velho ou de post da
             comunidade descer na lista sem sumir dela

Os PESOS e os LIMITES dos níveis são o ponto de partida. Eles são calibrados com a lista que o usuário marca
(conteudo/black/calibragem.json, quando existir), e depois com os cliques. Mudar um peso não tira nem põe oferta no
radar: quem decide quem entra continua sendo o corte de 20% do radar.py. A nota só decide a ordem, os destaques, os
níveis e o que vira alerta individual.
"""
import datetime as dt
import json
import math
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PESOS = {"desconto": 0.30, "historico": 0.20, "economia": 0.25, "relevancia": 0.25}
# confiança por fonte do preço: API oficial e página da loja foram lidas na loja; feed e Compara Jogos são repasse;
# post da comunidade não tem vendedor nem validade conferidos
CONF_FONTE = (("API", 1.0), ("página da loja", 1.0), ("feed da loja", 0.9), ("Compara Jogos", 0.85), ("achado da comunidade", 0.7))
# confiança pela idade da leitura (horas, fator): promoção acaba rápido
CONF_IDADE = ((6, 1.0), (12, 0.97), (24, 0.92), (48, 0.82), (96, 0.7))
DESC_MIN, DESC_MAX = 0.15, 0.45     # 15% (Quase Black) vale 0; 45% ou mais vale 1
ECON_PISO = 10.0                    # até R$ 10 economizados o sinal de economia vale 0
ECON_SATURA = 250.0                 # R$ economizados em que o sinal de economia chega a 1
BGG_MIN, BGG_MAX = 6.5, 8.2
LOJAS_SATURA = 8                    # jogo vendido em 8 lojas ou mais tem o máximo do sinal de lojas
EXPANSAO = 0.7                      # fator da relevância para expansões
# níveis: nota mínima de cada um (ponto de partida; a calibragem ajusta)
NIVEIS = (("Imperdível", 65), ("Muito boa", 52), ("Boa", 0))  # em 23/11/2026: ~15% dos jogos, ~50%, o resto


def _chave(nome):
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _lim(v, a, b):
    if b <= a:
        return 0.0
    return max(0.0, min(1.0, (v - a) / (b - a)))


def resenhas():
    """Nomes (normalizados) dos jogos com resenha no site (busca.json, tipo "r")."""
    try:
        return {_chave(x.get("n")) for x in json.loads((ROOT / "busca.json").read_text(encoding="utf-8")) if x.get("t") == "r"}
    except (FileNotFoundError, ValueError):
        return set()


def contar_lojas(hoje_d):
    """Quantas lojas diferentes vendem cada jogo (ofertas.json), como sinal de procura."""
    out = {}
    for slug, of in (hoje_d or {}).items():
        out[slug] = len({o.get("loja_id") or o.get("loja") for o in of.get("ofertas", []) if o.get("tipo") == "LINK" and o.get("por")})
    return out


def _horas(quando, agora):
    try:
        t = dt.datetime.fromisoformat(str(quando).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (agora - t).total_seconds() / 3600)


def confianca(x, agora):
    fonte = x.get("fonte_preco") or "Compara Jogos"
    f = next((v for k, v in CONF_FONTE if fonte.startswith(k) or k in fonte), 0.85)
    h = _horas(x.get("verificado"), agora)
    if h is None:
        return f * CONF_IDADE[-1][1]
    i = next((v for lim, v in CONF_IDADE if h <= lim), CONF_IDADE[-1][1] * 0.8)
    return f * i


def sinais(x, n_lojas=0, premiados=(), com_resenha=(), agora=None):
    """Os cinco sinais de uma oferta, cada um de 0 a 1."""
    agora = agora or dt.datetime.now(dt.timezone.utc)
    ref, por, menor = x["ref"], x["por"], x.get("menor") or x["ref"]
    if por <= menor or x.get("recorde"):
        hist = 1.0
    else:
        hist = _lim(ref - por, 0, ref - menor) if ref > menor else 0.0
    eco = max(0.0, ref - por)
    nome = _chave(x.get("nome"))
    bgg = x.get("bgg") or 0
    rel = 0.5 * _lim(bgg, BGG_MIN, BGG_MAX)
    rel += 0.25 * (1.0 if nome in premiados or nome in com_resenha else 0.0)
    rel += 0.25 * min(1.0, (n_lojas or 0) / LOJAS_SATURA)
    if x.get("tipo") == "expansion":
        rel *= EXPANSAO
    return {
        "desconto": _lim(x["desc"], DESC_MIN, DESC_MAX),
        "historico": hist,
        "economia": _lim(math.log1p(eco), math.log1p(ECON_PISO), math.log1p(ECON_SATURA)),
        "relevancia": rel,
        "confianca": confianca(x, agora),
    }


def nota(s, pesos=None):
    p = pesos or PESOS
    base = sum(p[k] * s[k] for k in p) / sum(p.values())
    return round(100 * base * s["confianca"], 1)


def nivel(n):
    return next(nome for nome, minimo in NIVEIS if n >= minimo)


def carregar_pesos():
    """Pesos calibrados (conteudo/black/nota_pesos.json), se existirem; senão, os de partida."""
    try:
        p = json.loads((ROOT / "conteudo" / "black" / "nota_pesos.json").read_text(encoding="utf-8"))
        return {k: float(p.get(k, v)) for k, v in PESOS.items()}
    except (FileNotFoundError, ValueError):
        return dict(PESOS)


def anotar(itens, hoje_d=None, premiados=(), agora=None):
    """Põe "nota", "nivel" e "sinais" em cada item (mexe nos próprios dicionários) e devolve a lista."""
    agora = agora or dt.datetime.now(dt.timezone.utc)
    lojas = contar_lojas(hoje_d)
    com_resenha = resenhas()
    pesos = carregar_pesos()
    for x in itens:
        s = sinais(x, lojas.get(x.get("slug"), 0), premiados, com_resenha, agora)
        x["sinais"] = {k: round(v, 3) for k, v in s.items()}
        x["nota"] = nota(s, pesos)
        x["nivel"] = nivel(x["nota"])
    return itens
