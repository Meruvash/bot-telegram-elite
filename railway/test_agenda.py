import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

os.environ["DADOS"] = tempfile.mkdtemp()
import agenda  # noqa: E402

T0 = dt.datetime(2026, 11, 25, 12, 0, tzinfo=dt.timezone.utc)
TODOS = list(agenda.AGENDA)


def estado(**kw):
    e = {"inicio": T0.isoformat(), "ultimo_ok": {}, "falhas": {}}
    e.update(kw)
    return e


class TestVigia(unittest.TestCase):
    def setUp(self):
        agenda.VIGIA = Path(tempfile.mkdtemp()) / "vigia.json"
        agenda.RADAR = Path(tempfile.mkdtemp())
        self.enviados = []
        agenda.avisar_dono = self.enviados.append

    def ok_todos(self, quando):
        return {r: quando.isoformat() for r in agenda.PRAZO_H}

    def test_sem_problema_logo_depois_de_ligar(self):
        self.assertEqual(agenda.problemas(estado(), TODOS, T0 + dt.timedelta(minutes=50)), [])

    def test_robo_parado(self):
        e = estado(ultimo_ok=self.ok_todos(T0))
        e["ultimo_ok"]["normal"] = (T0 - dt.timedelta(hours=3)).isoformat()
        chaves = [c for c, _ in agenda.problemas(e, TODOS, T0 + dt.timedelta(minutes=10))]
        self.assertEqual(chaves, ["parado:normal"])

    def test_educado_tem_prazo_maior(self):
        e = estado(ultimo_ok=self.ok_todos(T0 + dt.timedelta(hours=5)))
        e["ultimo_ok"]["educado"] = T0.isoformat()
        self.assertEqual(agenda.problemas(e, TODOS, T0 + dt.timedelta(hours=5, minutes=30)), [])

    def test_robo_desligado_nao_avisa(self):
        e = estado()
        ligados = [r for r in TODOS if r != "normal"]
        e["ultimo_ok"] = {r: (T0 + dt.timedelta(hours=3)).isoformat() for r in ligados}
        self.assertEqual(agenda.problemas(e, ligados, T0 + dt.timedelta(hours=3)), [])

    def test_falhas_seguidas(self):
        e = estado(ultimo_ok=self.ok_todos(T0), falhas={"ml": 2})
        self.assertIn("falha:ml", [c for c, _ in agenda.problemas(e, TODOS, T0 + dt.timedelta(minutes=5))])

    def test_pagina_parada(self):
        pag = agenda.RADAR / "black" / "index.html"
        pag.parent.mkdir(parents=True)
        pag.write_text("x")
        velho = (T0 - dt.timedelta(hours=1)).timestamp()
        os.utime(pag, (velho, velho))
        agora = T0 + dt.timedelta(hours=3, minutes=5)
        e = estado(ultimo_ok=self.ok_todos(agora))
        self.assertEqual([c for c, _ in agenda.problemas(e, TODOS, agora)], ["pagina"])

    def test_avisa_uma_vez_repete_depois_e_avisa_resolvido(self):
        e = estado(ultimo_ok=self.ok_todos(T0), falhas={"normal": 3})
        agenda.vigiar(e, TODOS, T0 + dt.timedelta(minutes=5))
        agenda.vigiar(e, TODOS, T0 + dt.timedelta(minutes=10))
        self.assertEqual(len(self.enviados), 1)
        self.assertIn("normal terminou com erro 3 vezes", self.enviados[0])
        e["ultimo_ok"] = self.ok_todos(T0 + dt.timedelta(hours=6))  # os outros robôs seguem rodando bem
        agenda.vigiar(e, TODOS, T0 + dt.timedelta(hours=6, minutes=10))
        self.assertEqual(len(self.enviados), 2)
        e["falhas"]["normal"] = 0
        agenda.vigiar(e, TODOS, T0 + dt.timedelta(hours=6, minutes=15))
        self.assertEqual(len(self.enviados), 3)
        self.assertIn("resolvido", self.enviados[-1])

    def test_nao_fecha_aviso_logo_depois_do_deploy(self):
        agenda._gravar_vigia({"avisados": {"falha:normal": T0.isoformat()}})
        e = estado(ultimo_ok=self.ok_todos(T0))
        agenda.vigiar(e, TODOS, T0 + dt.timedelta(minutes=10))
        self.assertEqual(self.enviados, [])


if __name__ == "__main__":
    unittest.main()
