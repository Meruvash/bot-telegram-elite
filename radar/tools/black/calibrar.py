"""Calibragem automática dos pesos da nota (nota.py), sem ninguém marcar nada.

Método (weak supervision, 25/11/2026): quem diz se uma oferta era boa são pessoas que já fazem esse julgamento de
graça, os canais de curadoria que o robô lê (Telegram: Compara Jogos, BG Turbo, Board Oferta, GameBox, Ludofertas)
e, quando existir, o clique no site (conteudo/black/cliques.json: {"slug|AAAA-MM-DD": n}). Para cada jogo e dia, o
robô monta os sinais da nota com o preço daquele dia (historico.json) e marca como positivo o que foi postado ou
clicado no mesmo dia, um dia antes ou um dia depois. Uma regressão logística acha o peso de cada sinal.

Trava: na primeira medição (25/11/2026, 7 dias de posts, 65 positivos) a regressão acertou só um pouco mais que o
acaso (AUC 0,55 na validação cruzada). Peso aprendido com tão pouco dado é ruído, então os pesos novos só valem quando:
  - há MIN_POSITIVOS ou mais positivos;
  - a AUC dos pesos novos na validação cruzada passa a dos pesos em uso por MARGEM ou mais;
  - nenhum peso fica fora de PESO_MIN..PESO_MAX (economia não zera: o piso de R$ 30 do dono continua valendo).
Senão, nada muda e o motivo fica no log. Cada treino grava uma linha em conteudo/black/calibragem/treinos.jsonl.

Uso (a agenda chama todo dia; treina só se o último treino tiver TREINO_DIAS ou mais):
  python3 tools/black/calibrar.py guardar   # copia os posts de curadoria para o arquivo permanente (sem limite de 7 dias)
  python3 tools/black/calibrar.py treinar [--forcar] [--simular]
"""
import argparse
import datetime as dt
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nota  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DADOS = ROOT / "conteudo" / "black"
PASTA = DADOS / "calibragem"
POSTS = PASTA / "posts.json"            # {"slug|AAAA-MM-DD": ["fonte", ...]}: guardado para sempre, só a chave
TREINOS = PASTA / "treinos.jsonl"
PESOS = DADOS / "nota_pesos.json"
CLIQUES = DADOS / "cliques.json"
F = ("desconto", "historico", "economia", "relevancia")
JANELA_TREINO = 90      # dias de histórico usados no treino
DESC_MIN_CANDIDATO = 0.10
MIN_DIAS_REF = 28
MIN_POSITIVOS = 150
MARGEM = 0.03
PESO_MIN, PESO_MAX = 0.05, 0.60
TREINO_DIAS = 7
DOBRAS = 5


def ler(p, padrao):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return padrao


