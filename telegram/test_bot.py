import datetime as dt
import unittest

import bot

AGORA = dt.datetime(2026, 11, 25, 15, 0, tzinfo=dt.timezone.utc)


class TestBot(unittest.TestCase):
    def feeds(self):
        return {
            "black": [{"id": "a1", "hora": "2026-11-25T14:00:00+00:00", "titulo": "−30% Root", "texto": "R$ 500 na Amazon <b>",
                       "url": "https://www.amazon.com.br/dp/B07F454YF3", "imagem": "https://x/img.jpg"},
                      {"id": "velho", "hora": "2026-11-20T14:00:00+00:00", "titulo": "antigo", "texto": "", "url": "https://x"}],
            "site": [{"id": "r-paleo", "tema": "resenhas", "hora": "2026-11-25T13:00:00Z", "titulo": "⭐ Resenha: Paleo",
                      "texto": "Dez módulos", "url": "https://eliteboardgamers.com.br/paleo/"},
                     {"id": "sem-url", "tema": "noticias", "hora": "2026-11-25T13:00:00Z", "titulo": "x"}],
        }

    def test_itens_junta_e_ordena(self):
        lista = bot.itens(self.feeds())
        self.assertEqual([a["id"] for a in lista], ["black:velho", "resenhas:r-paleo", "black:a1"])

    def test_novos_ignora_vistos_e_velhos(self):
        lista = bot.itens(self.feeds())
        fila = bot.novos(lista, {"publicados": ["resenhas:r-paleo"]}, agora=AGORA)
        self.assertEqual([a["id"] for a in fila], ["black:a1"])

    def test_escapa_html(self):
        a = bot.itens(self.feeds())[-1]
        self.assertIn("&lt;b&gt;", bot.texto_telegram(a))
        self.assertIn("Black de Verdade", bot.texto_telegram(a))

    def test_whatsapp_sem_html(self):
        a = bot.itens(self.feeds())[1]
        t = bot.texto_whatsapp(a)
        self.assertTrue(t.startswith("⭐ *Resenha: Paleo*"))
        b = bot.texto_whatsapp(bot.itens(self.feeds())[-1])
        self.assertTrue(b.startswith("🔥 *−30% Root*"))
        self.assertTrue(t.endswith("https://eliteboardgamers.com.br/paleo/"))

    def test_canal(self):
        self.assertEqual(bot.canal("meucanal"), "@meucanal")
        self.assertEqual(bot.canal("@meucanal"), "@meucanal")
        self.assertEqual(bot.canal("123456"), "123456")
        self.assertEqual(bot.canal("-100123"), "-100123")
        self.assertEqual(bot.canal(""), "")


if __name__ == "__main__":
    unittest.main()
