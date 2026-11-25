"""Testes da nota de qualidade:  python3 -m unittest radar/tools/black/test_nota.py"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nota  # noqa: E402

AGORA = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.timezone.utc)


def oferta(**k):
    base = {"slug": "x", "nome": "Jogo", "tipo": "game", "bgg": 7.8, "ref": 200.0, "por": 140.0, "menor": 150.0,
            "desc": 0.30, "recorde": True, "fonte_preco": "página da loja", "verificado": "2026-11-23T11:00:00+00:00"}
    base.update(k)
    return base


class TestNota(unittest.TestCase):
    def test_economia_alta_vence_desconto_maior_de_item_barato(self):
        caro = oferta(ref=380.0, por=250.0, menor=260.0, desc=0.34)
        barato = oferta(ref=17.0, por=10.0, menor=11.0, desc=0.41)
        n = lambda x: nota.nota(nota.sinais(x, 6, agora=AGORA))  # noqa: E731
        self.assertGreater(n(caro), n(barato))

    def test_preco_velho_e_comunidade_descem(self):
        s_novo = nota.sinais(oferta(), 6, agora=AGORA)
        s_velho = nota.sinais(oferta(verificado="2026-11-20T12:00:00+00:00"), 6, agora=AGORA)
        s_post = nota.sinais(oferta(fonte_preco="achado da comunidade (Ludofertas)"), 6, agora=AGORA)
        self.assertGreater(nota.nota(s_novo), nota.nota(s_velho))
        self.assertGreater(nota.nota(s_novo), nota.nota(s_post))

    def test_expansao_vale_menos(self):
        jogo = nota.sinais(oferta(), 6, agora=AGORA)
        exp = nota.sinais(oferta(tipo="expansion"), 6, agora=AGORA)
        self.assertLess(exp["relevancia"], jogo["relevancia"])

    def test_sinais_entre_0_e_1_e_niveis(self):
        s = nota.sinais(oferta(por=500.0, desc=-1.5), 0, agora=AGORA)
        self.assertTrue(all(0 <= v <= 1 for v in s.values()))
        self.assertEqual(nota.nivel(90), "Imperdível")
        self.assertEqual(nota.nivel(55), "Muito boa")
        self.assertEqual(nota.nivel(10), "Boa")


class TestCalibragem(unittest.TestCase):
    def test_auc(self):
        import calibrar
        self.assertEqual(calibrar.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]), 1.0)
        self.assertEqual(calibrar.auc([0.5, 0.5], [0, 1]), 0.5)

    def test_logistica_acha_o_sinal_que_importa(self):
        import calibrar
        import random
        r = random.Random(1)
        X = [[r.random(), r.random(), r.random(), r.random()] for _ in range(400)]
        y = [1 if x[3] > 0.7 else 0 for x in X]  # só a relevância decide
        w = calibrar.para_pesos(calibrar.logistica(X, y, passos=800))
        self.assertEqual(max(w, key=w.get), "relevancia")
        self.assertTrue(all(calibrar.PESO_MIN - 1e-9 <= v <= calibrar.PESO_MAX + 1e-9 for v in w.values()))


if __name__ == "__main__":
    unittest.main()