def gravar(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


# ------------------------------------------------------------------ rótulos

def guardar():
    """Copia jogo, dia e canal dos posts de curadoria (comunidade.json guarda só 7 dias) para o arquivo permanente."""
    posts = ler(POSTS, {})
    antes = len(posts)
    for arq in (DADOS / "comunidade.json", DADOS / "promobit.json"):
        for v in ler(arq, {}).values():
            jogo, dia = v.get("jogo"), (v.get("publicado") or v.get("visto") or "")[:10]
            if not jogo or len(dia) != 10:
                continue
            fonte = (v.get("fonte") or ("Promobit" if arq.name == "promobit.json" else "?")).removeprefix("Telegram: ")
            lst = posts.setdefault(f"{jogo}|{dia}", [])
            if fonte not in lst:
                lst.append(fonte)
    gravar(POSTS, posts)
    print(f"ok calibragem: {len(posts)} jogo-dias com post guardados ({len(posts) - antes} novos)")


def rotulos():
    """Conjunto (slug, dia) positivo: post de curadoria ou clique no site, no dia, um antes ou um depois."""
    pos = set()
    chaves = list(ler(POSTS, {})) + [k for k, n in ler(CLIQUES, {}).items() if n]
    for k in chaves:
        slug, _, dia = k.partition("|")
        try:
            d = dt.date.fromisoformat(dia)
        except ValueError:
            continue
        for i in (-1, 0, 1):
            pos.add((slug, (d + dt.timedelta(days=i)).isoformat()))
    return pos


# ------------------------------------------------------------------ amostras

def amostras(hoje=None):
    """Um vetor de sinais por jogo e dia em que o preço estava pelo menos 10% abaixo da média aparada."""
    import radar  # noqa: E402 (aqui dentro: o radar importa a nota, que não importa a calibragem)
    hist, hoje_d = radar.ler(radar.HIST, {}), radar.ler(radar.HOJE, {})
    lojas, prem, res = nota.contar_lojas(hoje_d), radar.premiados(), nota.resenhas()
    hoje = hoje or dt.date.today()
    inicio = hoje - dt.timedelta(days=JANELA_TREINO)
    pos = rotulos()
    X, y = [], []
    for slug, h in hist.items():
        pts = h.get("pontos") or {}
        dias = sorted(d for d in pts if inicio.isoformat() <= d < hoje.isoformat())
        for d in dias:
            D = dt.date.fromisoformat(d)
            jan = [p for k, p in pts.items() if (D - dt.timedelta(days=180)).isoformat() <= k < d]
            if len(jan) < MIN_DIAS_REF:
                continue
            ref, menor, por = radar.aparada(jan), min(jan), pts[d]
            desc = (ref - por) / ref
            if desc < DESC_MIN_CANDIDATO:
                continue
            x = {"slug": slug, "nome": h.get("nome"), "tipo": h.get("tipo"), "bgg": h.get("bgg"), "ref": ref, "por": por,
                 "menor": menor, "desc": desc, "recorde": por <= menor, "fonte_preco": "página da loja",
                 "verificado": d + "T12:00:00+00:00"}
            s = nota.sinais(x, lojas.get(slug, 0), prem, res, dt.datetime.fromisoformat(d + "T12:00:00+00:00"))
            X.append([s[f] for f in F])
            y.append(1 if (slug, d) in pos else 0)
    return X, y


# ------------------------------------------------------------------ regressão logística e AUC, em Python puro

def logistica(X, y, passos=3000, taxa=0.5, l2=0.01):
    """Regressão logística com classes balanceadas (gradiente descendente). Devolve os coeficientes dos sinais."""
    n, k = len(X), len(X[0])
    npos = sum(y) or 1
    pw, nw = n / (2 * npos), n / (2 * max(1, n - npos))
    w, b = [0.0] * k, 0.0
    for _ in range(passos):
        gw, gb = [0.0] * k, 0.0
        for xi, yi in zip(X, y):
            z = b + sum(a * c for a, c in zip(w, xi))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            e = (p - yi) * (pw if yi else nw)
            gb += e
            for j in range(k):
                gw[j] += e * xi[j]
        w = [wj - taxa * (g / n + l2 * wj) for wj, g in zip(w, gw)]
        b -= taxa * gb / n
    return w


def auc(pontos, y):
    """Área sob a curva ROC (Mann-Whitney), com empates contando meio."""
    pares = sorted(zip(pontos, y))
    npos = sum(y)
    nneg = len(y) - npos
    if not npos or not nneg:
        return 0.5
    soma, i = 0.0, 0
    while i < len(pares):
        j = i
        while j < len(pares) and pares[j][0] == pares[i][0]:
            j += 1
        media = (i + j + 1) / 2  # posto médio do bloco empatado (postos começam em 1)
        soma += media * sum(1 for _, yy in pares[i:j] if yy)
        i = j
    return (soma - npos * (npos + 1) / 2) / (npos * nneg)


def para_pesos(coef):
    c = [max(0.0, v) for v in coef]
    if sum(c) <= 0:
        return None
    w = [v / sum(c) for v in c]
    # limites: nenhum sinal some nem domina sozinho. Quem passa do limite fica preso nele, e o que sobra da soma 1
    # é repartido entre os outros na proporção que a regressão deu
    preso = {}
    for _ in range(2 * len(w)):
        livres = [i for i in range(len(w)) if i not in preso]
        if not livres:
            break
        resto = 1 - sum(preso.values())
        base = sum(w[i] for i in livres)
        novo = {i: resto * (w[i] / base if base > 0 else 1 / len(livres)) for i in livres}
        acima = {i: PESO_MAX for i, v in novo.items() if v > PESO_MAX + 1e-12}
        abaixo = {i: PESO_MIN for i, v in novo.items() if v < PESO_MIN - 1e-12}
        if acima:            # primeiro prende quem passa do teto, depois quem fica abaixo do piso
            preso.update(acima)
        elif abaixo:
            preso.update(abaixo)
        else:
            preso.update(novo)
            break
    w = [preso[i] for i in range(len(w))]
    return dict(zip(F, (round(v, 3) for v in w)))


def pontuar(X, pesos):
    return [sum(pesos[f] * x[i] for i, f in enumerate(F)) for x in X]


def validar(X, y, semente=0):
    """AUC dos pesos aprendidos em validação cruzada (cada dobra treina sem ela e é pontuada com o que aprendeu)."""
    idx = list(range(len(y)))
    random.Random(semente).shuffle(idx)
    pts = [0.0] * len(y)
    for d in range(DOBRAS):
        teste = set(idx[d::DOBRAS])
        Xt = [X[i] for i in idx if i not in teste]
        yt = [y[i] for i in idx if i not in teste]
        p = para_pesos(logistica(Xt, yt, passos=1500))
        for i in teste:
            pts[i] = pontuar([X[i]], p)[0] if p else 0.0
    return auc(pts, y)


# ------------------------------------------------------------------ treino

def treinar(forcar=False, simular=False):
    ultimos = [json.loads(l) for l in TREINOS.read_text(encoding="utf-8").splitlines() if l.strip()] if TREINOS.exists() else []
    if ultimos and not forcar:
        quando = dt.datetime.fromisoformat(ultimos[-1]["hora"])
        if dt.datetime.now(dt.timezone.utc) - quando < dt.timedelta(days=TREINO_DIAS):
            print(f"ok calibragem: último treino em {quando:%d/%m}; o próximo é em {TREINO_DIAS} dias")
            return
    X, y = amostras()
    atual = nota.carregar_pesos()
    reg = {"hora": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "amostras": len(y), "positivos": sum(y),
           "pesos_em_uso": atual}
    if sum(y) < 10 or len(y) - sum(y) < 10:
        reg.update(aplicado=False, motivo="dados insuficientes para treinar")
    else:
        novos = para_pesos(logistica(X, y))
        reg["auc_em_uso"] = round(auc(pontuar(X, atual), y), 3)
        reg["auc_novos_validacao"] = round(validar(X, y), 3)
        reg["pesos_novos"] = novos
        if not novos:
            reg.update(aplicado=False, motivo="nenhum sinal ajudou a prever")
        elif sum(y) < MIN_POSITIVOS:
            reg.update(aplicado=False, motivo=f"só {sum(y)} positivos (mínimo {MIN_POSITIVOS})")
        elif reg["auc_novos_validacao"] < reg["auc_em_uso"] + MARGEM:
            reg.update(aplicado=False, motivo=f"pesos novos não acertam {MARGEM} a mais que os em uso")
        else:
            reg.update(aplicado=not simular, motivo="simulação" if simular else "pesos novos acertam mais")
            if not simular:
                gravar(PESOS, {**novos, "_calibrado": reg["hora"], "_auc": reg["auc_novos_validacao"]})
    if not simular:
        PASTA.mkdir(parents=True, exist_ok=True)
        with TREINOS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    print("ok calibragem:", json.dumps(reg, ensure_ascii=False))
    return reg


def main():
    a = argparse.ArgumentParser()
    a.add_argument("acao", choices=["guardar", "treinar"])
    a.add_argument("--forcar", action="store_true")
    a.add_argument("--simular", action="store_true")
    o = a.parse_args()
    if o.acao == "guardar":
        guardar()
    else:
        guardar()
        treinar(o.forcar, o.simular)


if __name__ == "__main__":
    main()
